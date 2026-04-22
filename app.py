from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import base64
import os
import secrets

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
    servicos_destaque = Servico.query.filter_by(destaque=True).order_by(Servico.data_postagem.desc()).limit(6).all()
    servicos_recentes = Servico.query.order_by(Servico.data_postagem.desc()).limit(8).all()
    return render_template('index.html', 
                         servicos_destaque=servicos_destaque,
                         servicos_recentes=servicos_recentes)

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
    if current_user.tipo == 'prestador':
        servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
        return render_template('dashboard_prestador.html', servicos=servicos)
    else:
        solicitacoes = Solicitacao.query.filter_by(cliente_id=current_user.id).all()
        return render_template('dashboard_cliente.html', solicitacoes=solicitacoes)

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
    categoria = request.args.get('categoria')
    if categoria:
        servicos = Servico.query.filter_by(categoria=categoria).order_by(Servico.data_postagem.desc()).all()
    else:
        servicos = Servico.query.order_by(Servico.data_postagem.desc()).all()
    return render_template('lista_servicos.html', servicos=servicos, categoria=categoria)

@app.route('/servico/<int:id>')
def detalhe_servico(id):
    servico = Servico.query.get_or_404(id)
    return render_template('detalhe_servico.html', servico=servico)

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