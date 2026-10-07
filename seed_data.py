"""
Script para popular o banco de dados com dados realistas.
Baixa fotos do randomuser.me e salva em base64 no banco.

Executar no Console do Railway:
    python seed_data.py

Para remover os dados depois:
    python seed_data.py --remove
"""

import sys
import base64
import random
import urllib.request
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import Usuario, Servico, Assinatura, Mensagem

try:
    from models import Avaliacao
    TEM_AVALIACAO = True
except ImportError:
    TEM_AVALIACAO = False

# ============================================
# CONFIGURAÇÕES
# ============================================
SEED_PREFIX = "seed_"
SEED_DOMAIN = "@hiring-scope.com.br"


# ============================================
# FUNÇÃO PARA BAIXAR FOTO E CONVERTER EM BASE64
# ============================================
def baixar_foto_base64(url):
    """Baixa uma imagem da URL e retorna em base64"""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return base64.b64encode(response.read()).decode('utf-8')
    except Exception as e:
        print(f"     ⚠️ Erro ao baixar foto {url}: {e}")
        return None


# ============================================
# DADOS REALISTAS COM FOTOS
# ============================================
# Cada pessoa tem um gênero definido, para pegarmos a foto certa
PRESTADORES = [
    {"nome": "Carlos Silva",        "email": "carlos.silva",       "tel": "11987654321", "genero": "men"},
    {"nome": "Ana Paula Santos",    "email": "ana.santos",         "tel": "11976543210", "genero": "women"},
    {"nome": "Roberto Almeida",     "email": "roberto.almeida",    "tel": "11965432109", "genero": "men"},
    {"nome": "Juliana Costa",       "email": "juliana.costa",      "tel": "11954321098", "genero": "women"},
    {"nome": "Marcos Oliveira",     "email": "marcos.oliveira",    "tel": "11943210987", "genero": "men"},
    {"nome": "Patrícia Ferreira",   "email": "patricia.ferreira",  "tel": "11932109876", "genero": "women"},
    {"nome": "Felipe Rodrigues",    "email": "felipe.rodrigues",   "tel": "11921098765", "genero": "men"},
    {"nome": "Camila Martins",      "email": "camila.martins",     "tel": "11910987654", "genero": "women"},
    {"nome": "Bruno Souza",         "email": "bruno.souza",        "tel": "11909876543", "genero": "men"},
    {"nome": "Larissa Lima",        "email": "larissa.lima",       "tel": "11998765432", "genero": "women"},
]

CLIENTES = [
    {"nome": "Maria Silva",         "email": "maria.silva",        "tel": "11988887777", "genero": "women"},
    {"nome": "João Santos",         "email": "joao.santos",        "tel": "11977776666", "genero": "men"},
    {"nome": "Fernanda Alves",      "email": "fernanda.alves",     "tel": "11966665555", "genero": "women"},
    {"nome": "Pedro Costa",         "email": "pedro.costa",        "tel": "11955554444", "genero": "men"},
    {"nome": "Carla Rodrigues",     "email": "carla.rodrigues",    "tel": "11944443333", "genero": "women"},
    {"nome": "Lucas Pereira",       "email": "lucas.pereira",      "tel": "11933332222", "genero": "men"},
]

