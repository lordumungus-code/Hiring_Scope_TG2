"""Gera o par de chaves das notificações push (VAPID).

Uso: python gerar_chaves_push.py

Rode UMA vez e guarde as duas variáveis na hospedagem (Railway > Variables).
Se você gerar chaves novas depois, todo mundo precisa ativar as notificações de novo.
A chave privada é secreta: não coloque no git nem compartilhe.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b'=').decode('ascii')


chave = ec.generate_private_key(ec.SECP256R1())
privada = chave.private_numbers().private_value.to_bytes(32, 'big')
publica = chave.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
)

print('Adicione estas duas variáveis na hospedagem (e no .env local, se quiser testar no seu computador):')
print()
print(f'VAPID_PUBLIC_KEY={b64url(publica)}')
print(f'VAPID_PRIVATE_KEY={b64url(privada)}')
