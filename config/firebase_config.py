import firebase_admin
from firebase_admin import credentials, auth
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Configurações do Firebase (usadas nos templates)
firebase_config = {
    "apiKey": os.environ.get('FIREBASE_API_KEY', 'AIzaSyANfk1Nlat3JjepQq7lClbmu6xImva_W6Y'),
    "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN', 'hiring-scope.firebaseapp.com'),
    "projectId": os.environ.get('FIREBASE_PROJECT_ID', 'hiring-scope'),
    "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET', 'hiring-scope.firebasestorage.app'),
    "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '400656444315'),
    "appId": os.environ.get('FIREBASE_APP_ID', '1:400656444315:web:cff12e5a8a7593fde20f3e'),
    "databaseURL": os.environ.get('FIREBASE_DATABASE_URL', 'https://hiring-scope-default-rtdb.firebaseio.com')
}

# Firebase Admin SDK - tenta local primeiro, depois variável de ambiente
try:
    # Tentativa 1: arquivo local (desenvolvimento)
    cred_path = os.path.join(os.path.dirname(__file__), 'firebase-adminsdk.json')
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin SDK inicializado via arquivo local")
    else:
        # Tentativa 2: variável de ambiente (produção no Render)
        cred_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK inicializado via variável de ambiente")
        else:
            print("⚠️ Nenhuma credencial Firebase encontrada")
            
except Exception as e:
    print(f"❌ Erro ao inicializar Firebase Admin: {e}")

def get_firebase_config():
    return firebase_config