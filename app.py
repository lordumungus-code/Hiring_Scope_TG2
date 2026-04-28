from flask import Flask
from datetime import datetime
from dotenv import load_dotenv
import os

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
    
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)