SERVICOS = [
    {"categoria": "Construção", "titulo": "Instalação elétrica residencial", "desc": "Instalação completa de tomadas, interruptores e disjuntores. Trabalho com garantia de 6 meses.", "preco": 350.00, "tipo_preco": "fixo"},
    {"categoria": "Construção", "titulo": "Conserto de vazamentos", "desc": "Identificação e conserto de vazamentos em encanamentos, torneiras e descargas. Atendimento 24h.", "preco": 150.00, "tipo_preco": "fixo"},
    {"categoria": "Construção", "titulo": "Pintura de apartamento", "desc": "Pintura completa de apartamentos até 80m². Material não incluso. Acabamento profissional.", "preco": 25.00, "tipo_preco": "metro"},
    {"categoria": "Limpeza", "titulo": "Limpeza residencial completa", "desc": "Limpeza pesada de casas e apartamentos. Inclui banheiros, cozinha, quartos e áreas comuns.", "preco": 180.00, "tipo_preco": "fixo"},
    {"categoria": "Limpeza", "titulo": "Diarista semanal", "desc": "Serviço de diarista uma vez por semana. Organização, limpeza e passadoria inclusos.", "preco": 150.00, "tipo_preco": "dia"},
    {"categoria": "Design", "titulo": "Criação de logotipo", "desc": "Criação de logotipo profissional com 3 opções de conceito e arquivos em alta resolução.", "preco": 500.00, "tipo_preco": "fixo"},
    {"categoria": "Design", "titulo": "Design de redes sociais", "desc": "Pacote mensal com 20 artes para Instagram e Facebook. Design moderno e personalizado.", "preco": 800.00, "tipo_preco": "fixo"},
    {"categoria": "Tecnologia", "titulo": "Formatação de computador", "desc": "Formatação completa, instalação de drivers, programas essenciais e backup dos dados.", "preco": 120.00, "tipo_preco": "fixo"},
    {"categoria": "Tecnologia", "titulo": "Criação de site institucional", "desc": "Site institucional com até 5 páginas, responsivo e otimizado para SEO.", "preco": 2500.00, "tipo_preco": "fixo"},
    {"categoria": "Educação", "titulo": "Aulas particulares de matemática", "desc": "Aulas de reforço para ensino fundamental e médio. Preparação para ENEM e vestibulares.", "preco": 80.00, "tipo_preco": "hora"},
    {"categoria": "Educação", "titulo": "Aulas de inglês conversação", "desc": "Aulas dinâmicas de conversação em inglês. Todos os níveis, online ou presencial.", "preco": 90.00, "tipo_preco": "hora"},
    {"categoria": "Saúde", "titulo": "Personal trainer domiciliar", "desc": "Treinos personalizados em casa ou academia. Avaliação física inclusa.", "preco": 120.00, "tipo_preco": "hora"},
    {"categoria": "Beleza", "titulo": "Manicure e pedicure", "desc": "Atendimento a domicílio. Esmaltação, alongamento e decoração de unhas.", "preco": 70.00, "tipo_preco": "fixo"},
    {"categoria": "Marketing", "titulo": "Gestão de tráfego pago", "desc": "Gestão mensal de campanhas no Google Ads e Facebook Ads. Relatórios semanais.", "preco": 1200.00, "tipo_preco": "fixo"},
    {"categoria": "Serviços Gerais", "titulo": "Montagem de móveis", "desc": "Montagem de móveis de qualquer marca. Trabalho rápido e com garantia.", "preco": 100.00, "tipo_preco": "fixo"},
    {"categoria": "Serviços Gerais", "titulo": "Marido de aluguel", "desc": "Pequenos reparos domésticos: prateleiras, quadros, torneiras e mais.", "preco": 120.00, "tipo_preco": "hora"},
]

AVALIACOES = [
    {"nota": 5, "comentario": "Excelente profissional! Muito atencioso e pontual. Recomendo!"},
    {"nota": 5, "comentario": "Trabalho impecável, superou minhas expectativas. Com certeza vou contratar novamente."},
    {"nota": 5, "comentario": "Profissional muito qualificado e educado. Preço justo pelo serviço."},
    {"nota": 4, "comentario": "Bom trabalho, apenas atrasou um pouco na entrega. Mas o resultado ficou ótimo."},
    {"nota": 5, "comentario": "Simplesmente perfeito! Rápido, organizado e cobrou um preço justo."},
    {"nota": 5, "comentario": "Recomendo! Cumpriu tudo o que prometeu e ainda deu dicas extras."},
    {"nota": 4, "comentario": "Serviço bem feito, só achei um pouco caro. Mas a qualidade compensa."},
    {"nota": 5, "comentario": "Melhor profissional que já contratei. Super profissional e atencioso."},
    {"nota": 5, "comentario": "Trabalho de altíssima qualidade. Já indiquei para vários amigos!"},
    {"nota": 5, "comentario": "Pontual, educado e fez um trabalho maravilhoso. Nota 10!"},
]


