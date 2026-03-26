from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Servico, Solicitacao
from datetime import datetime, timedelta
import base64

servico_bp = Blueprint('servico', __name__, url_prefix='/servico')

@servico_bp.route('/')
def lista():
    categoria = request.args.get('categoria')
    if categoria:
        servicos = Servico.query.filter_by(categoria=categoria).order_by(Servico.data_postagem.desc()).all()
    else:
        servicos = Servico.query.order_by(Servico.data_postagem.desc()).all()
    return render_template('lista_servicos.html', servicos=servicos, categoria=categoria)

@servico_bp.route('/<int:id>')
def detalhe(id):
    servico = Servico.query.get_or_404(id)
    return render_template('detalhe_servico.html', servico=servico)

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
            imagem_base64=imagem_base64
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

@servico_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    servico = Servico.query.get_or_404(id)
    
    if servico.prestador_id != current_user.id:
        flash('Você não tem permissão para editar este serviço', 'danger')
        return redirect(url_for('servico.detalhe', id=id))
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        categoria = request.form.get('categoria')
        preco = request.form.get('preco')
        destaque = request.form.get('destaque') == 'on'
        destaque_pago = request.form.get('destaque_pago') == 'on'
        
        if destaque_pago:
            if not servico.destaque_pago or (servico.destaque_data_fim and servico.destaque_data_fim < datetime.utcnow()):
                servico.destaque_pago = True
                servico.destaque_data_fim = datetime.utcnow() + timedelta(days=30)
                flash('Destaque Premium ativado! Seu serviço ficará em destaque por 30 dias.', 'success')
        else:
            servico.destaque_pago = False
            servico.destaque_data_fim = None
        
        remover_imagem = request.form.get('remover_imagem') == 'true'
        
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '':
                file_data = file.read()
                servico.imagem_base64 = base64.b64encode(file_data).decode('utf-8')
        elif remover_imagem:
            servico.imagem_base64 = None
        
        servico.titulo = titulo
        servico.descricao = descricao
        servico.categoria = categoria
        servico.preco = float(preco) if preco else None
        servico.destaque = destaque
        
        db.session.commit()
        
        flash('Serviço atualizado com sucesso!', 'success')
        return redirect(url_for('servico.detalhe', id=servico.id))
    
    return render_template('editar_servico.html', servico=servico, now=datetime.utcnow())

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
        mensagem=mensagem
    )
    
    db.session.add(solicitacao)
    db.session.commit()
    
    flash('Solicitação enviada com sucesso!', 'success')
    return redirect(url_for('servico.detalhe', id=servico_id))