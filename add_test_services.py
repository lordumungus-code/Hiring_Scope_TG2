# add_test_services_icons.py
import sys
import os
from datetime import datetime, timedelta
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Usuario, Servico

# Serviços reais para teste
SERVICOS_REAIS = [
    ("Marketing Digital", "Estratégias para aumentar suas vendas online", 300.00, 'Marketing'),
    ("Limpeza de Ar Condicionado", "Limpeza completa de ar condicionado", 120.00, 'Limpeza'),
    ("Personal Trainer", "Treinos personalizados em domicílio", 80.00, 'hora', 'Saúde'),
    ("Pintura de Apartamento", "Pintura completa até 70m²", 1500.00, 'Construção'),
    ("Instalação de Câmeras", "Sistemas de segurança residencial", 200.00, 'Construção'),
    ("Encanador", "Reparos hidráulicos e desentupimento", 90.00, 'hora', 'Construção'),
    ("Manicure", "Serviços de unhas em domicílio", 40.00, 'Beleza'),
    ("DJ para Festas", "Música e animação para seu evento", 500.00, 'Eventos'),
    ("Aulas de Matemática", "Aulas particulares de matemática", 50.00, 'hora', 'Educação'),
    ("Desenvolvimento Web", "Criação de sites profissionais", 2000.00, 'Tecnologia'),
    ("Fotografia", "Ensaios fotográficos e eventos", 250.00, 'Eventos'),
    ("Jardinagem", "Cuidados com jardins e poda", 80.00, 'hora', 'Serviços Gerais'),
    ("Dedetização", "Controle de pragas urbanas", 120.00, 'Limpeza'),
    ("Conserto de Computadores", "Manutenção e reparo de PCs", 60.00, 'hora', 'Tecnologia'),
    ("Massoterapia", "Massagem relaxante e terapêutica", 100.00, 'hora', 'Saúde'),
    ("Revisão de Textos", "Correção de textos acadêmicos", 0.05, 'metro', 'Educação'),
    ("Organização de Festas", "Planejamento de eventos", 500.00, 'Eventos'),
    ("Venda de Bolos", "Bolos caseiros para festas", 50.00, 'Eventos'),
    ("Babá", "Cuidado infantil com segurança", 25.00, 'hora', 'Serviços Gerais'),
    ("Passeador de Cães", "Passeios diários com seu pet", 30.00, 'hora', 'Serviços Gerais'),
    ("Design de Interiores", "Projeto de decoração", 500.00, 'Design'),
    ("Tradução de Documentos", "Tradução inglês-português", 0.10, 'metro', 'Educação'),
]

def criar_servicos():
    with app.app_context():
        prestador = Usuario.query.filter_by(tipo='prestador').first()
        
        if not prestador:
            prestador = Usuario(
                nome="Prestador Master",
                email="prestador_master@email.com",
                telefone="11999997777",
                tipo="prestador",
                descricao="Profissional experiente com mais de 10 anos de mercado."
            )
            prestador.set_password("123456")
            db.session.add(prestador)
            db.session.commit()
            print("✅ Prestador master criado!")
            print("   Email: prestador_master@email.com / Senha: 123456")
        
        # Limpar serviços antigos
        servicos_existentes = Servico.query.count()
        if servicos_existentes > 0:
            print(f"📌 Removendo {servicos_existentes} serviços antigos...")
            Servico.query.delete()
            db.session.commit()
        
        servicos_para_criar = []
        
        print(f"\n📌 Criando serviços...")
        
        for i in range(100):
            servico_base = SERVICOS_REAIS[i % len(SERVICOS_REAIS)]
            
            if len(servico_base) == 4:
                titulo, descricao, preco, categoria = servico_base
                tipo_preco = 'fixo'
            elif len(servico_base) == 5:
                titulo, descricao, preco, tipo_preco, categoria = servico_base
            else:
                continue
            
            servico = Servico(
                prestador_id=prestador.id,
                titulo=f"{titulo}",
                descricao=f"{descricao} ✅ Atendimento com qualidade e pontualidade.",
                categoria=categoria,
                tipo_preco=tipo_preco,
                preco=preco if tipo_preco != 'consulta' else None,
                destaque=i < 10,
                destaque_pago=i < 5,
                data_postagem=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
                imagem_base64=None  # Sem imagem, vai mostrar ícone
            )
            servicos_para_criar.append(servico)
            
            if (i + 1) % 20 == 0:
                print(f"   ✅ {i+1} serviços criados...")
        
        db.session.add_all(servicos_para_criar)
        db.session.commit()
        
        print(f"\n✅ SUCESSO! {len(servicos_para_criar)} serviços criados!")
        
        # Estatísticas
        categorias = {}
        for s in servicos_para_criar:
            categorias[s.categoria] = categorias.get(s.categoria, 0) + 1
        
        print(f"\n📊 SERVIÇOS POR CATEGORIA:")
        for cat, qtd in sorted(categorias.items(), key=lambda x: x[1], reverse=True):
            print(f"   {cat}: {qtd} serviços")
        
        return True

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SCRIPT PARA ADICIONAR 100 SERVIÇOS")
    print("=" * 60)
    
    criar_servicos()
    
    print("\n" + "=" * 60)
    print("✨ FINALIZADO! Acesse http://localhost:5000")
    print("=" * 60)