import mercadopago
import os
from datetime import datetime, timedelta

# Carregar token da variável de ambiente (nunca hardcoded!)
ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')

if not ACCESS_TOKEN:
    print("⚠️ MERCADOPAGO_ACCESS_TOKEN não configurado: pagamentos de planos ficarão indisponíveis.")

sdk = mercadopago.SDK(ACCESS_TOKEN) if ACCESS_TOKEN else None


BASE_URL = "https://hiring-scope.com.br"


def criar_preferencia(titulo, descricao, valor, email, nome, referencia, retorno):
    """Cria um link de pagamento no Mercado Pago.
    
    referencia: identifica o que está sendo pago (volta no pagamento como external_reference)
    retorno: caminhos do site para onde o Mercado Pago devolve o usuário
             ({'success': ..., 'failure': ..., 'pending': ...})
    """
    
    if sdk is None:
        return {'success': False, 'error': 'Mercado Pago não configurado'}
    
    print(f"💳 Criando pagamento para: {titulo} - R$ {valor}")
    
    payment_data = {
        "items": [
            {
                "title": titulo,
                "description": descricao,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": valor
            }
        ],
        "payer": {
            "email": email,
            "name": nome
        },
        "back_urls": {chave: f"{BASE_URL}{caminho}" for chave, caminho in retorno.items()},
        "notification_url": f"{BASE_URL}/assinatura/webhook",
        "external_reference": referencia
    }
    
    try:
        preference = sdk.preference().create(payment_data)
        
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


def criar_link_pagamento(plano, plano_nome, plano_valor, prestador_id, prestador_email, prestador_nome):
    """Cria o link de pagamento de um plano de destaque"""
    return criar_preferencia(
        titulo=f"Assinatura {plano_nome} - HiringScope",
        descricao=f"Acesso ao plano {plano_nome} por 30 dias",
        valor=plano_valor,
        email=prestador_email,
        nome=prestador_nome,
        referencia=f"prestador_{prestador_id}_{plano}",
        retorno={
            'success': '/assinatura/sucesso',
            'failure': '/assinatura/erro',
            'pending': '/assinatura/pendente'
        }
    )

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