import re


def limpar_telefone(telefone):
    """Só os dígitos, sem o código do país (55) quando ele vier junto"""
    if not telefone:
        return ''
    digitos = re.sub(r'\D', '', str(telefone))
    # "+55 12 97408-5264" ou "5512974085264": tira o 55 e fica DDD + número
    if len(digitos) in (12, 13) and digitos.startswith('55'):
        digitos = digitos[2:]
    return digitos


def validar_telefone(telefone):
    """Retorna (valido, mensagem, telefone_limpo)"""
    if not telefone or not str(telefone).strip():
        return False, 'Telefone é obrigatório.', None

    limpo = limpar_telefone(telefone)

    if len(limpo) not in (10, 11):
        return False, 'Telefone deve ter DDD + número (10 ou 11 dígitos).', None

    ddd = int(limpo[:2])
    if ddd < 11 or ddd > 99:
        return False, 'DDD inválido.', None

    if len(limpo) == 11 and limpo[2] != '9':
        return False, 'Celular deve começar com 9 após o DDD.', None

    if len(limpo) == 10 and limpo[2] not in '2345':
        return False, 'Número de telefone fixo inválido.', None

    if len(set(limpo)) <= 2:
        return False, 'Número de telefone inválido.', None

    return True, '', limpo


def formatar_telefone(telefone_limpo):
    if not telefone_limpo:
        return ''
    if len(telefone_limpo) == 11:
        return f'({telefone_limpo[:2]}) {telefone_limpo[2:7]}-{telefone_limpo[7:]}'
    return f'({telefone_limpo[:2]}) {telefone_limpo[2:6]}-{telefone_limpo[6:]}'


def telefone_ja_existe(telefone_limpo, ignorar_usuario_id=None):
    from models import Usuario
    for u in Usuario.query.filter(Usuario.telefone.isnot(None)).all():
        if ignorar_usuario_id and u.id == ignorar_usuario_id:
            continue
        if limpar_telefone(u.telefone) == telefone_limpo:
            return True
    return False


def validar_cpf_cnpj(documento):
    """Confere os dígitos verificadores de um CPF ou CNPJ. Retorna (valido, documento_formatado)"""
    numeros = re.sub(r'\D', '', str(documento or ''))
    
    if len(numeros) == 11:
        if len(set(numeros)) == 1:
            return False, None
        for tamanho in (9, 10):
            soma = sum(int(numeros[i]) * (tamanho + 1 - i) for i in range(tamanho))
            digito = (soma * 10) % 11 % 10
            if digito != int(numeros[tamanho]):
                return False, None
        return True, f'{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}'
    
    if len(numeros) == 14:
        if len(set(numeros)) == 1:
            return False, None
        for tamanho in (12, 13):
            pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
            soma = sum(int(numeros[i]) * pesos[i] for i in range(tamanho))
            resto = soma % 11
            digito = 0 if resto < 2 else 11 - resto
            if digito != int(numeros[tamanho]):
                return False, None
        return True, f'{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}'
    
    return False, None
