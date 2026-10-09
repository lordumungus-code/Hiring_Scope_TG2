import re


def limpar_telefone(telefone):
    if not telefone:
        return ''
    return re.sub(r'\D', '', str(telefone))


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