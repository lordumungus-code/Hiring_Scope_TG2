"""
Script para popular o banco com dados realistas + fotos.
Executar no Console do Railway: python seed_data.py
Para remover: python seed_data.py --remove
"""

import sys
import base64
import random
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import Usuario, Servico, Assinatura, Mensagem

try:
    from models import Avaliacao
    TEM_AVALIACAO = True
except ImportError:
    TEM_AVALIACAO = False

SEED_PREFIX = "seed_"
SEED_DOMAIN = "@hiring-scope.com.br"


# ============================================
# BAIXAR FOTO DE PERFIL
# ============================================
def baixar_foto_perfil(nome, genero, idx):
    urls = [
        f"https://randomuser.me/api/portraits/{genero}/{idx + 1}.jpg",
        f"https://i.pravatar.cc/200?img={idx + 1}",
        f"https://ui-avatars.com/api/?name={urllib.parse.quote(nome)}&background=0b2b5c&color=fff&size=200&bold=true",
    ]
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = response.read()
                if len(data) > 1000:
                    return base64.b64encode(data).decode('utf-8')
        except:
            continue
    return None


# ============================================
# BAIXAR FOTO DE SERVIÇO (por categoria)
# ============================================
# Fotos do Unsplash (URLs diretas com parâmetros de tamanho)
FOTOS_POR_CATEGORIA = {
    "Construção": [
        "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?w=600&h=600&fit=crop",
    ],
    "Limpeza": [
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1585421514738-01798e348b17?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1584820927498-cdd1c71a4a4c?w=600&h=600&fit=crop",
    ],
    "Design": [
        "https://images.unsplash.com/photo-1626785774573-4b799315345d?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=600&h=600&fit=crop",
    ],
    "Tecnologia": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1517430816045-df4b7de11d1d?w=600&h=600&fit=crop",
    ],
    "Educação": [
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=600&h=600&fit=crop",
    ],
    "Saúde": [
        "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=600&h=600&fit=crop",
    ],
    "Beleza": [
        "https://images.unsplash.com/photo-1604654894610-df63bc536371?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=600&h=600&fit=crop",
    ],
    "Marketing": [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1552581234-26160f608093?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1533750349088-cd871a92f312?w=600&h=600&fit=crop",
    ],
    "Serviços Gerais": [
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1621905252507-b35492cc74b4?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=600&h=600&fit=crop",
    ],
}


def baixar_foto_servico(categoria, idx):
    """Baixa uma foto do serviço baseada na categoria"""
    fotos = FOTOS_POR_CATEGORIA.get(categoria, FOTOS_POR_CATEGORIA["Serviços Gerais"])
    url = fotos[idx % len(fotos)]
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            if len(data) > 1000:
                return base64.b64encode(data).decode('utf-8')
    except Exception as e:
        print(f"     ⚠️ Erro: {str(e)[:60]}")
    
    return None


# ============================================
# DADOS
# ============================================
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
    {"nota": 5, "comentario": "Trabalho impecável, superou minhas expectativas."},
    {"nota": 5, "comentario": "Profissional muito qualificado e educado. Preço justo."},
    {"nota": 4, "comentario": "Bom trabalho, apenas atrasou um pouco. Mas o resultado ficou ótimo."},
    {"nota": 5, "comentario": "Simplesmente perfeito! Rápido, organizado e preço justo."},
    {"nota": 5, "comentario": "Recomendo! Cumpriu tudo o que prometeu e ainda deu dicas extras."},
    {"nota": 4, "comentario": "Serviço bem feito, só achei um pouco caro. Mas a qualidade compensa."},
    {"nota": 5, "comentario": "Melhor profissional que já contratei. Super atencioso."},
    {"nota": 5, "comentario": "Trabalho de altíssima qualidade. Já indiquei para vários amigos!"},
    {"nota": 5, "comentario": "Pontual, educado e fez um trabalho maravilhoso. Nota 10!"},
]


