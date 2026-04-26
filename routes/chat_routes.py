from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Usuario, Mensagem
from datetime import datetime

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

@chat_bp.route('/')
@login_required
def index():
    """Página principal do chat - Versão simplificada"""
    try:
        # Buscar TODOS os usuários exceto o atual
        # Primeiro, tenta buscar quem já conversou
        usuarios_que_conversaram = db.session.query(Usuario).join(
            Mensagem,
            (Mensagem.remetente_id == Usuario.id) | (Mensagem.destinatario_id == Usuario.id)
        ).filter(
            (Mensagem.remetente_id == current_user.id) | (Mensagem.destinatario_id == current_user.id),
            Usuario.id != current_user.id
        ).distinct().all()
        
        # Se não houver conversas, mostrar todos os prestadores (para cliente)
        if not usuarios_que_conversaram:
            if current_user.tipo == 'cliente':
                usuarios_que_conversaram = Usuario.query.filter(
                    Usuario.tipo == 'prestador',
                    Usuario.id != current_user.id
                ).limit(10).all()
            else:
                usuarios_que_conversaram = Usuario.query.filter(
                    Usuario.tipo == 'cliente',
                    Usuario.id != current_user.id
                ).limit(10).all()
        
        print(f"[CHAT] Usuário {current_user.id} - Encontrados {len(usuarios_que_conversaram)} contatos")
        
        return render_template('chat/index.html', usuarios=usuarios_que_conversaram)
    except Exception as e:
        print(f"[CHAT] Erro: {e}")
        return render_template('chat/index.html', usuarios=[])

@chat_bp.route('/historico/<int:user_id>')
@login_required
def historico(user_id):
    """Retorna histórico de mensagens"""
    try:
        mensagens = Mensagem.query.filter(
            ((Mensagem.remetente_id == current_user.id) & (Mensagem.destinatario_id == user_id)) |
            ((Mensagem.remetente_id == user_id) & (Mensagem.destinatario_id == current_user.id))
        ).order_by(Mensagem.data_envio.asc()).all()
        
        # Marcar como lidas
        for msg in mensagens:
            if msg.destinatario_id == current_user.id and not msg.lida:
                msg.lida = True
        db.session.commit()
        
        resultado = []
        for msg in mensagens:
            resultado.append({
                'id': msg.id,
                'remetente_id': msg.remetente_id,
                'destinatario_id': msg.destinatario_id,
                'conteudo': msg.conteudo,
                'data_envio': msg.data_envio.strftime('%H:%M - %d/%m/%Y'),
                'lida': msg.lida
            })
        
        return jsonify(resultado)
    except Exception as e:
        print(f"[CHAT] Erro histórico: {e}")
        return jsonify([])

@chat_bp.route('/enviar', methods=['POST'])
@login_required
def enviar_mensagem():
    """Envia uma nova mensagem"""
    try:
        data = request.get_json()
        destinatario_id = data.get('destinatario_id')
        conteudo = data.get('conteudo', '').strip()
        
        if not conteudo:
            return jsonify({'error': 'Mensagem vazia'}), 400
        
        nova_mensagem = Mensagem(
            remetente_id=current_user.id,
            destinatario_id=destinatario_id,
            conteudo=conteudo,
            data_envio=datetime.utcnow(),
            lida=False
        )
        
        db.session.add(nova_mensagem)
        db.session.commit()
        
        print(f"🔥🔥🔥 MENSAGEM ENVIADA 🔥🔥🔥")
        print(f"  Remetente: {current_user.id} - {current_user.nome}")
        print(f"  Destinatário: {destinatario_id}")
        print(f"  Conteúdo: {conteudo}")
        
        # Emitir via socket
        from extensions import socketio
        
        print(f"  Emitindo para room: user_{destinatario_id}")
        
        socketio.emit('new_private_message', {
            'id': nova_mensagem.id,
            'remetente_id': current_user.id,
            'remetente_nome': current_user.nome,
            'destinatario_id': destinatario_id,
            'conteudo': conteudo,
            'data_envio': nova_mensagem.data_envio.strftime('%H:%M')
        }, room=f'user_{destinatario_id}')
        
        print(f"✅ Evento emitido para user_{destinatario_id}")
        
        return jsonify({
            'success': True,
            'mensagem': {
                'id': nova_mensagem.id,
                'conteudo': conteudo,
                'data_envio': nova_mensagem.data_envio.strftime('%H:%M')
            }
        })
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/nao-lidas')
@login_required
def nao_lidas():
    """Retorna número de mensagens não lidas"""
    try:
        count = Mensagem.query.filter_by(
            destinatario_id=current_user.id,
            lida=False
        ).count()
        return jsonify({'count': count})
    except Exception as e:
        print(f"[CHAT] Erro não lidas: {e}")
        return jsonify({'count': 0})

# ============================================
# ROTA PARA BADGES POR CONVERSA (APENAS UMA VEZ!)
# ============================================

@chat_bp.route('/nao-lidas-por-conversa')
@login_required
def nao_lidas_por_conversa():
    """Retorna número de mensagens não lidas por conversa"""
    try:
        from sqlalchemy import func
        
        resultados = db.session.query(
            Mensagem.remetente_id,
            func.count(Mensagem.id).label('total')
        ).filter(
            Mensagem.destinatario_id == current_user.id,
            Mensagem.lida == False
        ).group_by(Mensagem.remetente_id).all()
        
        conversas = {}
        for r in resultados:
            conversas[str(r.remetente_id)] = r.total
        
        return jsonify({'conversas': conversas})
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({'conversas': {}})

# ============================================
# ROTA PARA MARCAR MENSAGENS COMO LIDAS
# ============================================

@chat_bp.route('/marcar-lidas/<int:usuario_id>', methods=['POST'])
@login_required
def marcar_lidas(usuario_id):
    """Marca todas as mensagens de um usuário como lidas"""
    try:
        mensagens = Mensagem.query.filter_by(
            remetente_id=usuario_id,
            destinatario_id=current_user.id,
            lida=False
        ).all()
        
        for msg in mensagens:
            msg.lida = True
        
        db.session.commit()
        
        return jsonify({'success': True, 'count': len(mensagens)})
    except Exception as e:
        print(f"Erro ao marcar lidas: {e}")
        return jsonify({'success': False}), 500