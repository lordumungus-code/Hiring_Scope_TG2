from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from extensions import socketio, db
from models import Mensagem, Usuario
from datetime import datetime

# Dicionário para rastrear usuários online
usuarios_online = {}

@socketio.on('connect')
def handle_connect():
    """Quando um usuário conecta via WebSocket"""
    try:
        if current_user.is_authenticated:
            user_room = f"user_{current_user.id}"
            join_room(user_room)
            
            usuarios_online[current_user.id] = {
                'nome': current_user.nome,
                'sid': request.sid
            }
            
            emit('user_status', {
                'user_id': current_user.id,
                'nome': current_user.nome,
                'status': 'online'
            }, broadcast=True)
            
            print(f"✅ Usuário {current_user.nome} conectado ao chat")
    except Exception as e:
        print(f"Erro no connect: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Quando um usuário desconecta"""
    try:
        if current_user.is_authenticated and current_user.id in usuarios_online:
            del usuarios_online[current_user.id]
            
            emit('user_status', {
                'user_id': current_user.id,
                'nome': current_user.nome,
                'status': 'offline'
            }, broadcast=True)
            
            print(f"❌ Usuário {current_user.nome} desconectado do chat")
    except Exception as e:
        print(f"Erro no disconnect: {e}")

@socketio.on('send_private_message')
def handle_private_message(data):
    """Envia mensagem privada para um usuário específico"""
    try:
        if not current_user.is_authenticated:
            return
        
        destinatario_id = data.get('destinatario_id')
        conteudo = data.get('conteudo')
        
        if not destinatario_id or not conteudo:
            return
        
        # Salva a mensagem
        mensagem = Mensagem(
            remetente_id=current_user.id,
            destinatario_id=destinatario_id,
            conteudo=conteudo
        )
        db.session.add(mensagem)
        db.session.commit()
        
        msg_data = {
            'id': mensagem.id,
            'remetente_id': current_user.id,
            'remetente_nome': current_user.nome,
            'destinatario_id': destinatario_id,
            'conteudo': conteudo,
            'data_envio': mensagem.data_envio.strftime('%d/%m/%Y %H:%M'),
            'lida': False
        }
        
        # Envia para o destinatário
        destinatario_room = f"user_{destinatario_id}"
        emit('new_private_message', msg_data, room=destinatario_room)
        
        # Confirma para o remetente
        emit('message_sent', msg_data, room=f"user_{current_user.id}")
        
        # Notificação se estiver online
        if destinatario_id in usuarios_online:
            emit('notification', {
                'tipo': 'nova_mensagem',
                'titulo': f'Nova mensagem de {current_user.nome}',
                'mensagem': conteudo[:50] + ('...' if len(conteudo) > 50 else ''),
                'remetente_id': current_user.id,
                'remetente_nome': current_user.nome
            }, room=destinatario_room)
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        db.session.rollback()

@socketio.on('typing')
def handle_typing(data):
    """Indica que o usuário está digitando"""
    try:
        if not current_user.is_authenticated:
            return
        
        destinatario_id = data.get('destinatario_id')
        is_typing = data.get('is_typing', False)
        
        if destinatario_id:
            emit('user_typing', {
                'user_id': current_user.id,
                'user_nome': current_user.nome,
                'is_typing': is_typing
            }, room=f"user_{destinatario_id}")
    except Exception as e:
        print(f"Erro no typing: {e}")

@socketio.on('mark_as_read')
def handle_mark_as_read(data):
    """Marca mensagens como lidas"""
    try:
        if not current_user.is_authenticated:
            return
        
        remetente_id = data.get('remetente_id')
        
        if remetente_id:
            Mensagem.query.filter_by(
                remetente_id=remetente_id,
                destinatario_id=current_user.id,
                lida=False
            ).update({'lida': True})
            db.session.commit()
            
            emit('messages_read', {
                'user_id': current_user.id,
                'user_nome': current_user.nome
            }, room=f"user_{remetente_id}")
    except Exception as e:
        print(f"Erro ao marcar como lida: {e}")
        db.session.rollback()

def get_historico_mensagens(user1_id, user2_id):
    """Retorna o histórico de mensagens entre dois usuários"""
    try:
        mensagens = Mensagem.query.filter(
            ((Mensagem.remetente_id == user1_id) & (Mensagem.destinatario_id == user2_id)) |
            ((Mensagem.remetente_id == user2_id) & (Mensagem.destinatario_id == user1_id))
        ).order_by(Mensagem.data_envio).all()
        
        return [{
            'id': m.id,
            'remetente_id': m.remetente_id,
            'remetente_nome': m.remetente.nome,
            'conteudo': m.conteudo,
            'data_envio': m.data_envio.strftime('%d/%m/%Y %H:%M'),
            'lida': m.lida
        } for m in mensagens]
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return []

def get_nao_lidas(user_id):
    """Retorna o número de mensagens não lidas para um usuário"""
    try:
        return Mensagem.query.filter_by(
            destinatario_id=user_id,
            lida=False
        ).count()
    except Exception as e:
        print(f"Erro ao buscar não lidas: {e}")
        return 0