from flask import Blueprint, render_template, jsonify, request, Response, abort
from flask_login import login_required, current_user
from flask_socketio import join_room
from extensions import db, socketio, limiter
from models import Usuario, Mensagem
from utils.imagens import processar_imagem
from services.push_service import enviar_push
from datetime import datetime
from sqlalchemy import func, or_, and_
import base64

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


# ============================================
# PRESENÇA (quem está online de verdade)
# ============================================
# Online = tem pelo menos uma aba do site aberta (cada aba mantém uma conexão Socket.IO).
# Fica em memória: funciona porque o servidor roda com um único worker.

conexoes_por_usuario = {}   # user_id -> conjunto de conexões (sid) abertas
usuario_por_conexao = {}    # sid -> user_id
ESPERA_OFFLINE = 5          # segundos; evita piscar "offline" ao trocar de página


def esta_online(user_id):
    return bool(conexoes_por_usuario.get(user_id))


@socketio.on('connect')
def handle_connect():
    """Coloca o usuário logado na própria sala (user_<id>) e marca como online."""
    # A identidade vem da sessão, nunca de um id enviado pelo cliente
    if not current_user.is_authenticated:
        return

    user_id = current_user.id
    join_room(f'user_{user_id}')

    ja_estava_online = esta_online(user_id)
    conexoes_por_usuario.setdefault(user_id, set()).add(request.sid)
    usuario_por_conexao[request.sid] = user_id

    if not ja_estava_online:
        socketio.emit('user_status', {'user_id': user_id, 'online': True})


@socketio.on('disconnect')
def handle_disconnect():
    user_id = usuario_por_conexao.pop(request.sid, None)
    if user_id is None:
        return

    conexoes = conexoes_por_usuario.get(user_id, set())
    conexoes.discard(request.sid)

    if not conexoes:
        conexoes_por_usuario.pop(user_id, None)
        socketio.start_background_task(avisar_offline, user_id)


def avisar_offline(user_id):
    """Só avisa que saiu se o usuário não voltou logo em seguida (ex.: mudou de página)."""
    socketio.sleep(ESPERA_OFFLINE)
    if not esta_online(user_id):
        socketio.emit('user_status', {'user_id': user_id, 'online': False})


@chat_bp.route('/online')
@login_required
def online():
    """Lista os ids dos usuários que estão online agora"""
    return jsonify({'online': [uid for uid in conexoes_por_usuario if uid != current_user.id]})


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def mensagens_visiveis(outro_id=None):
    """Mensagens do usuário logado que ele não apagou (opcionalmente só com outro_id)"""
    eu = current_user.id
    enviadas = and_(Mensagem.remetente_id == eu, Mensagem.apagada_remetente == False)
    recebidas = and_(Mensagem.destinatario_id == eu, Mensagem.apagada_destinatario == False)
    if outro_id is not None:
        enviadas = and_(enviadas, Mensagem.destinatario_id == outro_id)
        recebidas = and_(recebidas, Mensagem.remetente_id == outro_id)
    return Mensagem.query.filter(or_(enviadas, recebidas))


def mensagem_json(msg):
    return {
        'id': msg.id,
        'remetente_id': msg.remetente_id,
        'destinatario_id': msg.destinatario_id,
        'conteudo': msg.conteudo,
        'tem_imagem': msg.imagem_base64 is not None,
        # Horário em UTC; o navegador converte para o horário local
        'data_iso': msg.data_envio.isoformat() + 'Z',
        'lida': msg.lida
    }


def marcar_como_lidas(remetente_id):
    """Marca como lidas as mensagens recebidas de remetente_id e avisa quem enviou"""
    quantidade = Mensagem.query.filter_by(
        remetente_id=remetente_id,
        destinatario_id=current_user.id,
        lida=False
    ).update({'lida': True}, synchronize_session=False)
    db.session.commit()

    if quantidade:
        socketio.emit('messages_read', {'leitor_id': current_user.id}, room=f'user_{remetente_id}')
    return quantidade


def entregar(mensagem):
    """Avisa o destinatário em tempo real"""
    dados = mensagem_json(mensagem)
    dados['remetente_nome'] = current_user.nome
    if mensagem.imagem_base64 is not None and not mensagem.conteudo:
        dados['conteudo'] = '📷 Foto'   # texto usado nas notificações e na prévia da conversa
    socketio.emit('new_private_message', dados, room=f'user_{mensagem.destinatario_id}')
    
    # Destinatário com o site fechado: aviso por notificação push
    if not esta_online(mensagem.destinatario_id):
        enviar_push(mensagem.destinatario_id, f'Nova mensagem de {current_user.nome}', dados['conteudo'],
                    url='/chat/', tag=f'chat-{current_user.id}')


# ============================================
# PÁGINA
# ============================================

