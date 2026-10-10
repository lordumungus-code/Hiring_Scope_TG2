from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from extensions import db
from models import Assinatura, Servico
from services.mercado_pago_service import criar_link_pagamento, verificar_pagamento

assinatura_bp = Blueprint('assinatura', __name__, url_prefix='/assinatura')

PLANOS = {
    'basico': {'nome': 'Básico', 'valor': 9.99},
    'pro': {'nome': 'Pro', 'valor': 29.90}
}


@assinatura_bp.route('/checkout/<plano>')
@login_required
def checkout(plano):
    """Página de checkout para o plano escolhido"""

    print(f"🔍 Checkout chamado para plano: {plano}")

    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem contratar planos', 'danger')
        return redirect(url_for('main.index'))

    if plano not in PLANOS:
        flash('Plano inválido', 'danger')
        return redirect(url_for('servico.planos_destaque'))

    config = PLANOS[plano]

    # Criar link de pagamento
    result = criar_link_pagamento(
        plano=plano,
        plano_nome=config['nome'],
        plano_valor=config['valor'],
        prestador_id=current_user.id,
        prestador_email=current_user.email,
        prestador_nome=current_user.nome
    )

    if result and result.get('success') and result.get('url'):
        print(f"🚀 Redirecionando para: {result['url']}")
        return redirect(result['url'])
    else:
        print(f"❌ Erro no checkout: {result}")
        flash('Erro ao criar link de pagamento. Tente novamente.', 'danger')
        return redirect(url_for('servico.planos_destaque'))


@assinatura_bp.route('/sucesso')
@login_required
def sucesso():
    """Página de retorno após o pagamento: só ativa se o Mercado Pago confirmar"""

    session.pop('plano_contratado', None)

    # O Mercado Pago devolve o id do pagamento na URL de retorno
    payment_id = request.args.get('payment_id') or request.args.get('collection_id')
    resultado = confirmar_pagamento(payment_id, prestador_id_esperado=current_user.id) if payment_id else 'invalido'

    if resultado in ('ativada', 'ja_processado'):
        flash('✅ Assinatura ativada com sucesso! Seus serviços estão em destaque.', 'success')
    elif resultado == 'pendente':
        flash('Seu pagamento está em análise. O plano será ativado assim que for aprovado.', 'info')
    else:
        flash('Não foi possível confirmar o pagamento. Se você já pagou, o plano será ativado assim que o Mercado Pago confirmar.', 'warning')

    return redirect(url_for('servico.meus_servicos'))


@assinatura_bp.route('/pendente')
@login_required
def pendente():
    """Página de retorno para pagamento pendente (boleto, Pix aguardando, etc.)"""
    flash('Seu pagamento está pendente. O plano será ativado assim que for aprovado.', 'info')
    return redirect(url_for('servico.meus_servicos'))


@assinatura_bp.route('/erro')
@login_required
def erro():
    """Página de erro no pagamento"""
    flash('Ocorreu um erro ao processar seu pagamento. Tente novamente.', 'danger')
    return redirect(url_for('servico.planos_destaque'))


@assinatura_bp.route('/webhook', methods=['POST'])
def webhook():
    """Webhook do Mercado Pago"""

    data = request.get_json(silent=True) or {}

    # O Mercado Pago manda os dados no corpo (webhook) ou na query string (IPN)
    tipo = data.get('type') or request.args.get('type') or request.args.get('topic')
    corpo = data.get('data') if isinstance(data.get('data'), dict) else {}
    payment_id = corpo.get('id') or request.args.get('data.id') or request.args.get('id')

    if tipo == 'payment' and payment_id:
        # O mesmo webhook recebe pagamentos de planos e de contratos formais
        if confirmar_pagamento(payment_id) == 'invalido':
            from routes.contrato_formal_routes import confirmar_pagamento_contrato
            confirmar_pagamento_contrato(payment_id)

    return jsonify({'status': 'ok'}), 200


def confirmar_pagamento(payment_id, prestador_id_esperado=None):
    """Consulta o pagamento no Mercado Pago e ativa a assinatura se estiver aprovado.

    Retorna 'ativada', 'ja_processado', 'pendente' ou 'invalido'.
    """

    payment = verificar_pagamento(payment_id)
    if not payment:
        return 'invalido'

    status = payment.get('status')
    if status in ('pending', 'in_process'):
        return 'pendente'
    if status != 'approved':
        return 'invalido'

    # external_reference = prestador_<id>_<plano>
    parts = (payment.get('external_reference') or '').split('_')
    if len(parts) != 3 or parts[0] != 'prestador' or not parts[1].isdigit():
        return 'invalido'

    prestador_id = int(parts[1])
    plano = 'basico' if parts[2] == 'básico' else parts[2]  # links antigos usavam o nome com acento

    if plano not in PLANOS:
        return 'invalido'
    if prestador_id_esperado is not None and prestador_id != prestador_id_esperado:
        return 'invalido'
    if float(payment.get('transaction_amount') or 0) + 0.01 < PLANOS[plano]['valor']:
        return 'invalido'

    # Cada pagamento ativa a assinatura uma única vez
    if Assinatura.query.filter_by(pagamento_id=str(payment_id)).first():
        return 'ja_processado'

    ativar_assinatura(plano, prestador_id, pagamento_id=str(payment_id))
    return 'ativada'


def ativar_assinatura(plano, prestador_id, pagamento_id=None):
    """Ativa a assinatura para o prestador"""

    # Verificar se já existe assinatura ativa
    assinatura_existente = Assinatura.query.filter_by(
        prestador_id=prestador_id,
        status='ativa'
    ).first()

    if assinatura_existente:
        assinatura_existente.status = 'expirada'

    # Calcular datas
    data_inicio = datetime.utcnow()
    data_fim = data_inicio + timedelta(days=30)

    # Criar nova assinatura
    nova_assinatura = Assinatura(
        prestador_id=prestador_id,
        plano=plano,
        status='ativa',
        data_inicio=data_inicio,
        data_fim=data_fim,
        ultimo_pagamento=data_inicio,
        pagamento_id=pagamento_id
    )

    db.session.add(nova_assinatura)

    # Ativar destaques conforme plano
    limites = {'basico': 1, 'pro': 3}
    limite = limites.get(plano, 1)

    servicos = Servico.query.filter_by(prestador_id=prestador_id).limit(limite).all()
    for servico in servicos:
        servico.destaque = True
        servico.destaque_pago = True
        servico.destaque_data_fim = data_fim
        servico.plano_destaque = plano

    db.session.commit()

    return True


@assinatura_bp.route('/status')
@login_required
def status():
    """Verifica o status da assinatura do prestador"""

    assinatura = Assinatura.query.filter_by(
        prestador_id=current_user.id,
        status='ativa'
    ).first()

    return render_template('assinatura/status.html', assinatura=assinatura)


@assinatura_bp.route('/cancelar', methods=['POST'])
@login_required
def cancelar():
    """Cancela a assinatura do prestador"""

    assinatura = Assinatura.query.filter_by(
        prestador_id=current_user.id,
        status='ativa'
    ).first()

    if assinatura:
        assinatura.status = 'cancelada'

        # Desativar destaques
        servicos = Servico.query.filter_by(prestador_id=current_user.id).all()
        for servico in servicos:
            servico.destaque = False
            servico.destaque_pago = False

        db.session.commit()
        flash('Assinatura cancelada com sucesso!', 'success')
    else:
        flash('Nenhuma assinatura ativa encontrada.', 'warning')

    return redirect(url_for('main.dashboard'))
