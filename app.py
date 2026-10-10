from flask import Flask
from datetime import datetime
from dotenv import load_dotenv
import os
import secrets

from werkzeug.middleware.proxy_fix import ProxyFix

# CARREGAR .env PRIMEIRO (antes de usar os.environ)
load_dotenv()

from extensions import db, login_manager, socketio, limiter

# Blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.servico_routes import servico_bp
from routes.contrato_routes import contrato_bp
from routes.contrato_formal_routes import formal_bp
from routes.orcamento_routes import orcamento_bp
from routes.push_routes import push_bp
from routes.chat_routes import chat_bp
from routes.admin_routes import admin_bp
from routes.assinatura_routes import assinatura_bp

app = Flask(__name__)
# Atrás do proxy do Railway: usa o IP/protocolo reais do visitante (rate limit por IP, HTTPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    # Sem chave fixa as sessões seriam forjáveis; uma aleatória só derruba os logins a cada reinício
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    print("⚠️  AVISO: SECRET_KEY não configurada! Usando chave temporária (logins caem a cada reinício).")

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///prestadores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # uploads de até 10MB

# Inicializar extensões
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
socketio.init_app(app, cors_allowed_origins="*")
limiter.init_app(app)
# Registrar blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(servico_bp)
app.register_blueprint(contrato_bp)
app.register_blueprint(formal_bp)
app.register_blueprint(orcamento_bp)
app.register_blueprint(push_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(assinatura_bp)

@login_manager.user_loader
def load_user(user_id):
    from models import Usuario
    usuario = Usuario.query.get(int(user_id))
    # Conta desativada/excluída: encerra as sessões abertas em outros aparelhos
    return usuario if usuario and not usuario.desativada else None


def garantir_colunas():
    """Adiciona colunas novas em bancos já existentes (o create_all não altera tabelas)."""
    from sqlalchemy import inspect, text

    novas_colunas = [
        ('usuarios', 'desativada', 'BOOLEAN NOT NULL DEFAULT FALSE'),
        ('mensagens', 'imagem_base64', 'TEXT'),
        ('mensagens', 'apagada_remetente', 'BOOLEAN NOT NULL DEFAULT FALSE'),
        ('mensagens', 'apagada_destinatario', 'BOOLEAN NOT NULL DEFAULT FALSE'),
    ]
    inspetor = inspect(db.engine)
    existentes = {tabela: [c['name'] for c in inspetor.get_columns(tabela)] for tabela in ('usuarios', 'mensagens')}

    for tabela, coluna, tipo in novas_colunas:
        if coluna not in existentes[tabela]:
            db.session.execute(text(f'ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}'))
            db.session.commit()
            print(f"✅ Coluna '{coluna}' adicionada em {tabela}")


# Criar tabelas
with app.app_context():
    from models import Usuario, Servico, Assinatura
    db.create_all()
    garantir_colunas()

@app.context_processor
def utility_processor():
    def get_icone_categoria(categoria):
        icons = {
            'Tecnologia': 'fa-laptop-code',
            'Construção': 'fa-hard-hat',
            'Design': 'fa-paintbrush',
            'Educação': 'fa-chalkboard-user',
            'Saúde': 'fa-heartbeat',
            'Marketing': 'fa-chart-line',
            'Limpeza': 'fa-broom',
            'Beleza': 'fa-spa',
            'Eventos': 'fa-calendar-alt',
            'Serviços Gerais': 'fa-tools'
        }
        return icons.get(categoria, 'fa-tools')
    
    def get_cor_categoria(categoria):
        colors = {
            'Tecnologia': 'primary',
            'Construção': 'warning',
            'Design': 'danger',
            'Educação': 'success',
            'Saúde': 'info',
            'Marketing': 'secondary',
            'Limpeza': 'success',
            'Beleza': 'pink',
            'Eventos': 'warning',
            'Serviços Gerais': 'secondary'
        }
        return colors.get(categoria, 'dark')
    
    from services.push_service import chave_publica, push_configurado

    return {
        'get_icone_categoria': get_icone_categoria,
        'get_cor_categoria': get_cor_categoria,
        'now': datetime.utcnow(),
        # Chave pública das notificações push (vazia = recurso desligado)
        'push_chave_publica': chave_publica() if push_configurado() else ''
    }
@app.context_processor
def inject_notificacoes():
    """Injeta contagens de notificações em TODOS os templates."""
    from flask_login import current_user

    if not current_user.is_authenticated:
        return {
            'notificacoes_count': 0,
            'chat_count': 0,
        }
    
    try:
        from models import Contrato, Mensagem

        # 🔔 CONTRATOS (sino)
        if current_user.tipo == 'prestador':
            notificacoes = Contrato.query.filter_by(
                prestador_id=current_user.id,
                status='pendente'
            ).count()
        else:
            notificacoes = Contrato.query.filter_by(
                cliente_id=current_user.id,
                status='concluido'
            ).filter(Contrato.avaliacao == None).count()

        # 💬 MENSAGENS NÃO LIDAS (chat)
        try:
            chat_count = Mensagem.query.filter_by(
                destinatario_id=current_user.id,
                lida=False
            ).count()
        except Exception as e:
            print(f"⚠️ Erro contando mensagens: {e}")
            chat_count = 0

        return {
            'notificacoes_count': notificacoes,
            'chat_count': chat_count,
        }
    except Exception as e:
        print(f"⚠️ Erro em inject_notificacoes: {e}")
        return {
            'notificacoes_count': 0,
            'chat_count': 0,
        }
    
@app.route('/api/notificacoes')
def api_notificacoes():
    """Retorna lista de notificações em JSON."""
    from flask import jsonify, url_for
    from flask_login import current_user

    if not current_user.is_authenticated:
        return jsonify({'notificacoes': [], 'chat': []})

    try:
        from models import Contrato

        notificacoes = []

        if current_user.tipo == 'prestador':
            contratos_pendentes = Contrato.query.filter_by(
                prestador_id=current_user.id,
                status='pendente'
            ).order_by(Contrato.data_solicitacao.desc()).limit(5).all()

            for c in contratos_pendentes:
                notificacoes.append({
                    'tipo': 'contrato_pendente',
                    'titulo': f'Nova solicitação: {c.servico.titulo}',
                    'descricao': f'Cliente: {c.cliente.nome}',
                    'data': c.data_solicitacao.strftime('%d/%m/%Y %H:%M'),
                    'url': url_for('contrato.detalhe_contrato', contrato_id=c.id),
                    'icone': 'fa-bell',
                    'cor': 'amber',
                })
        else:
            contratos_avaliar = Contrato.query.filter_by(
                cliente_id=current_user.id,
                status='concluido'
            ).filter(Contrato.avaliacao == None).limit(5).all()

            for c in contratos_avaliar:
                notificacoes.append({
                    'tipo': 'avaliar',
                    'titulo': f'Avalie: {c.servico.titulo}',
                    'descricao': f'Prestador: {c.prestador.nome}',
                    'data': c.data_conclusao.strftime('%d/%m/%Y') if c.data_conclusao else '',
                    'url': url_for('contrato.detalhe_contrato', contrato_id=c.id),
                    'icone': 'fa-star',
                    'cor': 'amber',
                })

        return jsonify({
            'notificacoes': notificacoes,
            'chat': [],
        })
    except Exception as e:
        print(f"⚠️ Erro em api_notificacoes: {e}")
        return jsonify({'notificacoes': [], 'chat': []})



@app.errorhandler(413)
def arquivo_muito_grande(e):
    from flask import flash, redirect, request, url_for

    flash('Arquivo muito grande. O tamanho máximo é 10MB.', 'danger')
    return redirect(request.referrer or url_for('main.index'))


def criar_dados_exemplo():
    """Cria o prestador e os serviços de exemplo (apenas em desenvolvimento local)."""
    from models import Usuario, Servico

    if Usuario.query.filter_by(email='prestador@email.com').first() is None:
        prestador = Usuario(
            nome='Prestador Exemplo', 
            email='prestador@email.com',
            telefone='11999999999', 
            tipo='prestador'
        )
        prestador.set_password('123456')
        db.session.add(prestador)
        db.session.commit()
        
        servicos = [
            Servico(prestador_id=prestador.id, titulo='Consultoria em Marketing Digital',
                   descricao='Ajuda com estratégias de marketing', categoria='Marketing', preco=150.00, destaque=True),
            Servico(prestador_id=prestador.id, titulo='Desenvolvimento de Sites',
                   descricao='Criação de sites profissionais', categoria='Tecnologia', preco=2000.00, destaque=True),
            Servico(prestador_id=prestador.id, titulo='Aulas Particulares de Inglês',
                   descricao='Aulas online para todos os níveis', categoria='Educação', preco=50.00, destaque=True)
        ]
        db.session.add_all(servicos)
        db.session.commit()
        print("✅ Dados de exemplo criados!")


if __name__ == '__main__':
    # Só no servidor local: em produção (gunicorn) a conta de teste não é criada
    with app.app_context():
        criar_dados_exemplo()

    print("="*60)
    print("🚀 SISTEMA DE PRESTADORES DE SERVIÇOS")
    print("📍 Acesse: http://localhost:5000")
    print("📧 Prestador teste: prestador@email.com / 123456")
    print("🔐 Admin: python admin.py <email>")
    print("="*60)
    
    if not os.environ.get('MERCADOPAGO_ACCESS_TOKEN'):
        print("⚠️ Token Mercado Pago NÃO encontrado! Verifique o arquivo .env")
    
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    socketio.run(app, debug=debug_mode)