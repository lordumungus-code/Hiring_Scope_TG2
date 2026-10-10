from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db
from models import (Usuario, Servico, Avaliacao, Contrato, Solicitacao, Assinatura, ContratoFormal,
                    PedidoOrcamento, servicos_ativos)
from services.conta_service import excluir_conta
from services.moderacao_service import remover_servico, bloquear_usuario, desbloquear_usuario
from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Decorator para verificar se é admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso negado. Área restrita para administradores.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def usuarios_existentes():
    """Usuários de verdade: as contas excluídas (anonimizadas) ficam de fora das listas e dos totais"""
    return Usuario.query.filter(~Usuario.email.like('%@removido.invalid'))


def voltar(padrao):
    """Volta para a tela do painel de onde a ação partiu (lista, detalhe ou dashboard)"""
    origem = request.form.get('voltar', '')
    return redirect(origem if origem.startswith('/admin') else url_for(padrao))


# ============================================
# DASHBOARD ADMIN
# ============================================

@admin_bp.route('/')
@admin_required
def dashboard():
    """Dashboard do administrador"""
    agora = datetime.utcnow()
    semana = agora - timedelta(days=7)

    usuarios = usuarios_existentes()
    total_usuarios = usuarios.count()

    # Contratos por status
    por_status = dict(db.session.query(Contrato.status, func.count(Contrato.id)).group_by(Contrato.status).all())
    status_contratos = [
        ('pendente', 'Pendentes', 'warning', por_status.get('pendente', 0)),
        ('aceito', 'Aceitos', 'info', por_status.get('aceito', 0)),
        ('em_andamento', 'Em andamento', 'primary', por_status.get('em_andamento', 0)),
        ('concluido', 'Concluídos', 'success', por_status.get('concluido', 0)),
        ('cancelado', 'Cancelados', 'secondary', por_status.get('cancelado', 0)),
    ]

    # Cadastros por dia nos últimos 14 dias (horário de Brasília)
    inicio = (agora - timedelta(hours=3)).date() - timedelta(days=13)
    por_dia = {inicio + timedelta(days=i): 0 for i in range(14)}
    for (quando,) in usuarios.filter(Usuario.data_cadastro >= agora - timedelta(days=15)).with_entities(Usuario.data_cadastro):
        dia = (quando - timedelta(hours=3)).date()
        if dia in por_dia:
            por_dia[dia] += 1
    maior = max(por_dia.values()) or 1
    cadastros_por_dia = [
        {'dia': dia.strftime('%d/%m'), 'total': total, 'altura': round(total * 100 / maior)}
        for dia, total in por_dia.items()
    ]

    return render_template(
        'admin/dashboard.html',
        # Usuários
        total_usuarios=total_usuarios,
        novos_usuarios=usuarios.filter(Usuario.data_cadastro >= semana).count(),
        total_prestadores=usuarios.filter_by(tipo='prestador').count(),
        total_clientes=usuarios.filter_by(tipo='cliente').count(),
        total_admins=usuarios.filter_by(is_admin=True).count(),
        total_bloqueados=usuarios.filter_by(bloqueada=True).count(),
        total_dormindo=usuarios.filter_by(desativada=True, bloqueada=False).count(),
        # Serviços
        total_servicos=servicos_ativos().count(),
        novos_servicos=servicos_ativos().filter(Servico.data_postagem >= semana).count(),
        servicos_destaque=servicos_ativos().filter_by(destaque=True).count(),
        # Contratos e avaliações
        total_contratos=sum(por_status.values()),
        status_contratos=status_contratos,
        contratos_abertos=sum(por_status.get(s, 0) for s in ('pendente', 'aceito', 'em_andamento')),
        total_avaliacoes=Avaliacao.query.count(),
        media_geral=round(db.session.query(func.avg(Avaliacao.nota)).scalar() or 0, 1),
        # Recursos pagos e movimento
        planos_ativos=Assinatura.query.filter(Assinatura.status == 'ativa', Assinatura.data_fim > agora).count(),
        formais_pagos=ContratoFormal.query.filter(ContratoFormal.pago_em.isnot(None)).count(),
        formais_assinados=ContratoFormal.query.filter_by(status='assinado').count(),
        pedidos_abertos=PedidoOrcamento.query.filter(
            PedidoOrcamento.status == 'aberto', PedidoOrcamento.criado_em >= agora - timedelta(days=15)
        ).count(),
        # Listas
        cadastros_por_dia=cadastros_por_dia,
        usuarios_recentes=usuarios.order_by(Usuario.data_cadastro.desc()).limit(8).all(),
        servicos_recentes=servicos_ativos().order_by(Servico.data_postagem.desc()).limit(8).all(),
    )

