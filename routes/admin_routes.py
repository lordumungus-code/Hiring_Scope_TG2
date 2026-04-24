from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Usuario, Servico, Avaliacao, Contrato, Solicitacao
from functools import wraps
from datetime import datetime, timedelta

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

# ============================================
# DASHBOARD ADMIN
# ============================================

@admin_bp.route('/')
@admin_required
def dashboard():
    """Dashboard do administrador"""
    # Estatísticas
    total_usuarios = Usuario.query.count()
    total_prestadores = Usuario.query.filter_by(tipo='prestador').count()
    total_clientes = Usuario.query.filter_by(tipo='cliente').count()
    total_admins = Usuario.query.filter_by(is_admin=True).count()
    
    total_servicos = Servico.query.count()
    total_contratos = Contrato.query.count()
    total_avaliacoes = Avaliacao.query.count()
    
    # Contratos por status
    contratos_pendentes = Contrato.query.filter_by(status='pendente').count()
    contratos_andamento = Contrato.query.filter_by(status='em_andamento').count()
    contratos_concluidos = Contrato.query.filter_by(status='concluido').count()
    
    # Usuários recentes
    usuarios_recentes = Usuario.query.order_by(Usuario.data_cadastro.desc()).limit(10).all()
    
    # Serviços recentes
    servicos_recentes = Servico.query.order_by(Servico.data_postagem.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         total_usuarios=total_usuarios,
                         total_prestadores=total_prestadores,
                         total_clientes=total_clientes,
                         total_admins=total_admins,
                         total_servicos=total_servicos,
                         total_contratos=total_contratos,
                         total_avaliacoes=total_avaliacoes,
                         contratos_pendentes=contratos_pendentes,
                         contratos_andamento=contratos_andamento,
                         contratos_concluidos=contratos_concluidos,
                         usuarios_recentes=usuarios_recentes,
                         servicos_recentes=servicos_recentes)

# ============================================
# GERENCIAR USUÁRIOS
# ============================================

@admin_bp.route('/usuarios')
@admin_required
def usuarios():
    """Lista todos os usuários"""
    search = request.args.get('search', '')
    tipo = request.args.get('tipo', '')
    
    query = Usuario.query
    
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
    
    # Estatísticas do usuário
    if usuario.tipo == 'prestador':
        total_servicos = Servico.query.filter_by(prestador_id=usuario.id).count()
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

@admin_bp.route('/usuarios/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    """Bane um usuário (bloqueia acesso)"""
    usuario = Usuario.query.get_or_404(user_id)
    
    if usuario.id == current_user.id:
        flash('Você não pode banir a si mesmo.', 'danger')
        return redirect(url_for('admin.usuario_detalhe', user_id=user_id))
    
    # Adicionar campo 'is_banned' no modelo Usuario se quiser
    # Por enquanto, vamos apenas definir um status
    usuario.is_banned = getattr(usuario, 'is_banned', False)
    usuario.is_banned = not usuario.is_banned
    
    db.session.commit()
    
    status = 'banido' if usuario.is_banned else 'desbanido'
    flash(f'Usuário {status} com sucesso.', 'success')
    return redirect(url_for('admin.usuario_detalhe', user_id=user_id))

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
    
    query = Servico.query
    
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
    categorias = db.session.query(Servico.categoria).distinct().all()
    
    return render_template('admin/servicos.html', servicos=servicos, search=search, categoria=categoria, destaque=destaque, categorias=categorias)

@admin_bp.route('/servicos/<int:servico_id>/delete', methods=['POST'])
@admin_required
def delete_servico(servico_id):
    """Remove um serviço"""
    servico = Servico.query.get_or_404(servico_id)
    titulo = servico.titulo
    
    db.session.delete(servico)
    db.session.commit()
    
    flash(f'Serviço "{titulo}" removido com sucesso.', 'success')
    return redirect(url_for('admin.servicos'))

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
    from sqlalchemy import func
    
    # Contagem por período
    hoje = datetime.utcnow()
    inicio_semana = hoje - timedelta(days=7)
    inicio_mes = hoje - timedelta(days=30)
    
    # Usuários por mês
    usuarios_por_mes = db.session.query(
        func.strftime('%Y-%m', Usuario.data_cadastro).label('mes'),
        func.count(Usuario.id).label('total')
    ).group_by('mes').order_by('mes').limit(12).all()
    
    # Serviços por categoria
    servicos_por_categoria = db.session.query(
        Servico.categoria,
        func.count(Servico.id).label('total')
    ).group_by(Servico.categoria).all()
    
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