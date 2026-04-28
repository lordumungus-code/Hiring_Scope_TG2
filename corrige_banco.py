import sqlite3
import os

db_path = 'instance/prestadores.db'

if not os.path.exists(db_path):
    print("❌ Banco de dados não encontrado. Execute o app primeiro.")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Lista de colunas para adicionar na tabela contratos
colunas_contratos = [
    ('valor_servico', 'REAL'),
    ('comissao_plataforma', 'REAL DEFAULT 10.0'),
    ('valor_comissao', 'REAL DEFAULT 0.0'),
    ('valor_liquido_prestador', 'REAL DEFAULT 0.0'),
    ('pagamento_status', 'VARCHAR(20) DEFAULT "pendente"'),
    ('transacao_id', 'VARCHAR(100)'),
    ('data_pagamento_cliente', 'DATETIME'),
    ('data_pagamento_prestador', 'DATETIME')
]

# Lista de colunas para adicionar na tabela servicos
colunas_servicos = [
    ('plano_destaque', 'VARCHAR(20)')
]

# Lista de colunas para adicionar na tabela usuarios
colunas_usuarios = [
    ('assinatura_id', 'INTEGER')
]

def adicionar_coluna(tabela, coluna, tipo):
    try:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        print(f"✅ Coluna '{coluna}' adicionada em {tabela}")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print(f"⚠️ Coluna '{coluna}' já existe em {tabela}")
        else:
            print(f"❌ Erro ao adicionar {coluna} em {tabela}: {e}")

# Verificar/Adicionar colunas na tabela contratos
print("\n📌 Verificando tabela 'contratos'...")
for coluna, tipo in colunas_contratos:
    adicionar_coluna('contratos', coluna, tipo)

# Verificar/Adicionar colunas na tabela servicos
print("\n📌 Verificando tabela 'servicos'...")
for coluna, tipo in colunas_servicos:
    adicionar_coluna('servicos', coluna, tipo)

# Verificar/Adicionar colunas na tabela usuarios
print("\n📌 Verificando tabela 'usuarios'...")
for coluna, tipo in colunas_usuarios:
    adicionar_coluna('usuarios', coluna, tipo)

# Verificar se a tabela assinaturas existe
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assinaturas'")
if not cursor.fetchone():
    print("\n📌 Criando tabela 'assinaturas'...")
    cursor.execute('''
        CREATE TABLE assinaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prestador_id INTEGER NOT NULL,
            plano VARCHAR(20) NOT NULL,
            status VARCHAR(20) DEFAULT 'ativa',
            data_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_fim DATETIME NOT NULL,
            ultimo_pagamento DATETIME,
            pagamento_id VARCHAR(100),
            FOREIGN KEY (prestador_id) REFERENCES usuarios(id)
        )
    ''')
    print("✅ Tabela 'assinaturas' criada!")

conn.commit()
conn.close()

print("\n✅ Migração concluída!")
print("🚀 Agora reinicie o servidor com: python app.py")