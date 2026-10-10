"""Notificações push do navegador (Web Push): chegam mesmo com o site fechado.

Precisa das variáveis VAPID_PUBLIC_KEY e VAPID_PRIVATE_KEY (gere com `python gerar_chaves_push.py`).
Sem elas, o recurso fica desligado e o resto do site funciona normalmente.
"""
import json
import os
from urllib.parse import urlparse

from flask import current_app
from pywebpush import webpush, WebPushException

from extensions import db, socketio
from models import InscricaoPush

# Só aceitamos endereços dos serviços de push dos navegadores (o servidor faz uma requisição
# para o endereço informado pelo navegador; sem esta lista, alguém poderia apontá-lo para outro lugar)
SERVICOS_DE_PUSH = (
    'fcm.googleapis.com',               # Chrome, Edge, Brave, Opera, Android
    '.push.services.mozilla.com',       # Firefox
    '.notify.windows.com',              # Edge antigo / Windows
    '.push.apple.com',                  # Safari (macOS e iOS)
)


def chave_publica():
    return os.environ.get('VAPID_PUBLIC_KEY', '').strip()


def push_configurado():
    return bool(chave_publica() and os.environ.get('VAPID_PRIVATE_KEY', '').strip())


def endpoint_valido(endpoint):
    try:
        url = urlparse(endpoint)
    except ValueError:
        return False
    host = (url.hostname or '').lower()
    return url.scheme == 'https' and len(endpoint) <= 1000 and any(
        host == servico or (servico.startswith('.') and host.endswith(servico)) for servico in SERVICOS_DE_PUSH
    )


def enviar_push(usuario_id, titulo, corpo, url='/', tag=None):
    """Envia a notificação para todos os aparelhos em que o usuário ativou o push (em segundo plano)"""
    if not push_configurado():
        return

    dados = json.dumps({'titulo': titulo[:80], 'corpo': (corpo or '')[:180], 'url': url, 'tag': tag}, ensure_ascii=False)
    app = current_app._get_current_object()
    socketio.start_background_task(_enviar, app, usuario_id, dados)


def _enviar(app, usuario_id, dados):
    with app.app_context():
        contato = os.environ.get('VAPID_EMAIL') or 'mailto:contato@hiring-scope.com.br'

        for inscricao in InscricaoPush.query.filter_by(usuario_id=usuario_id).all():
            try:
                webpush(
                    subscription_info={'endpoint': inscricao.endpoint,
                                       'keys': {'p256dh': inscricao.p256dh, 'auth': inscricao.auth}},
                    data=dados,
                    vapid_private_key=os.environ['VAPID_PRIVATE_KEY'].strip(),
                    vapid_claims={'sub': contato},
                    ttl=24 * 3600,   # se o aparelho estiver desligado, o serviço de push guarda por até 1 dia
                    timeout=10
                )
            except WebPushException as e:
                status = e.response.status_code if e.response is not None else None
                if status in (404, 410):
                    # O navegador cancelou a inscrição (desinstalou, limpou dados, revogou a permissão)
                    db.session.delete(inscricao)
                else:
                    print(f"⚠️ Push não entregue (status {status}): {e}")
            except Exception as e:
                print(f"⚠️ Erro ao enviar push: {e}")

        db.session.commit()


def notificar(usuario_id, titulo, mensagem, url='/'):
    """Avisa o usuário: na tela se ele estiver com o site aberto; por push se estiver fora"""
    from routes.chat_routes import esta_online

    socketio.emit('notification', {'titulo': titulo, 'mensagem': mensagem, 'url': url}, room=f'user_{usuario_id}')
    if not esta_online(usuario_id):
        enviar_push(usuario_id, titulo, mensagem, url)
