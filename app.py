from flask import Flask
from datetime import datetime
from dotenv import load_dotenv
import os

from flask_socketio import join_room

# CARREGAR .env PRIMEIRO (antes de usar os.environ)
load_dotenv()

from extensions import db, login_manager, socketio

# Blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.servico_routes import servico_bp
from routes.contrato_routes import contrato_bp
from routes.chat_routes import chat_bp
from routes.admin_routes import admin_bp
from routes.assinatura_routes import assinatura_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///prestadores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensões
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
socketio.init_app(app, cors_allowed_origins="*")

# Registrar blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(servico_bp)
app.register_blueprint(contrato_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(assinatura_bp)

@login_manager.user_loader
def load_user(user_id):
    from models import Usuario
    return Usuario.query.get(int(user_id))

# Criar tabelas e dados de exemplo
with app.app_context():
    from models import Usuario, Servico, Assinatura
    db.create_all()
    
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
    
    return {
        'get_icone_categoria': get_icone_categoria,
        'get_cor_categoria': get_cor_categoria,
        'now': datetime.utcnow()
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
@login_manager.user_loader if False else (lambda f: f)  # ignora, só pra contexto
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
        return jsonify({'notificacoes': [], 'chat': [], 'erro': str(e)})



        @socketio.on('join')
        def handle_join(data):
            from flask_socketio import join_room
            user_id = data.get('user_id')
            if user_id:
                room = f'user_{user_id}'
                join_room(room)
                print(f"👤 Usuário {user_id} entrou na sala user_{user_id}")

if __name__ == '__main__':
    print("="*60)
    print("🚀 SISTEMA DE PRESTADORES DE SERVIÇOS")
    print("📍 Acesse: http://localhost:5000")
    print("📧 Prestador teste: prestador@email.com / 123456")
    print("🔐 Admin: crie um admin no banco")
    print("="*60)
    
    # Debug do token
    token = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', 'NÃO ENCONTRADO')
    if token != 'NÃO ENCONTRADO':
        print(f"🔑 Token Mercado Pago carregado: {token[:30]}...")
    else:
        print("⚠️ Token Mercado Pago NÃO encontrado! Verifique o arquivo .env")
    
    socketio.run(app, debug=True)