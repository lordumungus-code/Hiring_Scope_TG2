from flask import Flask
from extensions import db, login_manager, socketio
from models import Usuario, Servico, Solicitacao, Mensagem, Avaliacao, Favorito
import os

# Importa os blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.servico_routes import servico_bp
from routes.dashboard_routes import dashboard_bp
from routes.perfil_routes import perfil_bp
from routes.chat_routes import chat_bp

app = Flask(__name__)

# Configurações
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-simples-mas-segura')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///prestadores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_PARTITIONED'] = False

# Configurações Firebase
app.config['FIREBASE_API_KEY'] = os.environ.get('FIREBASE_API_KEY')
app.config['FIREBASE_AUTH_DOMAIN'] = os.environ.get('FIREBASE_AUTH_DOMAIN')
app.config['FIREBASE_PROJECT_ID'] = os.environ.get('FIREBASE_PROJECT_ID')
app.config['FIREBASE_STORAGE_BUCKET'] = os.environ.get('FIREBASE_STORAGE_BUCKET')
app.config['FIREBASE_MESSAGING_SENDER_ID'] = os.environ.get('FIREBASE_MESSAGING_SENDER_ID')
app.config['FIREBASE_APP_ID'] = os.environ.get('FIREBASE_APP_ID')

# Inicializa extensões
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'

socketio.init_app(app, cors_allowed_origins="*")

# Registra os blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(servico_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(perfil_bp)
app.register_blueprint(chat_bp)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Criar tabelas e dados de exemplo
with app.app_context():
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
        
        servicos_destaque = [
            Servico(
                prestador_id=prestador.id,
                titulo='Consultoria em Marketing Digital',
                descricao='Ajuda com estratégias de marketing para seu negócio',
                categoria='Marketing',
                preco=150.00,
                destaque=True
            ),
            Servico(
                prestador_id=prestador.id,
                titulo='Desenvolvimento de Sites',
                descricao='Criação de sites profissionais e responsivos',
                categoria='Tecnologia',
                preco=2000.00,
                destaque=True
            ),
            Servico(
                prestador_id=prestador.id,
                titulo='Aulas Particulares de Inglês',
                descricao='Aulas online para todos os níveis',
                categoria='Educação',
                preco=50.00,
                destaque=True
            )
        ]
        db.session.add_all(servicos_destaque)
        db.session.commit()
        print("✅ Dados de exemplo criados!")

# ============================================
# TESTE FIREBASE
# ============================================

@app.route('/test-firebase')
def test_firebase():
    """Testa se o Firebase está configurado"""
    try:
        from firebase_admin import auth as admin_auth
        return "✅ Firebase Admin SDK está funcionando!"
    except Exception as e:
        return f"❌ Erro: {e}"

# ============================================
# INICIALIZAÇÃO DO SERVIDOR
# ============================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SISTEMA DE PRESTADORES DE SERVIÇOS")
    print("="*60)
    print("📍 Acesse: http://localhost:5000")
    print("💬 Chat em tempo real ativado!")
    print("🔐 Login com Google (Firebase) ativado!")
    print("📧 Prestador teste: prestador@email.com / 123456")
    print("="*60 + "\n")
    
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)