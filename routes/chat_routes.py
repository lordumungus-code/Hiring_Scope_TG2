from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Usuario, Mensagem
from datetime import datetime
from sqlalchemy import func

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.route('/')
@login_required
def index():
    """Página principal do chat - Conversas + Sugestões"""
    try:
        # ============================================
        # 1. BUSCAR CONVERSAS EXISTENTES
        # ============================================
        usuarios_que_conversaram = db.session.query(Usuario).join(
            Mensagem,
            (Mensagem.remetente_id == Usuario.id) | (Mensagem.destinatario_id == Usuario.id)
        ).filter(
            (Mensagem.remetente_id == current_user.id) | (Mensagem.destinatario_id == current_user.id),
            Usuario.id != current_user.id
        ).distinct().all()
        
        # ============================================
        # 2. BUSCAR SUGESTÕES (com quem ainda NÃO conversou)
        # ============================================
        ids_que_ja_conversou = [u.id for u in usuarios_que_conversaram]
        
        # Agora permitimos que TODOS possam conversar com TODOS
        # (prestador ↔ cliente, prestador ↔ prestador, cliente ↔ cliente)
        query_sugestoes = Usuario.query.filter(Usuario.id != current_user.id)
        
        # Remove os que já estão na lista de conversas
        if ids_que_ja_conversou:
            query_sugestoes = query_sugestoes.filter(~Usuario.id.in_(ids_que_ja_conversou))
        
        sugestoes = query_sugestoes.order_by(Usuario.nome.asc()).limit(20).all()
        
        # ============================================
        # 3. BUSCAR CONTAGEM DE NÃO LIDAS POR CONVERSA
        # ============================================
        nao_lidas_por_usuario = {}
        try:
            resultados = db.session.query(
                Mensagem.remetente_id,
                func.count(Mensagem.id).label('total')
            ).filter(
                Mensagem.destinatario_id == current_user.id,
                Mensagem.lida == False
            ).group_by(Mensagem.remetente_id).all()
            
            for r in resultados:
                nao_lidas_por_usuario[r.remetente_id] = r.total
        except Exception as e:
            print(f"[CHAT] Erro ao buscar não lidas: {e}")
        
        print(f"[CHAT] Usuário {current_user.id} ({current_user.nome}) - "
              f"{len(usuarios_que_conversaram)} conversas, {len(sugestoes)} sugestões")
        
        return render_template(
            'chat/index.html',
            usuarios=usuarios_que_conversaram,
            sugestoes=sugestoes,
            nao_lidas_por_usuario=nao_lidas_por_usuario
        )
    except Exception as e:
        print(f"[CHAT] Erro: {e}")
        import traceback
        traceback.print_exc()
        return render_template('chat/index.html', usuarios=[], sugestoes=[], nao_lidas_por_usuario={})


@chat_bp.route('/historico/<int:user_id>')
@login_required
def historico(user_id):
    """Retorna histórico de mensagens"""
    try:
        # Verifica se o usuário existe
        outro_usuario = Usuario.query.get(user_id)
        if not outro_usuario:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        
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
        
        if not destinatario_id:
            return jsonify({'error': 'Destinatário não informado'}), 400
        
        # Verifica se o destinatário existe
        destinatario = Usuario.query.get(destinatario_id)
        if not destinatario:
            return jsonify({'error': 'Destinatário não encontrado'}), 404
        
        nova_mensagem = Mensagem(
            remetente_id=current_user.id,
            destinatario_id=destinatario_id,
            conteudo=conteudo,
            data_envio=datetime.utcnow(),
            lida=False
        )
        
        db.session.add(nova_mensagem)
        db.session.commit()
        
        print(f"🔥 MENSAGEM ENVIADA: {current_user.nome} → {destinatario.nome}")
        
        # Emitir via socket
        from extensions import socketio
        
        socketio.emit('new_private_message', {
            'id': nova_mensagem.id,
            'remetente_id': current_user.id,
            'remetente_nome': current_user.nome,
            'destinatario_id': destinatario_id,
            'conteudo': conteudo,
            'data_envio': nova_mensagem.data_envio.strftime('%H:%M')
        }, room=f'user_{destinatario_id}')
        
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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/nao-lidas')
@login_required
def nao_lidas():
    """Retorna número total de mensagens não lidas"""
    try:
        count = Mensagem.query.filter_by(
            destinatario_id=current_user.id,
            lida=False
        ).count()
        return jsonify({'count': count})
    except Exception as e:
        print(f"[CHAT] Erro não lidas: {e}")
        return jsonify({'count': 0})


@chat_bp.route('/nao-lidas-por-conversa')
@login_required
def nao_lidas_por_conversa():
    """Retorna número de mensagens não lidas por conversa"""
    try:
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