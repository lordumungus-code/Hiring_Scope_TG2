from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import Contrato, Servico, Avaliacao, Usuario

contrato_bp = Blueprint('contrato', __name__, url_prefix='/contrato')

@contrato_bp.route('/solicitar/<int:servico_id>', methods=['POST'])
@login_required
def solicitar_servico(servico_id):
    """Cliente solicita um serviço"""
    if current_user.tipo != 'cliente':
        flash('Apenas clientes podem solicitar serviços', 'danger')
        return redirect(url_for('detalhe_servico', id=servico_id))
    
    servico = Servico.query.get_or_404(servico_id)
    mensagem = request.form.get('mensagem')
    
    # Verificar se já existe solicitação pendente
    contrato_existente = Contrato.query.filter_by(
        cliente_id=current_user.id,
        servico_id=servico_id,
        status='pendente'
    ).first()
    
    if contrato_existente:
        flash('Você já possui uma solicitação pendente para este serviço', 'warning')
        return redirect(url_for('detalhe_servico', id=servico_id))
    
    contrato = Contrato(
        cliente_id=current_user.id,
        prestador_id=servico.prestador_id,
        servico_id=servico_id,
        mensagem_cliente=mensagem,
        preco_acordado=servico.preco
    )
    
    db.session.add(contrato)
    db.session.commit()
    
    flash('✅ Solicitação enviada com sucesso! Aguarde a resposta do prestador.', 'success')
    return redirect(url_for('contrato.meus_contratos'))


@contrato_bp.route('/meus-contratos')
@login_required
def meus_contratos():
    """Lista os contratos do usuário"""
    if current_user.tipo == 'prestador':
        contratos = Contrato.query.filter_by(
            prestador_id=current_user.id
        ).order_by(Contrato.data_solicitacao.desc()).all()
    else:
        contratos = Contrato.query.filter_by(
            cliente_id=current_user.id
        ).order_by(Contrato.data_solicitacao.desc()).all()
    
    return render_template('contratos/lista.html', contratos=contratos)


@contrato_bp.route('/detalhe/<int:contrato_id>')
@login_required
def detalhe_contrato(contrato_id):
    """Detalhes de um contrato específico"""
    contrato = Contrato.query.get_or_404(contrato_id)
    
    # Verificar permissão
    if contrato.cliente_id != current_user.id and contrato.prestador_id != current_user.id:
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    # Verificar se já existe avaliação (usando cliente_id)
    avaliacao = None
    if contrato.status == 'concluido':
        avaliacao = Avaliacao.query.filter_by(
            contrato_id=contrato.id,
            cliente_id=current_user.id
        ).first()
    
    return render_template('contratos/detalhe.html', contrato=contrato, avaliacao=avaliacao)


@contrato_bp.route('/atualizar-status/<int:contrato_id>', methods=['POST'])
@login_required
def atualizar_status(contrato_id):
    """Atualiza o status do contrato"""
    contrato = Contrato.query.get_or_404(contrato_id)
    novo_status = request.form.get('status')
    
    # Verificar permissão
    if contrato.prestador_id != current_user.id and contrato.cliente_id != current_user.id:
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    # Validações de status
    if novo_status == 'aceito' and contrato.prestador_id == current_user.id:
        contrato.status = 'aceito'
        contrato.data_aceite = datetime.utcnow()
        flash('✅ Serviço aceito! Entre em contato com o cliente para combinar os detalhes.', 'success')
        
    elif novo_status == 'em_andamento' and contrato.prestador_id == current_user.id:
        contrato.status = 'em_andamento'
        contrato.data_inicio = datetime.utcnow()
        flash('🔄 Serviço iniciado!', 'success')
        
    elif novo_status == 'concluido' and contrato.prestador_id == current_user.id:
        contrato.status = 'concluido'
        contrato.data_conclusao = datetime.utcnow()
        flash('✅ Serviço concluído! O cliente agora pode avaliar o serviço.', 'success')
        
    elif novo_status == 'cancelado':
        contrato.status = 'cancelado'
        flash('❌ Serviço cancelado!', 'warning')
    
    db.session.commit()
    return redirect(url_for('contrato.detalhe_contrato', contrato_id=contrato.id))


