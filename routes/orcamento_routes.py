from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from extensions import db, limiter, socketio
from models import PedidoOrcamento, RespostaOrcamento, Servico, Usuario, Mensagem
from utils.categorias import CATEGORIAS, CATEGORIAS_POR_GRUPO
from services.push_service import notificar

orcamento_bp = Blueprint('orcamento', __name__, url_prefix='/orcamento')

MAX_RESPOSTAS = 5          # cada pedido recebe no máximo 5 propostas, para o cliente não ser bombardeado
VALIDADE_DIAS = 15         # depois disso o pedido sai da lista dos prestadores
MAX_PEDIDOS_ABERTOS = 3    # por cliente

URGENCIAS = {
    'urgente': 'Urgente (hoje ou amanhã)',
    'semana': 'Nesta semana',
    'mes': 'Neste mês',
    'flexivel': 'Sem pressa',
}


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def pedidos_abertos():
    """Pedidos que ainda aceitam propostas: abertos, dentro da validade e de contas ativas"""
    limite = datetime.utcnow() - timedelta(days=VALIDADE_DIAS)
    return PedidoOrcamento.query.join(Usuario, PedidoOrcamento.cliente_id == Usuario.id).filter(
        PedidoOrcamento.status == 'aberto',
        PedidoOrcamento.criado_em >= limite,
        Usuario.desativada == False
    )


def categorias_do_prestador(prestador_id):
    return [c for (c,) in db.session.query(Servico.categoria).filter_by(prestador_id=prestador_id, removido=False).distinct() if c]


def contar_pedidos_para(prestador_id):
    """Quantos pedidos abertos existem nas categorias em que o prestador atua (para o painel)"""
    categorias = categorias_do_prestador(prestador_id)
    if not categorias:
        return 0
    return pedidos_abertos().filter(
        PedidoOrcamento.categoria.in_(categorias),
        PedidoOrcamento.cliente_id != prestador_id
    ).count()


def avisar(usuario_id, titulo, mensagem, url='/'):
    """Aviso na tela para quem está com o site aberto; notificação push para quem está fora"""
    notificar(usuario_id, titulo, mensagem, url)


# ============================================
# CLIENTE: PEDIR ORÇAMENTO
# ============================================

@orcamento_bp.route('/novo', methods=['GET', 'POST'])
@login_required
@limiter.limit('10 per hour', methods=['POST'])
def novo():
    if request.method == 'POST':
        categoria = request.form.get('categoria', '')
        descricao = request.form.get('descricao', '').strip()[:2000]
        local = request.form.get('local', '').strip()[:200]
        urgencia = request.form.get('urgencia', 'flexivel')

        erro = None
        if categoria not in CATEGORIAS:
            erro = 'Escolha uma categoria.'
        elif len(descricao) < 15:
            erro = 'Descreva o que você precisa com um pouco mais de detalhe (pelo menos 15 caracteres).'
        elif not local:
            erro = 'Informe o bairro ou a cidade.'
        elif urgencia not in URGENCIAS:
            erro = 'Escolha para quando você precisa.'
        elif pedidos_abertos().filter(PedidoOrcamento.cliente_id == current_user.id).count() >= MAX_PEDIDOS_ABERTOS:
            erro = f'Você já tem {MAX_PEDIDOS_ABERTOS} pedidos em aberto. Encerre um deles antes de criar outro.'

        if erro:
            flash(erro, 'danger')
            return render_template('orcamento/novo.html', grupos=CATEGORIAS_POR_GRUPO, urgencias=URGENCIAS,
                                   valores=request.form)

        pedido = PedidoOrcamento(cliente_id=current_user.id, categoria=categoria, descricao=descricao,
                                 local=local, urgencia=urgencia)
        db.session.add(pedido)
        db.session.commit()

        # Avisa em tempo real os prestadores que atuam nessa categoria
        prestadores = db.session.query(Servico.prestador_id).filter(
            Servico.categoria == categoria, Servico.prestador_id != current_user.id, Servico.removido == False
        ).distinct().all()
        for (prestador_id,) in prestadores:
            avisar(prestador_id, 'Novo pedido de orçamento', f'{categoria}: {descricao[:80]}', url_for('orcamento.pedidos'))

        if prestadores:
            flash(f'✅ Pedido enviado para {len(prestadores)} profissional(is) de {categoria}. As propostas chegam pelo chat e aparecem aqui.', 'success')
        else:
            flash(f'✅ Pedido publicado. Ainda não há profissionais de {categoria} cadastrados; ele fica visível para quem atende outras categorias.', 'info')
        return redirect(url_for('orcamento.meus'))

    return render_template('orcamento/novo.html', grupos=CATEGORIAS_POR_GRUPO, urgencias=URGENCIAS,
                           valores={'categoria': request.args.get('categoria', '')})


