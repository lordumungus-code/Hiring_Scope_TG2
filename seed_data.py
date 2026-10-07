"""
Script para popular o banco com dados realistas + fotos + avaliações + contratos.
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
from models import Usuario, Servico, Assinatura, Mensagem, Avaliacao, Contrato, Solicitacao

SEED_PREFIX = "seed_"
SEED_DOMAIN = "@hiring-scope.com.br"


# ============================================
# BAIXAR FOTO
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


FOTOS_POR_CATEGORIA = {
    "Construção": [
        "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=600&h=600&fit=crop",
    ],
    "Limpeza": [
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1585421514738-01798e348b17?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?w=600&h=600&fit=crop",
    ],
    "Design": [
        "https://images.unsplash.com/photo-1626785774573-4b799315345d?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1561070791-2526d30994b5?w=600&h=600&fit=crop",
    ],
    "Tecnologia": [
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=600&h=600&fit=crop",
    ],
    "Educação": [
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=600&h=600&fit=crop",
    ],
    "Saúde": [
        "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=600&h=600&fit=crop",
    ],
    "Beleza": [
        "https://images.unsplash.com/photo-1604654894610-df63bc536371?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=600&h=600&fit=crop",
    ],
    "Marketing": [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1552581234-26160f608093?w=600&h=600&fit=crop",
    ],
    "Serviços Gerais": [
        "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=600&h=600&fit=crop",
        "https://images.unsplash.com/photo-1621905252507-b35492cc74b4?w=600&h=600&fit=crop",
    ],
}


def baixar_foto_servico(categoria, idx):
    fotos = FOTOS_POR_CATEGORIA.get(categoria, FOTOS_POR_CATEGORIA["Serviços Gerais"])
    url = fotos[idx % len(fotos)]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
            if len(data) > 1000:
                return base64.b64encode(data).decode('utf-8')
    except:
        pass
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
    {"categoria": "Construção", "titulo": "Instalação elétrica residencial", "desc": "Instalação completa de tomadas, interruptores e disjuntores. Garantia de 6 meses.", "preco": 350.00, "tipo_preco": "fixo"},
    {"categoria": "Construção", "titulo": "Conserto de vazamentos", "desc": "Identificação e conserto de vazamentos em encanamentos, torneiras e descargas. 24h.", "preco": 150.00, "tipo_preco": "fixo"},
    {"categoria": "Construção", "titulo": "Pintura de apartamento", "desc": "Pintura completa de apartamentos até 80m². Material não incluso.", "preco": 25.00, "tipo_preco": "metro"},
    {"categoria": "Limpeza", "titulo": "Limpeza residencial completa", "desc": "Limpeza pesada de casas e apartamentos. Inclui banheiros, cozinha e quartos.", "preco": 180.00, "tipo_preco": "fixo"},
    {"categoria": "Limpeza", "titulo": "Diarista semanal", "desc": "Diarista uma vez por semana. Organização, limpeza e passadoria inclusos.", "preco": 150.00, "tipo_preco": "dia"},
    {"categoria": "Design", "titulo": "Criação de logotipo", "desc": "Logotipo profissional com 3 opções e arquivos em alta resolução.", "preco": 500.00, "tipo_preco": "fixo"},
    {"categoria": "Design", "titulo": "Design de redes sociais", "desc": "Pacote mensal com 20 artes para Instagram e Facebook.", "preco": 800.00, "tipo_preco": "fixo"},
    {"categoria": "Tecnologia", "titulo": "Formatação de computador", "desc": "Formatação completa, drivers, programas essenciais e backup.", "preco": 120.00, "tipo_preco": "fixo"},
    {"categoria": "Tecnologia", "titulo": "Criação de site institucional", "desc": "Site institucional com até 5 páginas, responsivo e otimizado.", "preco": 2500.00, "tipo_preco": "fixo"},
    {"categoria": "Educação", "titulo": "Aulas particulares de matemática", "desc": "Reforço para fundamental e médio. Preparação para ENEM.", "preco": 80.00, "tipo_preco": "hora"},
    {"categoria": "Educação", "titulo": "Aulas de inglês conversação", "desc": "Conversação em inglês. Todos os níveis, online ou presencial.", "preco": 90.00, "tipo_preco": "hora"},
    {"categoria": "Saúde", "titulo": "Personal trainer domiciliar", "desc": "Treinos personalizados. Avaliação física inclusa.", "preco": 120.00, "tipo_preco": "hora"},
    {"categoria": "Beleza", "titulo": "Manicure e pedicure", "desc": "Atendimento a domicílio. Esmaltação, alongamento e decoração.", "preco": 70.00, "tipo_preco": "fixo"},
    {"categoria": "Marketing", "titulo": "Gestão de tráfego pago", "desc": "Gestão mensal de campanhas no Google Ads e Facebook Ads.", "preco": 1200.00, "tipo_preco": "fixo"},
    {"categoria": "Serviços Gerais", "titulo": "Montagem de móveis", "desc": "Montagem de móveis de qualquer marca. Rápido e garantido.", "preco": 100.00, "tipo_preco": "fixo"},
    {"categoria": "Serviços Gerais", "titulo": "Marido de aluguel", "desc": "Pequenos reparos: prateleiras, quadros, torneiras e mais.", "preco": 120.00, "tipo_preco": "hora"},
]

COMENTARIOS = [
    "Excelente profissional! Muito atencioso e pontual. Recomendo!",
    "Trabalho impecável, superou minhas expectativas.",
    "Profissional muito qualificado e educado. Preço justo.",
    "Bom trabalho, apenas atrasou um pouco. Mas o resultado ficou ótimo.",
    "Simplesmente perfeito! Rápido, organizado e preço justo.",
    "Recomendo! Cumpriu tudo o que prometeu e ainda deu dicas extras.",
    "Serviço bem feito, só achei um pouco caro. Mas a qualidade compensa.",
    "Melhor profissional que já contratei. Super atencioso.",
    "Trabalho de altíssima qualidade. Já indiquei para vários amigos!",
    "Pontual, educado e fez um trabalho maravilhoso. Nota 10!",
]


# ============================================
# SEED PRINCIPAL
# ============================================
def seed_database():
    with app.app_context():
        print("🌱 Iniciando seed de dados...")
        print("=" * 60)
        
        # ============================================
        # 1. PRESTADORES
        # ============================================
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
        print(f"  ✅ {len(prestadores_criados)} prestadores")
        
        # ============================================
        # 2. CLIENTES
        # ============================================
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
        print(f"  ✅ {len(clientes_criados)} clientes")
        
        # ============================================
        # 3. SERVIÇOS
        # ============================================
        print("\n🔧 Criando serviços...")
        todos_prestadores = Usuario.query.filter(
            Usuario.email.like(f"{SEED_PREFIX}%")
        ).filter_by(tipo='prestador').all()
        
        servicos_criados = []
        for idx, s in enumerate(SERVICOS):
            prestador = random.choice(todos_prestadores)
            existente = Servico.query.filter_by(
                prestador_id=prestador.id, titulo=s['titulo']
            ).first()
            if existente:
                continue
            
            print(f"  📸 {s['titulo']}")
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
            servicos_criados.append(servico)
        db.session.commit()
        print(f"  ✅ {len(servicos_criados)} serviços")
        
        # ============================================
        # 4. CONTRATOS CONCLUÍDOS (PRIMEIRO!)
        # ============================================
        print("\n📄 Criando contratos concluídos...")
        todos_servicos = Servico.query.filter(
            Servico.prestador_id.in_([p.id for p in todos_prestadores])
        ).all()
        
        contratos_criados = []
        for i in range(30):  # 30 contratos concluídos
            cliente = random.choice(clientes_criados)
            servico = random.choice(todos_servicos)
            
            contrato = Contrato(
                cliente_id=cliente.id,
                prestador_id=servico.prestador_id,
                servico_id=servico.id,
                status='concluido',
                data_solicitacao=datetime.utcnow() - timedelta(days=random.randint(30, 90)),
                data_aceite=datetime.utcnow() - timedelta(days=random.randint(20, 29)),
                data_inicio=datetime.utcnow() - timedelta(days=random.randint(15, 19)),
                data_conclusao=datetime.utcnow() - timedelta(days=random.randint(1, 14)),
                preco_acordado=servico.preco,
                valor_servico=servico.preco,
                mensagem_cliente=f"Preciso do serviço de {servico.titulo.lower()}."
            )
            db.session.add(contrato)
            contratos_criados.append(contrato)
        
        db.session.commit()
        print(f"  ✅ {len(contratos_criados)} contratos concluídos")
        
        # ============================================
        # 5. AVALIAÇÕES (agora ligadas aos contratos!)
        # ============================================
        print("\n⭐ Criando avaliações...")
        avs_criadas = 0
        
        for contrato in contratos_criados:
            # 70% de chance de ter avaliação
            if random.random() < 0.7:
                nota = random.choices([5, 4, 3], weights=[70, 25, 5])[0]
                comentario = random.choice(COMENTARIOS)
                
                try:
                    avaliacao = Avaliacao(
                        contrato_id=contrato.id,
                        cliente_id=contrato.cliente_id,
                        prestador_id=contrato.prestador_id,
                        servico_id=contrato.servico_id,
                        nota=nota,
                        comentario=comentario,
                        qualidade=nota,
                        pontualidade=nota,
                        comunicacao=nota,
                        preco_justo=nota,
                        data_avaliacao=contrato.data_conclusao + timedelta(days=random.randint(1, 7))
                    )
                    db.session.add(avaliacao)
                    avs_criadas += 1
                except Exception as e:
                    print(f"     ⚠️ {e}")
        
        db.session.commit()
        print(f"  ✅ {avs_criadas} avaliações criadas")
        
        # ============================================
        # 6. ASSINATURAS ATIVAS
        # ============================================
        print("\n💳 Criando assinaturas...")
        assinaturas_criadas = 0
        for prestador in random.sample(todos_prestadores, min(4, len(todos_prestadores))):
            existente = Assinatura.query.filter_by(
                prestador_id=prestador.id, status='ativa'
            ).first()
            if existente:
                continue
            
            plano = random.choice(['basico', 'pro'])
            assinatura = Assinatura(
                prestador_id=prestador.id,
                plano=plano,
                status='ativa',
                data_inicio=datetime.utcnow() - timedelta(days=random.randint(1, 20)),
                data_fim=datetime.utcnow() + timedelta(days=random.randint(10, 30)),
                ultimo_pagamento=datetime.utcnow() - timedelta(days=random.randint(1, 20))
            )
            db.session.add(assinatura)
            assinaturas_criadas += 1
        db.session.commit()
        print(f"  ✅ {assinaturas_criadas} assinaturas")
        
        # ============================================
        # RESUMO FINAL
        # ============================================
        print("\n" + "=" * 60)
        print("🎉 SEED CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        print(f"👤 Prestadores: {Usuario.query.filter(Usuario.email.like(f'{SEED_PREFIX}%')).filter_by(tipo='prestador').count()}")
        print(f"👤 Clientes: {Usuario.query.filter(Usuario.email.like(f'{SEED_PREFIX}%')).filter_by(tipo='cliente').count()}")
        print(f"🔧 Serviços: {Servico.query.count()}")
        print(f"📄 Contratos: {Contrato.query.count()}")
        print(f"⭐ Avaliações: {Avaliacao.query.count()}")
        print(f"💳 Assinaturas: {Assinatura.query.count()}")
        print("=" * 60)
        print("🔐 Senha de todos: seed123456")
        print("🗑️  Para remover: python seed_data.py --remove")


def remove_seed_data():
    with app.app_context():
        print("🗑️  Removendo dados de seed...")
        usuarios = Usuario.query.filter(Usuario.email.like(f"{SEED_PREFIX}%")).all()
        ids = [u.id for u in usuarios]
        
        if not ids:
            print("  ⚠️ Nada para remover.")
            return
        
        # Ordem importa (FK constraints)
        Avaliacao.query.filter(
            (Avaliacao.prestador_id.in_(ids)) | (Avaliacao.cliente_id.in_(ids))
        ).delete(synchronize_session=False)
        
        Contrato.query.filter(
            (Contrato.cliente_id.in_(ids)) | (Contrato.prestador_id.in_(ids))
        ).delete(synchronize_session=False)
        
        Solicitacao.query.filter(
            Solicitacao.cliente_id.in_(ids)
        ).delete(synchronize_session=False)
        
        Mensagem.query.filter(
            (Mensagem.remetente_id.in_(ids)) | (Mensagem.destinatario_id.in_(ids))
        ).delete(synchronize_session=False)
        
        Assinatura.query.filter(Assinatura.prestador_id.in_(ids)).delete(synchronize_session=False)
        Servico.query.filter(Servico.prestador_id.in_(ids)).delete(synchronize_session=False)
        
        for u in usuarios:
            db.session.delete(u)
        
        db.session.commit()
        print(f"  ✅ {len(usuarios)} usuários e dados removidos")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--remove':
        remove_seed_data()
    else:
        seed_database()