# ============================================
# GERENCIAR USUÁRIOS
# ============================================

@admin_bp.route('/usuarios')
@admin_required
def usuarios():
    """Lista todos os usuários"""
    search = request.args.get('search', '')
    tipo = request.args.get('tipo', '')

    query = usuarios_existentes()

    if search:
        query = query.filter(
            Usuario.nome.ilike(f'%{search}%') |
            Usuario.email.ilike(f'%{search}%')
        )
    if tipo == 'prestador':
        query = query.filter_by(tipo='prestador', is_admin=False)
    elif tipo == 'cliente':
        query = query.filter_by(tipo='cliente')
    elif tipo == 'admin':
        query = query.filter_by(is_admin=True)
    elif tipo == 'bloqueado':
        query = query.filter_by(bloqueada=True)
    elif tipo == 'dormindo':
        query = query.filter_by(desativada=True, bloqueada=False)

    usuarios = query.order_by(Usuario.data_cadastro.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20
    )

    return render_template('admin/usuarios.html', usuarios=usuarios, search=search, tipo=tipo)

@admin_bp.route('/usuarios/<int:user_id>')
@admin_required
def usuario_detalhe(user_id):
    """Detalhes de um usuário específico"""
    usuario = Usuario.query.get_or_404(user_id)

    # Estatísticas
    if usuario.tipo == 'prestador':
        total_servicos = servicos_ativos().filter_by(prestador_id=usuario.id).count()
        total_contratos = Contrato.query.filter_by(prestador_id=usuario.id).count()
        media_avaliacoes = usuario.media_avaliacoes()
    else:
        total_servicos = 0
        total_contratos = Contrato.query.filter_by(cliente_id=usuario.id).count()
        media_avaliacoes = 0

    return render_template('admin/usuario_detalhe.html',
                         usuario=usuario,
                         total_servicos=total_servicos,
                         total_contratos=total_contratos,
                         media_avaliacoes=media_avaliacoes)

