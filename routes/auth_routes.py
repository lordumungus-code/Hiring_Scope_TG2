from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, limiter
from models import Usuario
import base64
import os
import secrets
from itsdangerous import URLSafeTimedSerializer, BadSignature
from firebase_admin import auth as admin_auth
from config.firebase_config import firebase_auth
from utils.validators import validar_telefone, formatar_telefone, telefone_ja_existe

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

VALIDADE_LINK_SENHA = 3600  # 1 hora


def destino_apos_login():
    """Volta para a página que pediu o login (?next=...), só se for um caminho do próprio site"""
    destino = request.args.get('next', '')
    if destino.startswith('/') and not destino.startswith('//') and '\\' not in destino:
        return destino
    return url_for('main.index')


def reativar_se_desativada(usuario):
    """Conta "dormindo" volta a ficar ativa quando o dono faz login"""
    if usuario.desativada:
        usuario.desativada = False
        db.session.commit()
        flash('Sua conta foi reativada. Que bom ter você de volta!', 'info')


def _serializer_senha():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='redefinir-senha')


def gerar_token_senha(usuario):
    # O final do hash atual entra no token: depois que a senha muda, o link deixa de valer
    return _serializer_senha().dumps({'id': usuario.id, 'h': usuario.senha_hash[-16:]})


def usuario_do_token_senha(token):
    """Retorna o usuário do link de redefinição, ou None se for inválido/expirado/já usado"""
    try:
        dados = _serializer_senha().loads(token, max_age=VALIDADE_LINK_SENHA)
    except BadSignature:
        return None
    usuario = Usuario.query.get(dados.get('id'))
    if not usuario or usuario.senha_hash[-16:] != dados.get('h'):
        return None
    return usuario

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.check_password(senha) and usuario.bloqueada:
            flash('Esta conta foi bloqueada pela administração do site. Fale com o suporte se achar que foi um engano.', 'danger')
        elif usuario and usuario.check_password(senha):
            reativar_se_desativada(usuario)
            # Com "Lembrar-me" marcado, o login continua valendo depois de fechar o navegador
            login_user(usuario, remember=request.form.get('remember') == 'on')
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
            return redirect(destino_apos_login())
        else:
            flash('Email ou senha inválidos', 'danger')
    
    return render_template('login.html', email=request.form.get('email', ''))

@auth_bp.route('/cadastro', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        telefone = request.form.get('telefone')
        tipo = request.form.get('tipo')
        
        if not nome or not email or '@' not in email:
            flash('Preencha nome e e-mail válidos.', 'danger')
            return redirect(url_for('auth.cadastro'))
        
        if not senha or len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('auth.cadastro'))
        
        if tipo not in ('cliente', 'prestador'):
            flash('Tipo de conta inválido.', 'danger')
            return redirect(url_for('auth.cadastro'))
        
        if Usuario.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'danger')
            return redirect(url_for('auth.cadastro'))
        # ─── VALIDAÇÃO DE TELEFONE ───
        ok, msg, tel_limpo = validar_telefone(telefone)
        if not ok:
            flash(msg, 'danger')
            return redirect(url_for('auth.cadastro'))
        
        if telefone_ja_existe(tel_limpo):
            flash('Este telefone já está cadastrado em outra conta. Faça login ou use outro número.', 'danger')
            return redirect(url_for('auth.cadastro'))
        
        # Padroniza o telefone antes de salvar
        telefone = formatar_telefone(tel_limpo)
        
        foto_perfil = None
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                file_data = file.read()
                foto_perfil = base64.b64encode(file_data).decode('utf-8')
        
        novo_usuario = Usuario(
            nome=nome, email=email, telefone=telefone,
            tipo=tipo, foto_perfil=foto_perfil,
            # Só aparecem no perfil público se o prestador marcar no cadastro
            mostrar_telefone=tipo == 'prestador' and request.form.get('mostrar_telefone') == 'on',
            mostrar_email=tipo == 'prestador' and request.form.get('mostrar_email') == 'on'
        )
        novo_usuario.set_password(senha)
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('cadastro_usuario.html',
                          nome=request.form.get('nome', ''),
                          email=request.form.get('email', ''),
                          telefone=request.form.get('telefone', ''))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/firebase/google')
def firebase_google():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('firebase_login.html')