# ============================================
# SEED
# ============================================
def seed_database():
    with app.app_context():
        print("🌱 Iniciando seed de dados...")
        print("=" * 60)
        
        # ============================================
        # 1. CRIAR PRESTADORES (com fotos!)
        # ============================================
        print("\n👤 Criando prestadores (baixando fotos)...")
        prestadores_criados = []
        for idx, p in enumerate(PRESTADORES):
            email = f"{SEED_PREFIX}{p['email']}{SEED_DOMAIN}"
            
            if Usuario.query.filter_by(email=email).first():
                print(f"  ⚠️ {p['nome']} já existe, pulando...")
                continue
            
            # Baixa foto do randomuser.me
            foto_url = f"https://randomuser.me/api/portraits/{p['genero']}/{idx + 1}.jpg"
            print(f"  📸 Baixando foto de {p['nome']}...")
            foto_base64 = baixar_foto_base64(foto_url)
            
            usuario = Usuario(
                nome=p['nome'],
                email=email,
                telefone=p['tel'],
                tipo='prestador',
                foto_perfil=foto_base64,
                data_cadastro=datetime.utcnow() - timedelta(days=random.randint(30, 180))
            )
            usuario.set_password('seed123456')
            db.session.add(usuario)
            db.session.flush()
            prestadores_criados.append(usuario)
        
        db.session.commit()
        print(f"  ✅ {len(prestadores_criados)} prestadores criados")
        
        # ============================================
        # 2. CRIAR CLIENTES (com fotos!)
        # ============================================
        print("\n👤 Criando clientes (baixando fotos)...")
        clientes_criados = []
        for idx, c in enumerate(CLIENTES):
            email = f"{SEED_PREFIX}{c['email']}{SEED_DOMAIN}"
            
            if Usuario.query.filter_by(email=email).first():
                continue
            
            # Baixa foto do randomuser.me (offset pra não repetir com prestadores)
            foto_url = f"https://randomuser.me/api/portraits/{c['genero']}/{idx + 30}.jpg"
            print(f"  📸 Baixando foto de {c['nome']}...")
            foto_base64 = baixar_foto_base64(foto_url)
            
            usuario = Usuario(
                nome=c['nome'],
                email=email,
                telefone=c['tel'],
                tipo='cliente',
                foto_perfil=foto_base64,
                data_cadastro=datetime.utcnow() - timedelta(days=random.randint(10, 120))
            )
            usuario.set_password('seed123456')
            db.session.add(usuario)
            db.session.flush()
            clientes_criados.append(usuario)
        
        db.session.commit()
        print(f"  ✅ {len(clientes_criados)} clientes criados")
        
        # ============================================
        # 3. CRIAR SERVIÇOS
        # ============================================
        print("\n🔧 Criando serviços...")
        todos_prestadores = Usuario.query.filter(
            Usuario.email.like(f"{SEED_PREFIX}%")
        ).filter_by(tipo='prestador').all()
        
        servicos_criados = []
        for s in SERVICOS:
            prestador = random.choice(todos_prestadores)
            
            existente = Servico.query.filter_by(
                prestador_id=prestador.id,
                titulo=s['titulo']
            ).first()
            if existente:
                continue
            
            servico = Servico(
                prestador_id=prestador.id,
                titulo=s['titulo'],
                descricao=s['desc'],
                categoria=s['categoria'],
                preco=s['preco'],
                tipo_preco=s['tipo_preco'],
                destaque=random.choice([True, False, False]),
                data_postagem=datetime.utcnow() - timedelta(days=random.randint(1, 60))
            )
            db.session.add(servico)
            servicos_criados.append(servico)
        
        db.session.commit()
        print(f"  ✅ {len(servicos_criados)} serviços criados")
        
        # ============================================
        # 4. CRIAR AVALIAÇÕES (se o modelo existir)
        # ============================================
        if TEM_AVALIACAO:
            print("\n⭐ Criando avaliações...")
            try:
                avaliacoes_criadas = 0
                todos_servicos = Servico.query.filter(
                    Servico.prestador_id.in_([p.id for p in todos_prestadores])
                ).all()
                
                for servico in random.sample(todos_servicos, min(20, len(todos_servicos))):
                    for _ in range(random.randint(1, 5)):
                        cliente = random.choice(clientes_criados)
                        av = random.choice(AVALIACOES)
                        
                        try:
                            avaliacao = Avaliacao(
                                prestador_id=servico.prestador_id,
                                cliente_id=cliente.id,
                                nota=av['nota'],
                                comentario=av['comentario'],
                                data_criacao=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                            )
                            db.session.add(avaliacao)
                            avaliacoes_criadas += 1
                        except Exception:
                            pass
                
                db.session.commit()
                print(f"  ✅ {avaliacoes_criadas} avaliações criadas")
            except Exception as e:
                print(f"  ⚠️ Erro ao criar avaliações: {e}")
        else:
            print("\n⚠️ Modelo Avaliacao não encontrado, pulando avaliações")
        
        # ============================================
        # RESUMO
        # ============================================
        print("\n" + "=" * 60)
        print("🎉 SEED CONCLUÍDO!")
        print("=" * 60)
        print(f"📊 Prestadores: {Usuario.query.filter(Usuario.email.like(f'{SEED_PREFIX}%')).filter_by(tipo='prestador').count()}")
        print(f"📊 Clientes: {Usuario.query.filter(Usuario.email.like(f'{SEED_PREFIX}%')).filter_by(tipo='cliente').count()}")
        print(f"📊 Serviços: {Servico.query.filter(Servico.prestador_id.in_([p.id for p in todos_prestadores])).count()}")
        print("=" * 60)
        print("🔐 Senha de todos: seed123456")
        print("🗑️  Para remover: python seed_data.py --remove")
        print("=" * 60)