def seed_database():
    with app.app_context():
        print("🌱 Iniciando seed de dados...")
        print("=" * 60)
        
        # 1. PRESTADORES
        print("\n👤 Criando prestadores...")
        prestadores_criados = []
        for idx, p in enumerate(PRESTADORES):
            email = f"{SEED_PREFIX}{p['email']}{SEED_DOMAIN}"
            if Usuario.query.filter_by(email=email).first():
                continue
            
            print(f"  📸 {p['nome']}")
            foto = baixar_foto_perfil(p['nome'], p['genero'], idx)
            
            usuario = Usuario(
                nome=p['nome'], email=email, telefone=p['tel'],
                tipo='prestador', foto_perfil=foto,
                data_cadastro=datetime.utcnow() - timedelta(days=random.randint(30, 180))
            )
            usuario.set_password('seed123456')
            db.session.add(usuario)
            db.session.flush()
            prestadores_criados.append(usuario)
        db.session.commit()
        
        # 2. CLIENTES
        print("\n👤 Criando clientes...")
        clientes_criados = []
        for idx, c in enumerate(CLIENTES):
            email = f"{SEED_PREFIX}{c['email']}{SEED_DOMAIN}"
            if Usuario.query.filter_by(email=email).first():
                continue
            
            print(f"  📸 {c['nome']}")
            foto = baixar_foto_perfil(c['nome'], c['genero'], idx + 30)
            
            usuario = Usuario(
                nome=c['nome'], email=email, telefone=c['tel'],
                tipo='cliente', foto_perfil=foto,
                data_cadastro=datetime.utcnow() - timedelta(days=random.randint(10, 120))
            )
            usuario.set_password('seed123456')
            db.session.add(usuario)
            db.session.flush()
            clientes_criados.append(usuario)
        db.session.commit()
        
        # 3. SERVIÇOS (com fotos!)
        print("\n🔧 Criando serviços (baixando fotos)...")
        todos_prestadores = Usuario.query.filter(
            Usuario.email.like(f"{SEED_PREFIX}%")
        ).filter_by(tipo='prestador').all()
        
        servicos_criados = 0
        for idx, s in enumerate(SERVICOS):
            prestador = random.choice(todos_prestadores)
            existente = Servico.query.filter_by(
                prestador_id=prestador.id, titulo=s['titulo']
            ).first()
            if existente:
                continue
            
            print(f"  📸 {s['titulo']} ({s['categoria']})")
            imagem = baixar_foto_servico(s['categoria'], idx)
            
            servico = Servico(
                prestador_id=prestador.id,
                titulo=s['titulo'], descricao=s['desc'],
                categoria=s['categoria'], preco=s['preco'],
                tipo_preco=s['tipo_preco'],
                imagem_base64=imagem,
                destaque=random.choice([True, False, False]),
                data_postagem=datetime.utcnow() - timedelta(days=random.randint(1, 60))
            )
            db.session.add(servico)
            servicos_criados += 1
        db.session.commit()
        print(f"  ✅ {servicos_criados} serviços criados")
        
        # 4. AVALIAÇÕES
        if TEM_AVALIACAO:
            print("\n⭐ Criando avaliações...")
            try:
                todos_servicos = Servico.query.filter(
                    Servico.prestador_id.in_([p.id for p in todos_prestadores])
                ).all()
                avs_criadas = 0
                for servico in random.sample(todos_servicos, min(20, len(todos_servicos))):
                    for _ in range(random.randint(1, 5)):
                        cliente = random.choice(clientes_criados)
                        av = random.choice(AVALIACOES)
                        try:
                            avaliacao = Avaliacao(
                                prestador_id=servico.prestador_id,
                                cliente_id=cliente.id,
                                nota=av['nota'], comentario=av['comentario'],
                                data_criacao=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                            )
                            db.session.add(avaliacao)
                            avs_criadas += 1
                        except:
                            pass
                db.session.commit()
                print(f"  ✅ {avs_criadas} avaliações")
            except Exception as e:
                print(f"  ⚠️ {e}")
        
        print("\n" + "=" * 60)
        print("🎉 SEED CONCLUÍDO!")


def remove_seed_data():
    with app.app_context():
        usuarios = Usuario.query.filter(Usuario.email.like(f"{SEED_PREFIX}%")).all()
        ids = [u.id for u in usuarios]
        if not ids:
            print("Nada para remover.")
            return
        
        if TEM_AVALIACAO:
            try:
                Avaliacao.query.filter(
                    (Avaliacao.prestador_id.in_(ids)) | (Avaliacao.cliente_id.in_(ids))
                ).delete(synchronize_session=False)
            except: pass
        
        Mensagem.query.filter(
            (Mensagem.remetente_id.in_(ids)) | (Mensagem.destinatario_id.in_(ids))
        ).delete(synchronize_session=False)
        Assinatura.query.filter(Assinatura.prestador_id.in_(ids)).delete(synchronize_session=False)
        Servico.query.filter(Servico.prestador_id.in_(ids)).delete(synchronize_session=False)
        for u in usuarios:
            db.session.delete(u)
        db.session.commit()
        print(f"✅ {len(usuarios)} usuários removidos")

# ============================================
# 5. CRIAR AVALIAÇÕES (FORÇADO)
# ============================================
if TEM_AVALIACAO:
    print("\n⭐ Criando avaliações...")
    try:
        todos_servicos = Servico.query.filter(
            Servico.prestador_id.in_([p.id for p in todos_prestadores])
        ).all()
        
        avs_criadas = 0
        # Para cada serviço, cria de 2 a 5 avaliações
        for servico in todos_servicos:
            num_avaliacoes = random.randint(2, 5)
            for _ in range(num_avaliacoes):
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
                    avs_criadas += 1
                except Exception as e:
                    pass
        
        db.session.commit()
        print(f"  ✅ {avs_criadas} avaliações criadas")
    except Exception as e:
        print(f"  ⚠️ Erro: {e}")        


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--remove':
        remove_seed_data()
    else:
        seed_database()