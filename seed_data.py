"""
Script para popular o banco de dados com dados realistas.
Executar UMA VEZ no Console do Railway com: python seed_data.py
Para remover os dados depois: python seed_data.py --remove
"""

import sys
import base64
import random
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import Usuario, Servico, Assinatura, Avaliacao, Mensagem

# ============================================
# CONFIGURAÇÕES
# ============================================
SEED_PREFIX = "seed_"  # Prefixo para identificar dados falsos
SEED_DOMAIN = "@hiring-scope.com.br"

# ============================================
# DADOS REALISTAS
# ============================================
PRESTADORES = [
    {"nome": "Carlos Silva", "email": "carlos.silva", "tel": "11987654321", "cidade": "São Paulo", "bio": "Eletricista com 15 anos de experiência"},
    {"nome": "Ana Paula Santos", "email": "ana.santos", "tel": "11976543210", "cidade": "São Paulo", "bio": "Diarista profissional e organizada"},
    {"nome": "Roberto Almeida", "email": "roberto.almeida", "tel": "11965432109", "cidade": "Campinas", "bio": "Encanador certificado 24h"},
    {"nome": "Juliana Costa", "email": "juliana.costa", "tel": "11954321098", "cidade": "São Paulo", "bio": "Designer gráfico e ilustradora"},
    {"nome": "Marcos Oliveira", "email": "marcos.oliveira", "tel": "11943210987", "cidade": "Santos", "bio": "Pintor profissional, acabamento impecável"},
    {"nome": "Patrícia Ferreira", "email": "patricia.ferreira", "tel": "11932109876", "cidade": "São Paulo", "bio": "Personal trainer e nutricionista"},
    {"nome": "Felipe Rodrigues", "email": "felipe.rodrigues", "tel": "11921098765", "cidade": "Osasco", "bio": "Técnico em informática e redes"},
    {"nome": "Camila Martins", "email": "camila.martins", "tel": "11910987654", "cidade": "São Paulo", "bio": "Manicure e pedicure profissional"},
    {"nome": "Bruno Souza", "email": "bruno.souza", "tel": "11909876543", "cidade": "Guarulhos", "bio": "Montador de móveis e marido de aluguel"},
    {"nome": "Larissa Lima", "email": "larissa.lima", "tel": "11998765432", "cidade": "São Paulo", "bio": "Professora particular de matemática"},
]

