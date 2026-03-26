from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
oauth = OAuth()