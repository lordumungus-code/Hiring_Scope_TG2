import firebase_admin
from firebase_admin import credentials, auth
import os
import json
from dotenv import load_dotenv

load_dotenv()

firebase_config = {
    "apiKey": os.environ.get('FIREBASE_API_KEY'),
    "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN'),
    "projectId": os.environ.get('FIREBASE_PROJECT_ID'),
    "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET'),
    "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
    "appId": os.environ.get('FIREBASE_APP_ID'),
    "databaseURL": os.environ.get('FIREBASE_DATABASE_URL')
}

# ============================================
# INICIALIZAÇÃO DO FIREBASE ADMIN SDK
# ============================================

# Tentar inicializar de diferentes formas (compatível com Railway e local)

if not firebase_admin._apps:
    try:
        # 1. Tentar variável de ambiente (Railway)
        firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS')
        
        if firebase_creds_json:
            cred_dict = json.loads(firebase_creds_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'projectId': firebase_config['projectId']
            })
            print("✅ Firebase Admin inicializado via variável de ambiente")
        
        # 2. Tentar arquivo local (desenvolvimento)
        else:
            cred_path = os.path.join(os.path.dirname(__file__), 'firebase-adminsdk.json')
            
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {
                    'projectId': firebase_config['projectId']
                })
                print("✅ Firebase Admin inicializado via arquivo local")
            else:
                print(f"⚠️ Arquivo de credenciais não encontrado: {cred_path}")
                print("   Configure a variável FIREBASE_CREDENTIALS no Railway")
    
    except Exception as e:
        print(f"❌ Erro ao inicializar Firebase Admin: {e}")

# Exportar o módulo auth do firebase-admin
firebase_auth = auth