@admin_bp.route('/usuarios/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Ativa/desativa admin de um usuário"""
    usuario = Usuario.query.get_or_404(user_id)

    if usuario.id == current_user.id:
        flash('Você não pode alterar seu próprio status de admin.', 'danger')
        return redirect(url_for('admin.usuario_detalhe', user_id=user_id))

    usuario.is_admin = not usuario.is_admin
    db.session.commit()

    status = 'ativado' if usuario.is_admin else 'desativado'
    flash(f'Admin {status} para {usuario.nome}.', 'success')
    return redirect(url_for('admin.usuario_detalhe', user_id=user_id))

@admin_bp.route('/usuarios/<int:user_id>/bloquear', methods=['POST'])
@admin_required
def bloquear(user_id):
    """Bloqueia ou desbloqueia uma conta: ela não entra mais e some do site, mas nada é apagado"""
    usuario = Usuario.query.get_or_404(user_id)

    if usuario.id == current_user.id:
        flash('Você não pode bloquear a si mesmo.', 'danger')
    elif usuario.is_admin:
        flash('Remova o acesso de administrador antes de bloquear esta conta.', 'danger')
    elif usuario.excluida:
        flash('Esta conta já foi excluída.', 'warning')
    elif usuario.bloqueada:
        desbloquear_usuario(usuario)
        db.session.commit()
        flash(f'Conta de {usuario.nome} desbloqueada.', 'success')
    else:
        bloquear_usuario(usuario)
        db.session.commit()
        flash(f'Conta de {usuario.nome} bloqueada. O perfil e os serviços saíram do ar.', 'success')

    return redirect(url_for('admin.usuario_detalhe', user_id=user_id))

@admin_bp.route('/usuarios/<int:user_id>/excluir', methods=['POST'])
@admin_required
def excluir_usuario(user_id):
    """Exclui uma conta definitivamente (mesma regra de quando o próprio usuário exclui a conta)"""
    usuario = Usuario.query.get_or_404(user_id)
    detalhe = redirect(url_for('admin.usuario_detalhe', user_id=user_id))

    if usuario.id == current_user.id:
        flash('Para excluir a sua própria conta, use "Gerenciar Conta" no seu perfil.', 'danger')
        return detalhe
    if usuario.is_admin:
        flash('Remova o acesso de administrador antes de excluir esta conta.', 'danger')
        return detalhe
    if usuario.excluida:
        flash('Esta conta já foi excluída.', 'warning')
        return redirect(url_for('admin.usuarios'))
    if request.form.get('confirmacao', '').strip().upper() != 'EXCLUIR':
        flash('Para excluir a conta, digite EXCLUIR no campo de confirmação.', 'danger')
        return detalhe

    nome, email = usuario.nome, usuario.email
    excluir_conta(usuario)
    print(f"🗑️ Admin {current_user.email} excluiu a conta {email} (id {user_id})")

    flash(f'Conta de {nome} ({email}) excluída.', 'success')
    return redirect(url_for('admin.usuarios'))

# ============================================
# GERENCIAR SERVIÇOS
# ============================================

@admin_bp.route('/servicos')
@admin_required
def servicos():
    """Lista todos os serviços"""
    search = request.args.get('search', '')
    categoria = request.args.get('categoria', '')
    destaque = request.args.get('destaque', '')

    query = servicos_ativos()

    if search:
        query = query.filter(
            Servico.titulo.ilike(f'%{search}%') |
            Servico.descricao.ilike(f'%{search}%')
        )
    if categoria:
        query = query.filter_by(categoria=categoria)
    if destaque == 'true':
        query = query.filter_by(destaque=True)
    elif destaque == 'false':
        query = query.filter_by(destaque=False)

    servicos = query.order_by(Servico.data_postagem.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=20)

    # Lista de categorias para filtro
    categorias = db.session.query(Servico.categoria).filter(Servico.removido == False).distinct().all()

    return render_template('admin/servicos.html', servicos=servicos, search=search, categoria=categoria, destaque=destaque, categorias=categorias)

@admin_bp.route('/servicos/<int:servico_id>/delete', methods=['POST'])
@admin_required
def delete_servico(servico_id):
    """Remove um serviço"""
    servico = Servico.query.get_or_404(servico_id)
    if servico.removido:
        flash('Este serviço já foi removido.', 'warning')
        return voltar('admin.servicos')

    titulo = servico.titulo
    resultado = remover_servico(servico)
    db.session.commit()
    print(f"🗑️ Admin {current_user.email} removeu o serviço \"{titulo}\" (id {servico_id}, {resultado})")

    if resultado == 'oculto':
        flash(f'Serviço "{titulo}" removido do site. Como já teve contratações, o histórico delas foi preservado.', 'success')
    else:
        flash(f'Serviço "{titulo}" removido com sucesso.', 'success')
    return voltar('admin.servicos')

@admin_bp.route('/servicos/<int:servico_id>/toggle-destaque', methods=['POST'])
@admin_required
def toggle_destaque(servico_id):
    """Ativa/desativa destaque de um serviço"""
    servico = Servico.query.get_or_404(servico_id)
    servico.destaque = not servico.destaque

    db.session.commit()

    status = 'ativado' if servico.destaque else 'desativado'
    flash(f'Destaque {status} para "{servico.titulo}".', 'success')
    return redirect(url_for('admin.servicos'))

# ============================================
# GERENCIAR AVALIAÇÕES
# ============================================

@admin_bp.route('/avaliacoes')
@admin_required
def avaliacoes():
    """Lista todas as avaliações"""
    nota = request.args.get('nota', '')
    search = request.args.get('search', '')

    query = Avaliacao.query

    if nota and nota.isdigit():
        query = query.filter_by(nota=int(nota))
    if search:
        query = query.join(Usuario, Avaliacao.cliente_id == Usuario.id).filter(
            Usuario.nome.ilike(f'%{search}%') |
            Avaliacao.comentario.ilike(f'%{search}%')
        )

    avaliacoes = query.order_by(Avaliacao.data_avaliacao.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=20)

    return render_template('admin/avaliacoes.html', avaliacoes=avaliacoes, nota=nota, search=search)

@admin_bp.route('/avaliacoes/<int:avaliacao_id>/delete', methods=['POST'])
@admin_required
def delete_avaliacao(avaliacao_id):
    """Remove uma avaliação"""
    avaliacao = Avaliacao.query.get_or_404(avaliacao_id)

    db.session.delete(avaliacao)
    db.session.commit()

    flash('Avaliação removida com sucesso.', 'success')
    return redirect(url_for('admin.avaliacoes'))

# ============================================
# GERENCIAR CONTRATOS
# ============================================

@admin_bp.route('/contratos')
@admin_required
def contratos():
    """Lista todos os contratos"""
    status = request.args.get('status', '')

    query = Contrato.query

    if status:
        query = query.filter_by(status=status)

    contratos = query.order_by(Contrato.data_solicitacao.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=20)

    # Status para filtro
    status_list = ['pendente', 'aceito', 'em_andamento', 'concluido', 'cancelado']

    return render_template('admin/contratos.html', contratos=contratos, status=status, status_list=status_list)

# ============================================
# ESTATÍSTICAS E RELATÓRIOS
# ============================================

@admin_bp.route('/estatisticas')
@admin_required
def estatisticas():
    """Estatísticas avançadas"""
    # Usuários por mês
    usuarios_por_mes = db.session.query(
        func.strftime('%Y-%m', Usuario.data_cadastro).label('mes'),
        func.count(Usuario.id).label('total')
    ).filter(~Usuario.email.like('%@removido.invalid')).group_by('mes').order_by('mes').limit(12).all()

    # Serviços por categoria
    servicos_por_categoria = db.session.query(
        Servico.categoria,
        func.count(Servico.id).label('total')
    ).filter(Servico.removido == False).group_by(Servico.categoria).all()

    # Contratos por status
    contratos_por_status = db.session.query(
        Contrato.status,
        func.count(Contrato.id).label('total')
    ).group_by(Contrato.status).all()

    return render_template('admin/estatisticas.html',
                         usuarios_por_mes=usuarios_por_mes,
                         servicos_por_categoria=servicos_por_categoria,
                         contratos_por_status=contratos_por_status)

# ============================================
# CRIAÇÃO DO PRIMEIRO ADMIN (via script)
# ============================================

def criar_admin(email, senha, nome):
    """Função para criar o primeiro administrador"""
    from models import Usuario

    usuario = Usuario.query.filter_by(email=email).first()
    if usuario:
        if not usuario.is_admin:
            usuario.is_admin = True
            db.session.commit()
            print(f"✅ {email} agora é administrador!")
        else:
            print(f"⚠️ {email} já é administrador.")
    else:
        novo_admin = Usuario(
            nome=nome,
            email=email,
            telefone='',
            tipo='prestador',
            is_admin=True
        )
        novo_admin.set_password(senha)
        db.session.add(novo_admin)
        db.session.commit()
        print(f"✅ Administrador {nome} criado com sucesso!")
