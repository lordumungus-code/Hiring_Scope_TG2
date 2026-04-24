from app import app, db
from models import Usuario

with app.app_context():
    # Criar admin
    admin = Usuario.query.filter_by(email='seu-email@admin.com').first()
    if not admin:
        admin = Usuario(
            nome='Admin',
            email='admin@admin.com',
            tipo='prestador',
            is_admin=True
        )
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin criado!")
    else:
        admin.is_admin = True
        db.session.commit()
        print("✅ Admin ativado!")