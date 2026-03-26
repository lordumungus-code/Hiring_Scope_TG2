from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Servico, Solicitacao
import base64
from datetime import datetime

servico_bp = Blueprint('servico', __name__, url_prefix='/servico')

@servico_bp.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastro():
    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem cadastrar serviços', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        categoria = request.form.get('categoria')
        preco = request.form.get('preco')
        
        imagem_base64 = None
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '':
                file_data = file.read()
                imagem_base64 = base64.b64encode(file_data).decode('utf-8')
        
        novo_servico = Servico(
            prestador_id=current_user.id,
            titulo=titulo,
            descricao=descricao,
            categoria=categoria,
            preco=float(preco) if preco else None,
            imagem_base64=imagem_base64,
            destaque=False,
            data_postagem=datetime.utcnow()
        )
        
        db.session.add(novo_servico)
        db.session.commit()
        
        flash('Serviço cadastrado com sucesso!', 'success')
        return redirect(url_for('servico.meus_servicos'))
    
    return render_template('cadastro_servico.html')

@servico_bp.route('/meus-servicos')
@login_required
def meus_servicos():
    if current_user.tipo != 'prestador':
        flash('Acesso negado', 'danger')
        return redirect(url_for('main.index'))
    
    servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
    return render_template('meus_servicos.html', servicos=servicos)

@servico_bp.route('/')
@servico_bp.route('/lista')
def lista():
    """Lista todos os serviços disponíveis"""
    categoria = request.args.get('categoria', '')
    if categoria:
        servicos = Servico.query.filter_by(categoria=categoria).order_by(Servico.data_postagem.desc()).all()
    else:
        servicos = Servico.query.order_by(Servico.data_postagem.desc()).all()
    return render_template('lista_servicos.html', servicos=servicos, categoria=categoria)

# ROTA DE DETALHE - ESSA É A QUE ESTAVA FALTANDO
@servico_bp.route('/<int:id>')
def detalhe(id):
    """Detalhes de um serviço específico"""
    servico = Servico.query.get_or_404(id)
    return render_template('detalhe_servico.html', servico=servico)

@servico_bp.route('/solicitar/<int:servico_id>', methods=['POST'])
@login_required
def solicitar(servico_id):
    if current_user.tipo != 'cliente':
        flash('Apenas clientes podem solicitar serviços', 'danger')
        return redirect(url_for('servico.detalhe', id=servico_id))
    
    servico = Servico.query.get_or_404(servico_id)
    mensagem = request.form.get('mensagem')
    
    solicitacao_existente = Solicitacao.query.filter_by(
        cliente_id=current_user.id,
        servico_id=servico_id
    ).first()
    
    if solicitacao_existente:
        flash('Você já solicitou este serviço', 'warning')
        return redirect(url_for('servico.detalhe', id=servico_id))
    
    solicitacao = Solicitacao(
        cliente_id=current_user.id,
        servico_id=servico_id,
        mensagem=mensagem,
        status='pendente',
        data_solicitacao=datetime.utcnow()
    )
    
    db.session.add(solicitacao)
    db.session.commit()
    
    flash('Solicitação enviada com sucesso!', 'success')
    return redirect(url_for('servico.detalhe', id=servico_id))