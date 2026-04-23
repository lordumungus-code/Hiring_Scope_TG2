from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import base64
import os
import secrets

from routes.contrato_routes import contrato_bp
# Importa as extensões
from extensions import db, login_manager, socketio

# Importa os modelos
from models import Usuario, Servico, Solicitacao, Mensagem, Avaliacao, Favorito

# Importa os blueprints
from routes.chat_routes import chat_bp

# Importa Firebase
from firebase_admin import auth as admin_auth
from config.firebase_config import firebase_auth

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-simples-mas-segura')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///prestadores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_PARTITIONED'] = False

# Inicializa extensões com o app
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

# Inicializa SocketIO com o app
socketio.init_app(app, cors_allowed_origins="*")

# Registra os blueprints
app.register_blueprint(chat_bp)

app.register_blueprint(contrato_bp)

# Configurações Firebase para os templates
app.config['FIREBASE_API_KEY'] = os.environ.get('FIREBASE_API_KEY')
app.config['FIREBASE_AUTH_DOMAIN'] = os.environ.get('FIREBASE_AUTH_DOMAIN')
app.config['FIREBASE_PROJECT_ID'] = os.environ.get('FIREBASE_PROJECT_ID')
app.config['FIREBASE_STORAGE_BUCKET'] = os.environ.get('FIREBASE_STORAGE_BUCKET')
app.config['FIREBASE_MESSAGING_SENDER_ID'] = os.environ.get('FIREBASE_MESSAGING_SENDER_ID')
app.config['FIREBASE_APP_ID'] = os.environ.get('FIREBASE_APP_ID')

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Criar tabelas
with app.app_context():
    db.create_all()
    # Criar um prestador de exemplo se não existir
    if Usuario.query.filter_by(email='prestador@email.com').first() is None:
        prestador = Usuario(
            nome='Prestador Exemplo',
            email='prestador@email.com',
            telefone='11999999999',
            tipo='prestador'
        )
        prestador.set_password('123456')
        db.session.add(prestador)
        db.session.commit()
        
        # Criar serviços em destaque
        servicos_destaque = [
            Servico(
                prestador_id=prestador.id,
                titulo='Consultoria em Marketing Digital',
                descricao='Ajuda com estratégias de marketing para seu negócio',
                categoria='Marketing',
                preco=150.00,
                destaque=True
            ),
            Servico(
                prestador_id=prestador.id,
                titulo='Desenvolvimento de Sites',
                descricao='Criação de sites profissionais e responsivos',
                categoria='Tecnologia',
                preco=2000.00,
                destaque=True
            ),
            Servico(
                prestador_id=prestador.id,
                titulo='Aulas Particulares de Inglês',
                descricao='Aulas online para todos os níveis',
                categoria='Educação',
                preco=50.00,
                destaque=True
            )
        ]
        db.session.add_all(servicos_destaque)
        db.session.commit()
        print("✅ Dados de exemplo criados!")

# ============================================
# ROTAS PRINCIPAIS
# ============================================

