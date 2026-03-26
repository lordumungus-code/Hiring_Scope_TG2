from authlib.integrations.flask_client import OAuth
from flask import current_app, url_for
import os

oauth = OAuth()

def init_oauth(app):
    """Inicializa OAuth com Google"""
    oauth.init_app(app)
    
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
            'prompt': 'select_account'
        }
    )
    
    return oauth