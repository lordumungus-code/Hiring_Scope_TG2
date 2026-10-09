from app import app
from extensions import db
from models import Usuario
from utils.validators import limpar_telefone, formatar_telefone

with app.app_context():
    vistos = {}
    alterados = 0
    limpos = 0

    for u in Usuario.query.filter(Usuario.telefone.isnot(None)).all():
        limpo = limpar_telefone(u.telefone)
        if not limpo:
            continue

        # Duplicado → deixa em branco
        if limpo in vistos:
            print(f"⚠️  Usuário {u.id} ({u.email}) tinha telefone duplicado: {u.telefone}")
            u.telefone = None
            limpos += 1
        else:
            vistos[limpo] = u.id
            novo = formatar_telefone(limpo)
            if novo != u.telefone:
                u.telefone = novo
                alterados += 1

    db.session.commit()
    print(f"\n✅ {alterados} telefones padronizados")
    print(f"✅ {limpos} duplicados zerados")
    print(f"✅ {len(vistos)} telefones únicos mantidos")