@app.route('/')
def index():
    from models import Servico, Usuario, Avaliacao, Contrato
    from sqlalchemy import func, desc
    
    servicos_destaque = Servico.query.filter_by(destaque=True).order_by(Servico.data_postagem.desc()).limit(6).all()
    servicos_recentes = Servico.query.order_by(Servico.data_postagem.desc()).limit(8).all()
    
    # ============================================
    # DEPOIMENTOS REAIS (AVALIAÇÕES NOTA 4 OU 5)
    # ============================================
    depoimentos = Avaliacao.query.filter(
        Avaliacao.nota >= 4,  # Apenas notas 4 ou 5
        Avaliacao.comentario.isnot(None),  # Tem comentário
        Avaliacao.comentario != ''  # Comentário não vazio
    ).order_by(desc(Avaliacao.data_avaliacao)).limit(6).all()
    
    # Se não houver avaliações reais, mostrar depoimentos padrão
    if not depoimentos:
        # Depoimentos padrão (fallback)
        depoimentos = [
            {'nome': 'Maria Silva', 'texto': 'Excelente plataforma! Encontrei um profissional qualificado em poucos minutos. Recomendo!', 'nota': 5, 'tipo': 'Cliente'},
            {'nome': 'João Santos', 'texto': 'Como prestador, consegui vários clientes através da plataforma. Ótimo sistema de chat!', 'nota': 5, 'tipo': 'Prestador'},
            {'nome': 'Ana Oliveira', 'texto': 'Interface intuitiva e fácil de usar. O suporte é rápido e eficiente. Estou muito satisfeito!', 'nota': 4, 'tipo': 'Cliente'}
        ]
    else:
        # Converter avaliações para formato do template
        depoimentos = [{
            'nome': d.cliente.nome if d.cliente else 'Cliente',
            'texto': d.comentario,
            'nota': d.nota,
            'tipo': 'Cliente',
            'data': d.data_avaliacao.strftime('%d/%m/%Y')
        } for d in depoimentos]
    
    # ============================================
    # TOP 10 PRESTADORES COM MELHORES AVALIAÇÕES
    # ============================================
    prestadores_com_avaliacoes = Usuario.query.filter(
        Usuario.tipo == 'prestador',
        Usuario.avaliacoes_recebidas.any()
    ).all()
    
    top_prestadores = []
    for prestador in prestadores_com_avaliacoes:
        media = prestador.media_avaliacoes()
        total = prestador.total_avaliacoes()
        if media > 0:
            top_prestadores.append({
                'prestador': prestador,
                'media': media,
                'total_avaliacoes': total,
                'servicos_count': len(prestador.servicos_oferecidos)
            })
    
    top_prestadores = sorted(top_prestadores, key=lambda x: x['media'], reverse=True)[:10]
    
    # Estatísticas
    total_usuarios = Usuario.query.count()
    total_servicos = Servico.query.count()
    total_avaliacoes = Avaliacao.query.count()
    
    # Serviços concluídos (via contratos)
    servicos_concluidos = Contrato.query.filter_by(status='concluido').count() if 'Contrato' in locals() else 0
    
    return render_template('index.html', 
                         servicos_destaque=servicos_destaque,
                         servicos_recentes=servicos_recentes,
                         top_prestadores=top_prestadores,
                         depoimentos=depoimentos,
                         total_usuarios=total_usuarios,
                         total_servicos=total_servicos,
                         total_avaliacoes=total_avaliacoes,
                         servicos_concluidos=servicos_concluidos)
# ============================================
# ROTAS DE AUTENTICAÇÃO COM FIREBASE
# ============================================