@orcamento_bp.route('/meus')
@login_required
def meus():
    pedidos = PedidoOrcamento.query.filter_by(cliente_id=current_user.id).order_by(PedidoOrcamento.criado_em.desc()).all()
    limite = datetime.utcnow() - timedelta(days=VALIDADE_DIAS)
    return render_template('orcamento/meus.html', pedidos=pedidos, urgencias=URGENCIAS,
                           max_respostas=MAX_RESPOSTAS, limite=limite)


@orcamento_bp.route('/<int:pedido_id>/fechar', methods=['POST'])
@login_required
def fechar(pedido_id):
    pedido = PedidoOrcamento.query.get_or_404(pedido_id)
    if pedido.cliente_id != current_user.id:
        abort(404)

    pedido.status = 'fechado'
    db.session.commit()
    flash('Pedido encerrado. Ele não recebe mais propostas.', 'success')
    return redirect(url_for('orcamento.meus'))


# ============================================
# PRESTADOR: VER PEDIDOS E ENVIAR PROPOSTA
# ============================================

@orcamento_bp.route('/pedidos')
@login_required
def pedidos():
    if current_user.tipo != 'prestador':
        flash('Esta página é para prestadores. Para pedir um orçamento, use "Pedir orçamento".', 'info')
        return redirect(url_for('orcamento.novo'))

    categorias = categorias_do_prestador(current_user.id)
    ver_todas = request.args.get('todas') == '1' or not categorias

    query = pedidos_abertos().filter(PedidoOrcamento.cliente_id != current_user.id)
    if not ver_todas:
        query = query.filter(PedidoOrcamento.categoria.in_(categorias))
    lista = query.order_by(PedidoOrcamento.criado_em.desc()).limit(100).all()

    ja_respondidos = {r.pedido_id for r in RespostaOrcamento.query.filter_by(prestador_id=current_user.id).all()}

    return render_template('orcamento/pedidos.html', pedidos=lista, urgencias=URGENCIAS,
                           categorias=categorias, ver_todas=ver_todas, ja_respondidos=ja_respondidos,
                           max_respostas=MAX_RESPOSTAS)


@orcamento_bp.route('/<int:pedido_id>/responder', methods=['POST'])
@login_required
@limiter.limit('20 per hour')
def responder(pedido_id):
    if current_user.tipo != 'prestador':
        abort(403)

    pedido = pedidos_abertos().filter(PedidoOrcamento.id == pedido_id).first()
    if not pedido or pedido.cliente_id == current_user.id:
        flash('Este pedido não está mais disponível.', 'warning')
        return redirect(url_for('orcamento.pedidos'))

    mensagem = request.form.get('mensagem', '').strip()[:1000]
    if len(mensagem) < 10:
        flash('Escreva uma mensagem para o cliente (pelo menos 10 caracteres).', 'danger')
        return redirect(url_for('orcamento.pedidos'))

    valor = None
    if request.form.get('valor', '').strip():
        try:
            valor = float(request.form['valor'].replace(',', '.'))
        except ValueError:
            valor = -1
        if not 0 < valor < 10_000_000:
            flash('Valor estimado inválido.', 'danger')
            return redirect(url_for('orcamento.pedidos'))

    if RespostaOrcamento.query.filter_by(pedido_id=pedido.id, prestador_id=current_user.id).first():
        flash('Você já enviou uma proposta para este pedido.', 'info')
        return redirect(url_for('orcamento.pedidos'))
    if len(pedido.respostas) >= MAX_RESPOSTAS:
        flash(f'Este pedido já recebeu as {MAX_RESPOSTAS} propostas permitidas.', 'warning')
        return redirect(url_for('orcamento.pedidos'))

    db.session.add(RespostaOrcamento(pedido_id=pedido.id, prestador_id=current_user.id, mensagem=mensagem, valor=valor))

    # A proposta também vai para o chat, onde a conversa continua
    resumo = pedido.descricao[:60] + ('...' if len(pedido.descricao) > 60 else '')
    texto = f'Olá! Vi seu pedido de orçamento de {pedido.categoria} ("{resumo}").\n\n{mensagem}'
    if valor:
        texto += f'\n\nValor estimado: R$ {valor:.2f}'.replace('.', ',')
    mensagem_chat = Mensagem(remetente_id=current_user.id, destinatario_id=pedido.cliente_id, conteudo=texto)
    db.session.add(mensagem_chat)
    db.session.commit()

    from routes.chat_routes import entregar
    entregar(mensagem_chat)
    avisar(pedido.cliente_id, 'Nova proposta de orçamento', f'{current_user.nome} respondeu ao seu pedido de {pedido.categoria}.', url_for('orcamento.meus'))

    flash('Proposta enviada! O cliente recebeu sua mensagem no chat.', 'success')
    return redirect(url_for('orcamento.pedidos'))
