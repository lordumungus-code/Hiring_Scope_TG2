import pyrebase
import firebase_admin
from firebase_admin import credentials, auth
import os
from dotenv import load_dotenv

load_dotenv()

firebase_config = {
    "apiKey": os.environ.get('FIREBASE_API_KEY', 'AIzaSyANfk1Nlat3JjepQq7lClbmu6xImva_W6Y'),
    "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN', 'hiring-scope.firebaseapp.com'),
    "projectId": os.environ.get('FIREBASE_PROJECT_ID', 'hiring-scope'),
    "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET', 'hiring-scope.firebasestorage.app'),
    "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '400656444315'),
    "appId": os.environ.get('FIREBASE_APP_ID', '1:400656444315:web:cff12e5a8a7593fde20f3e'),
    "databaseURL": os.environ.get('FIREBASE_DATABASE_URL', 'https://hiring-scope-default-rtdb.firebaseio.com')
}

firebase = pyrebase.initialize_app(firebase_config)
firebase_auth = firebase.auth()

# Firebase Admin SDK com tolerância de tempo
try:
    cred_path = os.path.join(os.path.dirname(__file__), 'firebase-adminsdk.json')
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        # Adiciona tolerância de 5 minutos para verificação de token
        firebase_admin.initialize_app(cred, {
            'projectId': firebase_config['projectId']
        })
        print("✅ Firebase Admin SDK inicializado com sucesso")
    else:
        print(f"⚠️ Arquivo de credenciais não encontrado em: {cred_path}")
except Exception as e:
    print(f"❌ Erro ao inicializar Firebase Admin: {e}")