@app.route('/auth/firebase/google')
def auth_firebase_google():
    """Redireciona para página de login Firebase"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('firebase_login.html')

@app.route('/auth/firebase/callback', methods=['POST'])
def auth_firebase_callback():
    """Callback após login Google via Firebase"""
    try:
        data = request.get_json()
        id_token = data.get('idToken')
        
        if not id_token:
            return jsonify({'error': 'Token não fornecido'}), 400
        
        decoded_token = admin_auth.verify_id_token(id_token)
        
        email = decoded_token.get('email')
        nome = decoded_token.get('name', email.split('@')[0] if email else 'Usuário')
        firebase_uid = decoded_token.get('uid')
        foto_url = decoded_token.get('picture')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if not usuario:
            session['firebase_user'] = {
                'email': email,
                'nome': nome,
                'firebase_uid': firebase_uid,
                'foto_url': foto_url
            }
            return jsonify({'redirect': '/cadastro/firebase'}), 200
        
        if foto_url and not usuario.foto_url:
            usuario.foto_url = foto_url
            db.session.commit()
        
        login_user(usuario)
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Erro no callback Firebase: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/cadastro/firebase', methods=['GET', 'POST'])
def cadastro_firebase():
    """Completa cadastro do usuário Firebase"""
    firebase_user = session.get('firebase_user')
    
    if not firebase_user:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        telefone = request.form.get('telefone', '')
        
        novo_usuario = Usuario(
            nome=firebase_user['nome'],
            email=firebase_user['email'],
            telefone=telefone,
            tipo=tipo,
            foto_url=firebase_user.get('foto_url')
        )
        senha_aleatoria = secrets.token_urlsafe(16)
        novo_usuario.set_password(senha_aleatoria)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        session.pop('firebase_user', None)
        login_user(novo_usuario)
        flash(f'Cadastro realizado! Bem-vindo, {novo_usuario.nome}!', 'success')
        return redirect(url_for('index'))
    
    return render_template('cadastro_firebase.html', usuario=firebase_user)

# ============================================
# ROTAS DE AUTENTICAÇÃO TRADICIONAL
# ============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.check_password(senha):
            login_user(usuario)
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Email ou senha inválidos', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema', 'info')
    return redirect(url_for('index'))

# ============================================
# CADASTRO DE USUÁRIO TRADICIONAL
# ============================================

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        telefone = request.form.get('telefone')
        tipo = request.form.get('tipo')
        
        if Usuario.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'danger')
            return redirect(url_for('cadastro'))
        
        # Processa a foto de perfil
        foto_perfil = None
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                # Lê o arquivo e converte para Base64
                file_data = file.read()
                foto_perfil = base64.b64encode(file_data).decode('utf-8')
        
        novo_usuario = Usuario(
            nome=nome,
            email=email,
            telefone=telefone,
            tipo=tipo,
            foto_perfil=foto_perfil  # Salva como Base64
        )
        novo_usuario.set_password(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('cadastro_usuario.html')

# ============================================
# DASHBOARD
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    from models import Contrato
    
    if current_user.tipo == 'prestador':
        servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
        contratos = Contrato.query.filter_by(prestador_id=current_user.id).order_by(Contrato.data_solicitacao.desc()).all()
        
        contratos_pendentes = [c for c in contratos if c.status == 'pendente']
        contratos_andamento = [c for c in contratos if c.status in ['aceito', 'em_andamento']]
        contratos_concluidos = [c for c in contratos if c.status == 'concluido']
        media_avaliacoes = current_user.media_avaliacoes()
        
        return render_template('dashboard_prestador.html',
                             servicos=servicos,
                             contratos=contratos,
                             contratos_pendentes=contratos_pendentes,
                             contratos_andamento=contratos_andamento,
                             contratos_concluidos=contratos_concluidos,
                             media_avaliacoes=media_avaliacoes)
    else:
        contratos = Contrato.query.filter_by(cliente_id=current_user.id).order_by(Contrato.data_solicitacao.desc()).all()
        contratos_pendentes = [c for c in contratos if c.status == 'pendente']
        contratos_andamento = [c for c in contratos if c.status in ['aceito', 'em_andamento']]
        contratos_concluidos = [c for c in contratos if c.status == 'concluido']
        
        return render_template('dashboard_cliente.html',
                             contratos=contratos,
                             contratos_pendentes=contratos_pendentes,
                             contratos_andamento=contratos_andamento,
                             contratos_concluidos=contratos_concluidos,
                             total_contratos=len(contratos))
# ============================================
# ROTAS DE SERVIÇOS
# ============================================

@app.route('/cadastro/servico', methods=['GET', 'POST'])
@login_required
def cadastro_servico():
    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem cadastrar serviços', 'danger')
        return redirect(url_for('index'))
    
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
        return redirect(url_for('meus_servicos'))
    
    return render_template('cadastro_servico.html')

@app.route('/meus-servicos')
@login_required
def meus_servicos():
    if current_user.tipo != 'prestador':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
    return render_template('meus_servicos.html', servicos=servicos)

@app.route('/servicos')
def lista_servicos():
    from models import Servico, Usuario
    from sqlalchemy import or_, func
    
    # Parâmetros de busca
    categoria = request.args.get('categoria')
    q = request.args.get('q', '').strip()  # Termo de busca
    prestador_id = request.args.get('prestador')
    
    # Query base
    query = Servico.query
    
    # Filtro por categoria
    if categoria:
        query = query.filter_by(categoria=categoria)
    
    # Filtro por prestador específico
    if prestador_id:
        query = query.filter_by(prestador_id=prestador_id)
    
    # ============================================
    # BUSCA AVANÇADA: título, descrição ou nome do prestador
    # ============================================
    if q:
        # Busca por título OU descrição OU nome do prestador
        query = query.join(Usuario).filter(
            or_(
                Servico.titulo.ilike(f'%{q}%'),
                Servico.descricao.ilike(f'%{q}%'),
                Usuario.nome.ilike(f'%{q}%')  # Nome do prestador
            )
        )
    
    # Ordenar por mais recentes primeiro
    servicos = query.order_by(Servico.data_postagem.desc()).all()
    
    # Buscar categorias distintas para o filtro
    categorias = db.session.query(Servico.categoria, func.count(Servico.id).label('total')).group_by(Servico.categoria).all()
    
    # Salvar termo de busca para exibir no template
    termo_busca = q
    
    return render_template('lista_servicos.html', 
                         servicos=servicos, 
                         categoria=categoria, 
                         categorias=categorias,
                         termo_busca=termo_busca)

# ============================================
# EDIÇÃO DE SERVIÇOS
# ============================================

@app.route('/servico/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_servico(id):
    servico = Servico.query.get_or_404(id)
    
    if servico.prestador_id != current_user.id:
        flash('Você não tem permissão para editar este serviço', 'danger')
        return redirect(url_for('detalhe_servico', id=id))
    
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
        return redirect(url_for('detalhe_servico', id=servico.id))
    
    return render_template('editar_servico.html', servico=servico, now=datetime.utcnow())

# ============================================
# SOLICITAÇÕES DE SERVIÇOS
# ============================================

@app.route('/solicitar/<int:servico_id>', methods=['POST'])
@login_required
def solicitar_servico(servico_id):
    if current_user.tipo != 'cliente':
        flash('Apenas clientes podem solicitar serviços', 'danger')
        return redirect(url_for('detalhe_servico', id=servico_id))
    
    servico = Servico.query.get_or_404(servico_id)
    mensagem = request.form.get('mensagem')
    
    solicitacao_existente = Solicitacao.query.filter_by(
        cliente_id=current_user.id,
        servico_id=servico_id
    ).first()
    
    if solicitacao_existente:
        flash('Você já solicitou este serviço', 'warning')
        return redirect(url_for('detalhe_servico', id=servico_id))
    
    solicitacao = Solicitacao(
        cliente_id=current_user.id,
        servico_id=servico_id,
        mensagem=mensagem
    )
    
    db.session.add(solicitacao)
    db.session.commit()
    
    flash('Solicitação enviada com sucesso!', 'success')
    return redirect(url_for('detalhe_servico', id=servico_id))

# ============================================
# PERFIL DO USUÁRIO
# ============================================

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    """Página de perfil do usuário"""
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        descricao = request.form.get('descricao')
        
        if email != current_user.email:
            email_existente = Usuario.query.filter_by(email=email).first()
            if email_existente:
                flash('Este e-mail já está em uso por outra conta.', 'danger')
                return redirect(url_for('perfil'))
        
        # Processa a foto de perfil
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                file_data = file.read()
                # Limita o tamanho da imagem
                if len(file_data) > 5 * 1024 * 1024:
                    flash('A imagem deve ter no máximo 5MB.', 'danger')
                    return redirect(url_for('perfil'))
                foto_base64 = base64.b64encode(file_data).decode('utf-8')
                current_user.foto_perfil = foto_base64
        
        current_user.nome = nome
        current_user.email = email
        current_user.telefone = telefone
        current_user.descricao = descricao
        
        db.session.commit()
        
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('perfil'))
    
    return render_template('perfil.html', usuario=current_user)

@app.route('/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
    """Altera a senha do usuário"""
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    confirmar_senha = request.form.get('confirmar_senha')
    
    if not current_user.check_password(senha_atual):
        flash('Senha atual incorreta.', 'danger')
        return redirect(url_for('perfil'))
    
    if nova_senha != confirmar_senha:
        flash('As novas senhas não coincidem.', 'danger')
        return redirect(url_for('perfil'))
    
    current_user.set_password(nova_senha)
    db.session.commit()
    
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('perfil'))

# ============================================
# TESTE FIREBASE
# ============================================

@app.route('/test-firebase')
def test_firebase():
    """Testa se o Firebase está configurado"""
    try:
        from firebase_admin import auth as admin_auth
        return "✅ Firebase Admin SDK está funcionando!"
    except Exception as e:
        return f"❌ Erro: {e}"


# ============================================
# ROTAS ADICIONAIS PARA SISTEMA DE CONTRATOS
# ============================================

@app.route('/meus-contratos')
@login_required
def meus_contratos():
    """Redireciona para a página de contratos do blueprint"""
    return redirect(url_for('contrato.meus_contratos'))

@app.route('/avaliar/<int:contrato_id>', methods=['GET', 'POST'])
@login_required
def avaliar_contrato(contrato_id):
    """Redireciona para avaliação do blueprint"""
    return redirect(url_for('contrato.avaliar_servico', contrato_id=contrato_id))

# ============================================
# CONTEXT PROCESSOR - Variáveis globais para templates
# ============================================

@app.context_processor
def utility_processor():
    """Adiciona funções utilitárias a todos os templates"""
    from models import Contrato, Avaliacao
    
    def get_icone_categoria(categoria):
        """Retorna o ícone Font Awesome para cada categoria"""
        icons = {
            'Tecnologia': 'fa-laptop-code',
            'Construção': 'fa-hard-hat',
            'Design': 'fa-paintbrush',
            'Educação': 'fa-chalkboard-user',
            'Saúde': 'fa-heartbeat',
            'Marketing': 'fa-chart-line',
            'Limpeza': 'fa-broom',
            'Segurança': 'fa-shield-alt',
            'Jardinagem': 'fa-leaf',
            'Fotografia': 'fa-camera',
            'Tradução': 'fa-language',
            'Consultoria': 'fa-briefcase'
        }
        return icons.get(categoria, 'fa-tools')
    
    def get_cor_categoria(categoria):
        """Retorna a cor Bootstrap para cada categoria"""
        colors = {
            'Tecnologia': 'primary',
            'Construção': 'warning',
            'Design': 'danger',
            'Educação': 'success',
            'Saúde': 'info',
            'Marketing': 'secondary'
        }
        return colors.get(categoria, 'dark')
    
    return {
        'get_icone_categoria': get_icone_categoria,
        'get_cor_categoria': get_cor_categoria,
        'now': datetime.utcnow()
    }

# ============================================
# ROTAS PARA DASHBOARD COM CONTRATOS
# ============================================

@app.route('/dashboard/prestador')
@login_required
def dashboard_prestador_completo():
    """Dashboard completo para prestador com contratos"""
    if current_user.tipo != 'prestador':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    from models import Contrato
    
    servicos = Servico.query.filter_by(prestador_id=current_user.id).all()
    contratos = Contrato.query.filter_by(prestador_id=current_user.id).order_by(Contrato.data_solicitacao.desc()).all()
    
    # Estatísticas
    total_servicos = len(servicos)
    total_contratos = len(contratos)
    contratos_pendentes = [c for c in contratos if c.status == 'pendente']
    contratos_andamento = [c for c in contratos if c.status in ['aceito', 'em_andamento']]
    contratos_concluidos = [c for c in contratos if c.status == 'concluido']
    media_avaliacoes = current_user.media_avaliacoes()
    
    return render_template('dashboard_prestador.html',
                         servicos=servicos,
                         contratos=contratos,
                         contratos_pendentes=contratos_pendentes,
                         contratos_andamento=contratos_andamento,
                         contratos_concluidos=contratos_concluidos,
                         total_servicos=total_servicos,
                         total_contratos=total_contratos,
                         media_avaliacoes=media_avaliacoes)

@app.route('/dashboard/cliente')
@login_required
def dashboard_cliente_completo():
    """Dashboard completo para cliente com contratos"""
    if current_user.tipo != 'cliente':
        flash('Acesso negado', 'danger')
        return redirect(url_for('index'))
    
    from models import Contrato
    
    contratos = Contrato.query.filter_by(cliente_id=current_user.id).order_by(Contrato.data_solicitacao.desc()).all()
    
    # Estatísticas
    contratos_pendentes = [c for c in contratos if c.status == 'pendente']
    contratos_andamento = [c for c in contratos if c.status in ['aceito', 'em_andamento']]
    contratos_concluidos = [c for c in contratos if c.status == 'concluido']
    total_contratos = len(contratos)
    
    return render_template('dashboard_cliente.html',
                         contratos=contratos,
                         contratos_pendentes=contratos_pendentes,
                         contratos_andamento=contratos_andamento,
                         contratos_concluidos=contratos_concluidos,
                         total_contratos=total_contratos)

@app.route('/prestadores')
def lista_prestadores():
    """Lista todos os prestadores com ranking"""
    from models import Usuario, Contrato
    from sqlalchemy import func, desc
    
    prestadores = Usuario.query.filter_by(tipo='prestador').all()
    
    # Calcular média para cada prestador
    ranking = []
    for p in prestadores:
        # Contar contratos concluídos
        contratos_concluidos = Contrato.query.filter_by(
            prestador_id=p.id,
            status='concluido'
        ).count()
        
        ranking.append({
            'prestador': p,
            'media': p.media_avaliacoes(),
            'total_avaliacoes': p.total_avaliacoes(),
            'total_servicos': len(p.servicos_oferecidos),
            'total_concluidos': contratos_concluidos
        })
    
    # Ordenar por média (maior primeiro)
    ranking = sorted(ranking, key=lambda x: x['media'], reverse=True)
    
    return render_template('prestadores.html', ranking=ranking)

@app.route('/perfil/<int:prestador_id>')
def perfil_prestador(prestador_id):
    """Página de perfil do prestador"""
    from models import Usuario
    
    prestador = Usuario.query.get_or_404(prestador_id)
    
    # Verificar se é um prestador
    if prestador.tipo != 'prestador':
        flash('Usuário não é um prestador de serviços', 'warning')
        return redirect(url_for('index'))
    
    return render_template('perfil_prestador.html', prestador=prestador)

# ============================================
# INICIALIZAÇÃO DO SERVIDOR
# ============================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SISTEMA DE PRESTADORES DE SERVIÇOS")
    print("="*60)
    print("📍 Acesse: http://localhost:5000")
    print("💬 Chat em tempo real ativado!")
    print("🔐 Login com Google (Firebase) ativado!")
    print("📧 Prestador teste: prestador@email.com / 123456")
    print("="*60 + "\n")
    
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)