@contrato_bp.route('/avaliar/<int:contrato_id>', methods=['GET', 'POST'])
@login_required
def avaliar_servico(contrato_id):
    """Avalia um serviço concluído"""
    contrato = Contrato.query.get_or_404(contrato_id)
    
    # Verificações
    if contrato.cliente_id != current_user.id:
        flash('Apenas o cliente pode avaliar o serviço', 'danger')
        return redirect(url_for('index'))
    
    if contrato.status != 'concluido':
        flash('Apenas serviços concluídos podem ser avaliados', 'warning')
        return redirect(url_for('contrato.detalhe_contrato', contrato_id=contrato.id))
    
    # Verificar se já avaliou
    avaliacao_existente = Avaliacao.query.filter_by(
        contrato_id=contrato.id,
        cliente_id=current_user.id
    ).first()
    
    if avaliacao_existente:
        flash('Você já avaliou este serviço', 'info')
        return redirect(url_for('contrato.detalhe_contrato', contrato_id=contrato.id))
    
    if request.method == 'POST':
        nota = int(request.form.get('nota', 0))
        comentario = request.form.get('comentario', '').strip()
        qualidade = int(request.form.get('qualidade', 0))
        pontualidade = int(request.form.get('pontualidade', 0))
        comunicacao = int(request.form.get('comunicacao', 0))
        preco = int(request.form.get('preco', 0))
        
        if nota < 1 or nota > 5:
            flash('A nota deve ser entre 1 e 5 estrelas', 'danger')
            return redirect(url_for('contrato.avaliar_servico', contrato_id=contrato.id))
        
        avaliacao = Avaliacao(
            contrato_id=contrato.id,
            cliente_id=current_user.id,
            prestador_id=contrato.prestador_id,
            servico_id=contrato.servico_id,
            nota=nota,
            comentario=comentario,
            qualidade=qualidade if qualidade > 0 else None,
            pontualidade=pontualidade if pontualidade > 0 else None,
            comunicacao=comunicacao if comunicacao > 0 else None,
            preco_justo=preco if preco > 0 else None
        )
        
        db.session.add(avaliacao)
        db.session.commit()
        
        flash('⭐ Avaliação enviada com sucesso! Obrigado pelo feedback.', 'success')
        return redirect(url_for('contrato.detalhe_contrato', contrato_id=contrato.id))
    
    return render_template('contratos/avaliar.html', contrato=contrato)


@contrato_bp.route('/editar-avaliacao/<int:avaliacao_id>', methods=['GET', 'POST'])
@login_required
def editar_avaliacao(avaliacao_id):
    """Edita uma avaliação existente"""
    avaliacao = Avaliacao.query.get_or_404(avaliacao_id)
    
    if avaliacao.cliente_id != current_user.id:
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    if not avaliacao.pode_editar(current_user.id):
        flash('Não é mais possível editar esta avaliação (apenas 7 dias após a criação)', 'warning')
        return redirect(url_for('contrato.detalhe_contrato', contrato_id=avaliacao.contrato_id))
    
    if request.method == 'POST':
        nota = int(request.form.get('nota', 0))
        comentario = request.form.get('comentario', '').strip()
        
        avaliacao.nota = nota
        avaliacao.comentario = comentario
        avaliacao.editado = True
        avaliacao.data_edicao = datetime.utcnow()
        
        db.session.commit()
        flash('⭐ Avaliação atualizada com sucesso!', 'success')
        return redirect(url_for('contrato.detalhe_contrato', contrato_id=avaliacao.contrato_id))
    
    return render_template('contratos/editar_avaliacao.html', avaliacao=avaliacao)