@chat_bp.route('/')
@login_required
def index():
    """Página principal do chat - Conversas + Sugestões"""
    try:
        # ============================================
        # 1. BUSCAR CONVERSAS EXISTENTES (que o usuário não apagou)
        # ============================================
        pares = mensagens_visiveis().with_entities(
            Mensagem.remetente_id, Mensagem.destinatario_id
        ).distinct().all()
        ids_que_ja_conversou = {d if r == current_user.id else r for r, d in pares}
        ids_que_ja_conversou.discard(current_user.id)

        usuarios_que_conversaram = (
            Usuario.query.filter(Usuario.id.in_(ids_que_ja_conversou)).order_by(Usuario.nome.asc()).all()
            if ids_que_ja_conversou else []
        )

        # ============================================
        # 2. BUSCAR SUGESTÕES (com quem ainda NÃO conversou)
        # ============================================
        # Agora permitimos que TODOS possam conversar com TODOS
        # (prestador ↔ cliente, prestador ↔ prestador, cliente ↔ cliente)
        query_sugestoes = Usuario.query.filter(Usuario.id != current_user.id, Usuario.desativada == False)

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


# ============================================
# MENSAGENS
# ============================================

@chat_bp.route('/historico/<int:user_id>')
@login_required
def historico(user_id):
    """Retorna histórico de mensagens"""
    try:
        # Verifica se o usuário existe
        outro_usuario = Usuario.query.get(user_id)
        if not outro_usuario:
            return jsonify({'error': 'Usuário não encontrado'}), 404

        # Abrir a conversa conta como "visto"
        marcar_como_lidas(user_id)

        mensagens = mensagens_visiveis(user_id).order_by(Mensagem.data_envio.asc(), Mensagem.id.asc()).all()
        return jsonify([mensagem_json(msg) for msg in mensagens])
    except Exception as e:
        print(f"[CHAT] Erro histórico: {e}")
        return jsonify([])


@chat_bp.route('/enviar', methods=['POST'])
@login_required
def enviar_mensagem():
    """Envia uma nova mensagem"""
    try:
        data = request.get_json(silent=True) or {}
        destinatario_id = data.get('destinatario_id')
        conteudo = str(data.get('conteudo') or '').strip()

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
            destinatario_id=destinatario.id,
            conteudo=conteudo,
            data_envio=datetime.utcnow(),
            lida=False
        )

        db.session.add(nova_mensagem)
        db.session.commit()

        entregar(nova_mensagem)

        return jsonify({'success': True, 'mensagem': mensagem_json(nova_mensagem)})
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Não foi possível enviar a mensagem.'}), 500


@chat_bp.route('/enviar-imagem', methods=['POST'])
@login_required
@limiter.limit('20 per minute')
def enviar_imagem():
    """Envia uma foto (com legenda opcional)"""
    destinatario = Usuario.query.get(request.form.get('destinatario_id', type=int) or 0)
    if not destinatario:
        return jsonify({'error': 'Destinatário não encontrado'}), 404

    arquivo = request.files.get('imagem')
    if not arquivo or arquivo.filename == '':
        return jsonify({'error': 'Nenhuma imagem enviada'}), 400

    imagem = processar_imagem(arquivo)
    if not imagem:
        return jsonify({'error': 'Arquivo de imagem inválido'}), 400

    nova_mensagem = Mensagem(
        remetente_id=current_user.id,
        destinatario_id=destinatario.id,
        conteudo=request.form.get('legenda', '').strip()[:1000],
        imagem_base64=imagem,
        data_envio=datetime.utcnow(),
        lida=False
    )
    db.session.add(nova_mensagem)
    db.session.commit()

    entregar(nova_mensagem)

    return jsonify({'success': True, 'mensagem': mensagem_json(nova_mensagem)})


@chat_bp.route('/imagem/<int:mensagem_id>')
@login_required
def imagem(mensagem_id):
    """Entrega a foto de uma mensagem, só para quem participa da conversa"""
    msg = mensagens_visiveis().filter(Mensagem.id == mensagem_id).first()
    if not msg or msg.imagem_base64 is None:
        abort(404)

    resposta = Response(base64.b64decode(msg.imagem_base64), mimetype='image/jpeg')
    # A foto de uma mensagem nunca muda; "private" para não ficar em caches compartilhados
    resposta.headers['Cache-Control'] = 'private, max-age=86400'
    return resposta


@chat_bp.route('/apagar/<int:usuario_id>', methods=['POST'])
@login_required
def apagar_conversa(usuario_id):
    """Apaga a conversa só para o usuário logado; a outra pessoa continua vendo as mensagens"""
    eu = current_user.id

    Mensagem.query.filter_by(remetente_id=eu, destinatario_id=usuario_id).update(
        {'apagada_remetente': True}, synchronize_session=False)
    Mensagem.query.filter_by(remetente_id=usuario_id, destinatario_id=eu).update(
        {'apagada_destinatario': True, 'lida': True}, synchronize_session=False)

    # Quando os dois lados já apagaram, a mensagem sai do banco de vez
    Mensagem.query.filter(
        or_(and_(Mensagem.remetente_id == eu, Mensagem.destinatario_id == usuario_id),
            and_(Mensagem.remetente_id == usuario_id, Mensagem.destinatario_id == eu)),
        Mensagem.apagada_remetente == True,
        Mensagem.apagada_destinatario == True
    ).delete(synchronize_session=False)

    db.session.commit()
    return jsonify({'success': True})


# ============================================
# NÃO LIDAS
# ============================================

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
        return jsonify({'success': True, 'count': marcar_como_lidas(usuario_id)})
    except Exception as e:
        print(f"Erro ao marcar lidas: {e}")
        return jsonify({'success': False}), 500
