from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from extensions import db
from models import Assinatura, Servico
from services.mercado_pago_service import criar_link_pagamento, verificar_pagamento

assinatura_bp = Blueprint('assinatura', __name__, url_prefix='/assinatura')


@assinatura_bp.route('/checkout/<plano>')
@login_required
def checkout(plano):
    """Página de checkout para o plano escolhido"""
    
    print(f"🔍 Checkout chamado para plano: {plano}")
    
    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem contratar planos', 'danger')
        return redirect(url_for('main.index'))
    
    planos_config = {
        'basico': {'nome': 'Básico', 'valor': 1},
        'pro': {'nome': 'Pro', 'valor': 29.90}
    }
    
    if plano not in planos_config:
        flash('Plano inválido', 'danger')
        return redirect(url_for('servico.planos_destaque'))
    
    config = planos_config[plano]
    
    # Salvar plano na sessão
    session['plano_contratado'] = plano
    
    # Criar link de pagamento
    result = criar_link_pagamento(
        plano_nome=config['nome'],
        plano_valor=config['valor'],
        prestador_id=current_user.id,
        prestador_email=current_user.email,
        prestador_nome=current_user.nome
    )
    
    print(f"📦 Resultado: {result}")
    
    if result and result.get('success') and result.get('url'):
        print(f"🚀 Redirecionando para: {result['url']}")
        return redirect(result['url'])
    else:
        flash('Erro ao criar link de pagamento. Tente novamente.', 'danger')
        return redirect(url_for('servico.planos_destaque'))


@assinatura_bp.route('/simular')
@login_required
def simular_pagamento():
    """Simula um pagamento (modo de teste)"""
    
    plano = request.args.get('plano')
    prestador_id = request.args.get('prestador')
    
    if plano and prestador_id and int(prestador_id) == current_user.id:
        return ativar_assinatura(plano, current_user.id)
    
    flash('Erro na simulação', 'danger')
    return redirect(url_for('servico.planos_destaque'))


@assinatura_bp.route('/sucesso')
@login_required
def sucesso():
    """Página de sucesso após pagamento"""
    
    plano = session.pop('plano_contratado', None)
    
    if plano:
        ativar_assinatura(plano, current_user.id)
        flash('✅ Assinatura ativada com sucesso! Seus serviços estão em destaque.', 'success')
    
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
    
    data = request.get_json()
    
    if data.get('type') == 'payment':
        payment_id = data.get('data', {}).get('id')
        
        if payment_id:
            payment = verificar_pagamento(payment_id)
            
            if payment and payment.get('status') == 'approved':
                external_ref = payment.get('external_reference', '')
                parts = external_ref.split('_')
                
                if len(parts) >= 3:
                    prestador_id = int(parts[1])
                    plano = parts[2]
                    ativar_assinatura(plano, prestador_id)
    
    return jsonify({'status': 'ok'}), 200


def ativar_assinatura(plano, prestador_id):
    """Ativa a assinatura para o prestador"""
    
    from models import Assinatura, Servico
    
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
        ultimo_pagamento=data_inicio
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


@assinatura_bp.route('/cancelar')
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