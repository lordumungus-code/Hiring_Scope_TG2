"""Torna um usuário já cadastrado administrador.

Uso: python admin.py email@do-usuario.com
"""
import sys

from app import app, db
from models import Usuario

if len(sys.argv) != 2:
    print("Uso: python admin.py email@do-usuario.com")
    sys.exit(1)

email = sys.argv[1].strip()

with app.app_context():
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        print(f"❌ Nenhum usuário com o e-mail {email}. Cadastre-se pelo site primeiro.")
        sys.exit(1)

    usuario.is_admin = True
    db.session.commit()
    print(f"✅ {email} agora é administrador!")
