from flask import Blueprint, request, jsonify, current_app, url_for
from flask_login import login_required, current_user

from extensions import db, limiter
from models import InscricaoPush
from services.push_service import endpoint_valido, push_configurado

push_bp = Blueprint('push', __name__)


@push_bp.route('/push/inscrever', methods=['POST'])
@login_required
@limiter.limit('30 per hour')
def inscrever():
    """Guarda a inscrição de push deste navegador para o usuário logado"""
    if not push_configurado():
        return jsonify({'erro': 'Notificações não configuradas'}), 503

    dados = request.get_json(silent=True) or {}
    endpoint = str(dados.get('endpoint') or '')
    chaves = dados.get('keys') if isinstance(dados.get('keys'), dict) else {}
    p256dh = str(chaves.get('p256dh') or '')
    auth = str(chaves.get('auth') or '')

    if not endpoint_valido(endpoint) or not p256dh or not auth or len(p256dh) > 200 or len(auth) > 100:
        return jsonify({'erro': 'Inscrição inválida'}), 400

    # O mesmo navegador passa a pertencer a quem está logado nele agora
    inscricao = InscricaoPush.query.filter_by(endpoint=endpoint).first()
    if not inscricao:
        inscricao = InscricaoPush(endpoint=endpoint)
        db.session.add(inscricao)
    inscricao.usuario_id = current_user.id
    inscricao.p256dh = p256dh
    inscricao.auth = auth
    db.session.commit()

    return jsonify({'sucesso': True})


@push_bp.route('/push/remover', methods=['POST'])
@login_required
def remover():
    """Desliga o push deste navegador (usado ao sair da conta ou ao desativar as notificações)"""
    endpoint = str((request.get_json(silent=True) or {}).get('endpoint') or '')
    InscricaoPush.query.filter_by(endpoint=endpoint, usuario_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'sucesso': True})


@push_bp.route('/sw.js')
def service_worker():
    """O service worker precisa ser servido na raiz do site para valer para todas as páginas"""
    resposta = current_app.send_static_file('js/sw.js')
    resposta.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resposta.headers['Cache-Control'] = 'no-cache'
    return resposta


@push_bp.route('/manifest.webmanifest')
def manifest():
    """Permite "Adicionar à tela de início" no celular (no iPhone, o push só funciona assim)"""
    resposta = jsonify({
        'name': 'HiringScope',
        'short_name': 'HiringScope',
        'description': 'Profissionais e serviços em Cruzeiro - SP',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#0b2b5c',
        'theme_color': '#0b2b5c',
        'lang': 'pt-BR',
        'icons': [
            {'src': url_for('static', filename='img/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': url_for('static', filename='img/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ],
    })
    resposta.headers['Content-Type'] = 'application/manifest+json'
    return resposta