@auth_bp.route('/firebase/callback', methods=['POST'])
def firebase_callback():
    try:
        data = request.get_json(silent=True) or {}
        id_token = data.get('idToken')
        if not id_token:
            return jsonify({'error': 'Token não fornecido'}), 400
        
        decoded_token = admin_auth.verify_id_token(id_token)
        email = decoded_token.get('email')
        
        # Sem e-mail confirmado pelo provedor, alguém poderia entrar na conta de outra pessoa
        if not email or not decoded_token.get('email_verified'):
            return jsonify({'error': 'E-mail não verificado'}), 400
        
        nome = decoded_token.get('name', email.split('@')[0] if email else 'Usuário')
        firebase_uid = decoded_token.get('uid')
        foto_url = decoded_token.get('picture')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if not usuario:
            session['firebase_user'] = {
                'email': email, 'nome': nome,
                'firebase_uid': firebase_uid, 'foto_url': foto_url
            }
            return jsonify({'redirect': '/auth/cadastro-firebase'}), 200
        
        if usuario.bloqueada:
            return jsonify({'error': 'Esta conta foi bloqueada pela administração do site.'}), 403
        
        # Só usa a foto do Google se o usuário não enviou uma própria
        tem_foto_propria = usuario.foto_perfil and usuario.foto_perfil != 'default.jpg'
        if foto_url and not usuario.foto_url and not tem_foto_propria:
            usuario.foto_url = foto_url
            db.session.commit()
        
        reativar_se_desativada(usuario)
        login_user(usuario, remember=True)
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Erro no callback Firebase: {e}")
        return jsonify({'error': 'Não foi possível autenticar com o Google.'}), 400

@auth_bp.route('/cadastro-firebase', methods=['GET', 'POST'])
def cadastro_firebase():
    firebase_user = session.get('firebase_user')
    if not firebase_user:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        telefone = request.form.get('telefone', '')
        
        if tipo not in ('cliente', 'prestador'):
            flash('Tipo de conta inválido.', 'danger')
            return redirect(url_for('auth.cadastro_firebase'))
    
        ok, msg, tel_limpo = validar_telefone(telefone)
        if not ok:
            flash(msg, 'danger')
            return redirect(url_for('auth.cadastro_firebase'))
        
        if telefone_ja_existe(tel_limpo):
            flash('Este telefone já está cadastrado em outra conta.', 'danger')
            return redirect(url_for('auth.cadastro_firebase'))
    
        telefone = formatar_telefone(tel_limpo)

        novo_usuario = Usuario(
            nome=firebase_user['nome'], email=firebase_user['email'],
            telefone=telefone, tipo=tipo, foto_url=firebase_user.get('foto_url'),
            mostrar_telefone=tipo == 'prestador' and request.form.get('mostrar_telefone') == 'on',
            mostrar_email=tipo == 'prestador' and request.form.get('mostrar_email') == 'on'
            )
        senha_aleatoria = secrets.token_urlsafe(16)
        novo_usuario.set_password(senha_aleatoria)
            
        db.session.add(novo_usuario)
        db.session.commit()
        session.pop('firebase_user', None)
        login_user(novo_usuario, remember=True)
        flash(f'Cadastro realizado! Bem-vindo, {novo_usuario.nome}!', 'success')
        return redirect(url_for('main.index'))
        
    return render_template('cadastro_firebase.html', usuario=firebase_user)


# ============================================
# RECUPERAÇÃO DE SENHA
# ============================================

@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def esqueci_senha():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        from services.email_service import enviar_email
        
        email = request.form.get('email', '').strip()
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario:
            base_url = (os.environ.get('SITE_URL') or request.host_url).rstrip('/')
            link = base_url + url_for('auth.redefinir_senha', token=gerar_token_senha(usuario))
            
            enviado = enviar_email(
                usuario.email,
                'Redefinir sua senha - HiringScope',
                render_template('emails/redefinir_senha.html', usuario=usuario, link=link)
            )
            if not enviado and current_app.debug:
                # Desenvolvimento local sem e-mail configurado: o link sai no terminal
                print(f"🔗 Link de redefinição para {usuario.email}: {link}")
        
        # Mesma mensagem existindo ou não a conta, para não revelar quem é cadastrado
        flash('Se este e-mail estiver cadastrado, enviamos um link para redefinir a senha. Confira também a caixa de spam.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('esqueci_senha.html')


@auth_bp.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def redefinir_senha(token):
    usuario = usuario_do_token_senha(token)
    if not usuario:
        flash('Este link de redefinição é inválido ou expirou. Solicite um novo.', 'danger')
        return redirect(url_for('auth.esqueci_senha'))
    
    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha', '')
        confirmar_senha = request.form.get('confirmar_senha', '')
        
        if len(nova_senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('auth.redefinir_senha', token=token))
        
        if nova_senha != confirmar_senha:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('auth.redefinir_senha', token=token))
        
        usuario.set_password(nova_senha)
        db.session.commit()
        
        flash('Senha redefinida com sucesso! Faça login com a nova senha.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('redefinir_senha.html', token=token)
