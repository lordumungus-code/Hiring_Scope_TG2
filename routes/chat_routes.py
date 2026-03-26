from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import Usuario, Mensagem
from extensions import db
from services.chat_service import get_historico_mensagens, get_nao_lidas

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('/')
@login_required
def index():
    """Página principal do chat"""
    try:
        # Busca usuários que já trocaram mensagem com o current_user
        usuarios_chat = db.session.query(Usuario).distinct().join(
            Mensagem,
            ((Mensagem.remetente_id == Usuario.id) & (Mensagem.destinatario_id == current_user.id)) |
            ((Mensagem.destinatario_id == Usuario.id) & (Mensagem.remetente_id == current_user.id))
        ).filter(Usuario.id != current_user.id).all()
        
        return render_template('chat/index.html', usuarios=usuarios_chat)
    except Exception as e:
        print(f"Erro no chat: {e}")
        return render_template('chat/index.html', usuarios=[])

@chat_bp.route('/historico/<int:user_id>')
@login_required
def historico(user_id):
    """Retorna o histórico de mensagens com um usuário específico"""
    try:
        mensagens = get_historico_mensagens(current_user.id, user_id)
        return jsonify(mensagens)
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return jsonify([])

@chat_bp.route('/nao-lidas')
@login_required
def nao_lidas():
    """Retorna o número de mensagens não lidas"""
    try:
        count = get_nao_lidas(current_user.id)
        return jsonify({'count': count})
    except Exception as e:
        print(f"Erro ao buscar não lidas: {e}")
        return jsonify({'count': 0})

@chat_bp.route('/usuarios-online')
@login_required
def usuarios_online():
    """Retorna a lista de usuários online"""
    try:
        from services.chat_service import usuarios_online
        online = [{'id': uid, 'nome': data['nome']} 
                  for uid, data in usuarios_online.items() 
                  if uid != current_user.id]
        return jsonify(online)
    except Exception as e:
        print(f"Erro ao buscar online: {e}")
        return jsonify([])