CLIENTES = [
    {"nome": "Maria Silva", "email": "maria.silva", "tel": "11988887777"},
    {"nome": "João Santos", "email": "joao.santos", "tel": "11977776666"},
    {"nome": "Fernanda Alves", "email": "fernanda.alves", "tel": "11966665555"},
    {"nome": "Pedro Costa", "email": "pedro.costa", "tel": "11955554444"},
    {"nome": "Carla Rodrigues", "email": "carla.rodrigues", "tel": "11944443333"},
    {"nome": "Lucas Pereira", "email": "lucas.pereira", "tel": "11933332222"},
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
# FUNÇÕES AUXILIARES
# ============================================
def gerar_avatar_inicial(nome):
    """Gera um placeholder usando a inicial do nome (não salva base64, só retorna None)"""
    return None  # Vamos usar a inicial no template


def seed_database():
    """Popula o banco com dados realistas"""
    with app.app_context():
        print("🌱 Iniciando seed de dados...")
        
        # ============================================
        # 1. CRIAR PRESTADORES
        # ============================================
        prestadores_criados = []
        for p in PRESTADORES:
            email = f"{SEED_PREFIX}{p['email']}{SEED_DOMAIN}"
            
            if Usuario.query.filter_by(email=email).first():
                print(f"  ⚠️ Prestador {p['nome']} já existe, pulando...")
                continue
            
            usuario = Usuario(
                nome=p['nome'],
                email=email,
                telefone=p['tel'],
                tipo='prestador',
                data_cadastro=datetime.utcnow() - timedelta(days=random.randint(30, 180))
            )
            usuario.set_password('seed123456')
            db.session.add(usuario)
            db.session.flush()
            prestadores_criados.append(usuario)
        
        db.session.commit()
        print(f"  ✅ {len(prestadores_criados)} prestadores criados")
        
        # ============================================
        # 2. CRIAR CLIENTES
        # ============================================
        clientes_criados = []
        for c in CLIENTES:
            email = f"{SEED_PREFIX}{c['email']}{SEED_DOMAIN}"
            
            if Usuario.query.filter_by(email=email).first():
                continue
            
            usuario = Usuario(
                nome=c['nome'],
                email=email,
                telefone=c['tel'],
                tipo='cliente',
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
        todos_prestadores = Usuario.query.filter(
            Usuario.email.like(f"{SEED_PREFIX}%")
        ).filter_by(tipo='prestador').all()
        
        servicos_criados = []
        for s in SERVICOS:
            prestador = random.choice(todos_prestadores)
            
            # Verifica se já existe
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
                destaque=random.choice([True, False, False]),  # ~33% em destaque
                data_postagem=datetime.utcnow() - timedelta(days=random.randint(1, 60))
            )
            db.session.add(servico)
            servicos_criados.append(servico)
        
        db.session.commit()
        print(f"  ✅ {len(servicos_criados)} serviços criados")
        
        # ============================================
        # 4. CRIAR AVALIAÇÕES
        # ============================================
        # Precisamos verificar se o modelo Avaliacao existe
        try:
            avaliacoes_criadas = 0
            todos_servicos = Servico.query.filter(
                Servico.prestador_id.in_([p.id for p in todos_prestadores])
            ).all()
            
            for servico in random.sample(todos_servicos, min(20, len(todos_servicos))):
                for _ in range(random.randint(1, 5)):
                    cliente = random.choice(clientes_criados)
                    av = AVALIACOES[random.randint(0, len(AVALIACOES) - 1)]
                    
                    # Verifica os campos do modelo
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
                    except Exception as e:
                        pass
            
            db.session.commit()
            print(f"  ✅ {avaliacoes_criadas} avaliações criadas")
        except Exception as e:
            print(f"  ⚠️ Não foi possível criar avaliações: {e}")
            print(f"     (O modelo Avaliacao pode não existir ainda)")
        
        # ============================================
        # 5. RESUMO FINAL
        # ============================================
        print("\n" + "="*50)
        print("🎉 SEED CONCLUÍDO COM SUCESSO!")
        print("="*50)
        print(f"📊 Prestadores: {Usuario.query.filter(Usuario.email.like(f'{SEED_PREFIX}%')).filter_by(tipo='prestador').count()}")
        print(f"📊 Clientes: {Usuario.query.filter(Usuario.email.like(f'{SEED_PREFIX}%')).filter_by(tipo='cliente').count()}")
        print(f"📊 Serviços: {Servico.query.filter(Servico.prestador_id.in_([p.id for p in todos_prestadores])).count()}")
        print("="*50)
        print("🔐 Senha de todos os seed: seed123456")
        print("🗑️  Para remover: python seed_data.py --remove")
        print("="*50)


def remove_seed_data():
    """Remove todos os dados de seed"""
    with app.app_context():
        print("🗑️  Removendo dados de seed...")
        
        # Buscar todos os usuários seed
        usuarios_seed = Usuario.query.filter(
            Usuario.email.like(f"{SEED_PREFIX}%")
        ).all()
        
        ids_usuarios = [u.id for u in usuarios_seed]
        
        if not ids_usuarios:
            print("  ⚠️ Nenhum dado de seed encontrado.")
            return
        
        # Remover avaliações (se existir o modelo)
        try:
            Avaliacao.query.filter(
                (Avaliacao.prestador_id.in_(ids_usuarios)) |
                (Avaliacao.cliente_id.in_(ids_usuarios))
            ).delete(synchronize_session=False)
        except:
            pass
        
        # Remover mensagens
        Mensagem.query.filter(
            (Mensagem.remetente_id.in_(ids_usuarios)) |
            (Mensagem.destinatario_id.in_(ids_usuarios))
        ).delete(synchronize_session=False)
        
        # Remover assinaturas
        Assinatura.query.filter(
            Assinatura.prestador_id.in_(ids_usuarios)
        ).delete(synchronize_session=False)
        
        # Remover serviços
        Servico.query.filter(
            Servico.prestador_id.in_(ids_usuarios)
        ).delete(synchronize_session=False)
        
        # Remover usuários
        for u in usuarios_seed:
            db.session.delete(u)
        
        db.session.commit()
        print(f"  ✅ {len(usuarios_seed)} usuários e todos os dados relacionados removidos!")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--remove':
        remove_seed_data()
    else:
        seed_database()