import mercadopago
import os
from datetime import datetime, timedelta

# Carregar token da variável de ambiente (nunca hardcoded!)
ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')

if not ACCESS_TOKEN:
    print("⚠️ MERCADOPAGO_ACCESS_TOKEN não configurado: pagamentos de planos ficarão indisponíveis.")

sdk = mercadopago.SDK(ACCESS_TOKEN) if ACCESS_TOKEN else None


def criar_link_pagamento(plano, plano_nome, plano_valor, prestador_id, prestador_email, prestador_nome):
    """Cria um link de pagamento no Mercado Pago"""
    
    if sdk is None:
        return {'success': False, 'error': 'Mercado Pago não configurado'}
    
    print(f"💳 Criando pagamento para: {plano_nome} - R$ {plano_valor}")
    
    base_url = "https://hiring-scope.com.br"
    
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
        "notification_url": f"{base_url}/assinatura/webhook",
        "external_reference": f"prestador_{prestador_id}_{plano}"
    }
    
    try:
        print("📤 Enviando requisição para Mercado Pago...")
        
        preference = sdk.preference().create(payment_data)
        
        print(f"📦 Resposta status: {preference['status']}")
        
        if preference['status'] == 201:
            url = preference['response']['init_point']  # init_point = produção
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
    
    if sdk is None:
        return None
    
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