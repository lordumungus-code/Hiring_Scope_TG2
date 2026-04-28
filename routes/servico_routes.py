from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Servico, Usuario, Solicitacao
from sqlalchemy import or_, func
import base64
from datetime import datetime, timedelta

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
        tipo_preco = request.form.get('tipo_preco', 'fixo')
        preco = request.form.get('preco')
        destaque = request.form.get('destaque') == 'on'
        
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
            tipo_preco=tipo_preco,
            preco=float(preco) if preco and tipo_preco != 'consulta' else None,
            imagem_base64=imagem_base64,
            destaque=destaque,
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
    categoria = request.args.get('categoria')
    q = request.args.get('q', '').strip()
    prestador_id = request.args.get('prestador')
    
    query = Servico.query
    if categoria:
        query = query.filter_by(categoria=categoria)
    if prestador_id:
        query = query.filter_by(prestador_id=prestador_id)
    if q:
        query = query.join(Usuario).filter(
            or_(Servico.titulo.ilike(f'%{q}%'),
                Servico.descricao.ilike(f'%{q}%'),
                Usuario.nome.ilike(f'%{q}%'))
        )
    
    servicos = query.order_by(Servico.data_postagem.desc()).all()
    categorias = db.session.query(Servico.categoria, func.count(Servico.id).label('total')).group_by(Servico.categoria).all()
    
    return render_template('lista_servicos.html',
                         servicos=servicos, categoria=categoria,
                         categorias=categorias, termo_busca=q)


@servico_bp.route('/<int:id>')
def detalhe(id):
    servico = Servico.query.get_or_404(id)
    return render_template('detalhe_servico.html', servico=servico)


@servico_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    servico = Servico.query.get_or_404(id)
    
    if servico.prestador_id != current_user.id:
        flash('Você não tem permissão para editar este serviço', 'danger')
        return redirect(url_for('servico.detalhe', id=id))
    
    if request.method == 'POST':
        servico.titulo = request.form.get('titulo')
        servico.descricao = request.form.get('descricao')
        servico.categoria = request.form.get('categoria')
        servico.tipo_preco = request.form.get('tipo_preco', 'fixo')
        
        preco = request.form.get('preco')
        if servico.tipo_preco != 'consulta' and preco:
            servico.preco = float(preco)
        else:
            servico.preco = None
        
        servico.destaque = request.form.get('destaque') == 'on'
        
        destaque_pago = request.form.get('destaque_pago') == 'on'
        if destaque_pago and not servico.destaque_pago:
            servico.destaque_pago = True
            servico.destaque_data_fim = datetime.utcnow() + timedelta(days=30)
            servico.destaque = True
            flash('Destaque Premium ativado! Seu serviço ficará em destaque por 30 dias.', 'success')
        elif not destaque_pago:
            servico.destaque_pago = False
            servico.destaque_data_fim = None
        
        if request.form.get('remover_imagem') == 'true':
            servico.imagem_base64 = None
        
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '':
                file_data = file.read()
                servico.imagem_base64 = base64.b64encode(file_data).decode('utf-8')
        
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
    
    solicitacao_existente = Solicitacao.query.filter_by(
        cliente_id=current_user.id, servico_id=servico_id
    ).first()
    
    if solicitacao_existente:
        flash('Você já solicitou este serviço', 'warning')
        return redirect(url_for('servico.detalhe', id=servico_id))
    
    solicitacao = Solicitacao(
        cliente_id=current_user.id, servico_id=servico_id,
        mensagem=request.form.get('mensagem'), data_solicitacao=datetime.utcnow()
    )
    db.session.add(solicitacao)
    db.session.commit()
    
    flash('Solicitação enviada com sucesso!', 'success')
    return redirect(url_for('servico.detalhe', id=servico_id))


# ============================================
# ROTAS DE PLANOS DE DESTAQUE
# ============================================

@servico_bp.route('/planos')
@login_required
def planos_destaque():
    """Página de planos de destaque para prestadores"""
    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem acessar os planos de destaque', 'warning')
        return redirect(url_for('main.index'))
    
    return render_template('servico/planos_destaque.html')


# ============================================
# REDIRECIONAMENTO PARA ASSINATURA (APENAS UMA VEZ!)
# ============================================

@servico_bp.route('/assinar/<plano>')
@login_required
def assinar_plano(plano):
    """Redireciona para o checkout da assinatura no blueprint assinatura"""
    return redirect(url_for('assinatura.checkout', plano=plano))