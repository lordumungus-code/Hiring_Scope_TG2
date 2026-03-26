from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Usuario
import base64

perfil_bp = Blueprint('perfil', __name__, url_prefix='/perfil')

@perfil_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
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
                return redirect(url_for('perfil.index'))
        
        # Processa a foto de perfil
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                file_data = file.read()
                if len(file_data) > 5 * 1024 * 1024:
                    flash('A imagem deve ter no máximo 5MB.', 'danger')
                    return redirect(url_for('perfil.index'))
                foto_base64 = base64.b64encode(file_data).decode('utf-8')
                current_user.foto_perfil = foto_base64
        
        current_user.nome = nome
        current_user.email = email
        current_user.telefone = telefone
        current_user.descricao = descricao
        
        db.session.commit()
        
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('perfil.index'))
    
    return render_template('perfil.html', usuario=current_user)

@perfil_bp.route('/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
    """Altera a senha do usuário"""
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    confirmar_senha = request.form.get('confirmar_senha')
    
    if not current_user.check_password(senha_atual):
        flash('Senha atual incorreta.', 'danger')
        return redirect(url_for('perfil.index'))
    
    if nova_senha != confirmar_senha:
        flash('As novas senhas não coincidem.', 'danger')
        return redirect(url_for('perfil.index'))
    
    current_user.set_password(nova_senha)
    db.session.commit()
    
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('perfil.index'))