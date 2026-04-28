import mercadopago
import os
from datetime import datetime, timedelta

# Carregar token
ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')

# Se não encontrar no .env, use o token direto (temporário para teste)
if not ACCESS_TOKEN:
    print("⚠️ Token não encontrado no .env, usando token fixo para teste")
    ACCESS_TOKEN = "APP_USR-1764446428749041-042723-deaf7c37e3850f1108698bb01ddc343a-3364931912"

print(f"🔑 Usando token: {ACCESS_TOKEN[:30]}...")

sdk = mercadopago.SDK(ACCESS_TOKEN)


def criar_link_pagamento(plano_nome, plano_valor, prestador_id, prestador_email, prestador_nome):
    """Cria um link de pagamento no Mercado Pago"""
    
    print(f"💳 Criando pagamento para: {plano_nome} - R$ {plano_valor}")
    
    # URLs de retorno
    base_url = "https://localhost:5000"  # Mude para HTTPS ou remova a URL de notificação
    
    # Dados do pagamento (sem notification_url)
    payment_data = {
        "items": [
            {
                "title": f"Assinatura {plano_nome} - HiringScope",
                "description": f"Acesso ao plano {plano_nome} por 30 dias",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": plano_valor
            }
        ],
        "payer": {
            "email": prestador_email,
            "name": prestador_nome
        },
        "back_urls": {
            "success": f"{base_url}/assinatura/sucesso",
            "failure": f"{base_url}/assinatura/erro",
            "pending": f"{base_url}/assinatura/pendente"
        },
        "external_reference": f"prestador_{prestador_id}_{plano_nome.lower()}"
        # notification_url removido - causa problema em localhost
    }
    
    try:
        print("📤 Enviando requisição para Mercado Pago...")
        
        preference = sdk.preference().create(payment_data)
        
        print(f"📦 Resposta status: {preference['status']}")
        
        if preference['status'] == 201:
            url = preference['response']['init_point']
            print(f"✅ Link gerado: {url}")
            return {
                'success': True,
                'url': url,
                'id': preference['response']['id']
            }
        else:
            print(f"❌ Erro: {preference}")
            return {'success': False, 'error': f'Erro {preference["status"]}'}
            
    except Exception as e:
        print(f"❌ Exceção: {e}")
        return {'success': False, 'error': str(e)}

def verificar_pagamento(payment_id):
    """Verifica o status de um pagamento no Mercado Pago"""
    
    print(f"🔍 Verificando pagamento: {payment_id}")
    
    try:
        payment = sdk.payment().get(payment_id)
        if payment['status'] == 200:
            return payment['response']
        else:
            print(f"❌ Erro ao verificar: {payment}")
            return None
    except Exception as e:
        print(f"❌ Exceção ao verificar: {e}")
        return None


def criar_simulacao(plano_nome, prestador_id):
    """Cria link de simulação para testes"""
    print(f"🔧 Usando modo SIMULAÇÃO para {plano_nome}")
    return {
        'success': True,
        'url': f"/assinatura/simular?plano={plano_nome.lower()}&prestador={prestador_id}",
        'id': f"simulacao_{prestador_id}_{plano_nome}"
    }