# ============================================
# REMOÇÃO
# ============================================
def remove_seed_data():
    with app.app_context():
        print("🗑️  Removendo dados de seed...")
        
        usuarios_seed = Usuario.query.filter(
            Usuario.email.like(f"{SEED_PREFIX}%")
        ).all()
        
        ids_usuarios = [u.id for u in usuarios_seed]
        
        if not ids_usuarios:
            print("  ⚠️ Nenhum dado de seed encontrado.")
            return
        
        # Remove avaliações
        if TEM_AVALIACAO:
            try:
                Avaliacao.query.filter(
                    (Avaliacao.prestador_id.in_(ids_usuarios)) |
                    (Avaliacao.cliente_id.in_(ids_usuarios))
                ).delete(synchronize_session=False)
            except:
                pass
        
        # Remove mensagens
        Mensagem.query.filter(
            (Mensagem.remetente_id.in_(ids_usuarios)) |
            (Mensagem.destinatario_id.in_(ids_usuarios))
        ).delete(synchronize_session=False)
        
        # Remove assinaturas
        Assinatura.query.filter(
            Assinatura.prestador_id.in_(ids_usuarios)
        ).delete(synchronize_session=False)
        
        # Remove serviços
        Servico.query.filter(
            Servico.prestador_id.in_(ids_usuarios)
        ).delete(synchronize_session=False)
        
        # Remove usuários
        for u in usuarios_seed:
            db.session.delete(u)
        
        db.session.commit()
        print(f"  ✅ {len(usuarios_seed)} usuários e dados relacionados removidos!")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--remove':
        remove_seed_data()
    else:
        seed_database()