from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import Usuario
import base64
import secrets
from firebase_admin import auth as admin_auth
from config.firebase_config import firebase_auth

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.check_password(senha):
            login_user(usuario)
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('Email ou senha inválidos', 'danger')
    
    return render_template('login.html')

@auth_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        telefone = request.form.get('telefone')
        tipo = request.form.get('tipo')
        
        if Usuario.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'danger')
            return redirect(url_for('auth.cadastro'))
        
        foto_perfil = None
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                file_data = file.read()
                foto_perfil = base64.b64encode(file_data).decode('utf-8')
        
        novo_usuario = Usuario(
            nome=nome, email=email, telefone=telefone,
            tipo=tipo, foto_perfil=foto_perfil
        )
        novo_usuario.set_password(senha)
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('cadastro_usuario.html')

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
                'email': email, 'nome': nome,
                'firebase_uid': firebase_uid, 'foto_url': foto_url
            }
            return jsonify({'redirect': '/auth/cadastro-firebase'}), 200
        
        if foto_url and not usuario.foto_url:
            usuario.foto_url = foto_url
            db.session.commit()
        
        login_user(usuario)
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"Erro no callback Firebase: {e}")
        return jsonify({'error': str(e)}), 400

@auth_bp.route('/cadastro-firebase', methods=['GET', 'POST'])
def cadastro_firebase():
    firebase_user = session.get('firebase_user')
    if not firebase_user:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        telefone = request.form.get('telefone', '')
        
        novo_usuario = Usuario(
            nome=firebase_user['nome'], email=firebase_user['email'],
            telefone=telefone, tipo=tipo, foto_url=firebase_user.get('foto_url')
        )
        senha_aleatoria = secrets.token_urlsafe(16)
        novo_usuario.set_password(senha_aleatoria)
        
        db.session.add(novo_usuario)
        db.session.commit()
        session.pop('firebase_user', None)
        login_user(novo_usuario)
        flash(f'Cadastro realizado! Bem-vindo, {novo_usuario.nome}!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('cadastro_firebase.html', usuario=firebase_user)