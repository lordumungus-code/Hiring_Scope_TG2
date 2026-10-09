from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
oauth = OAuth()

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri='memory://',
)