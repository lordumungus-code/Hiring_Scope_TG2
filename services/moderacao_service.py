"""Ações de moderação usadas pelo painel do administrador (e pela exclusão de conta)."""
from extensions import db
from models import Contrato, Solicitacao


def remover_servico(servico):
    """Tira um serviço do ar. Não faz commit.

    - Sem histórico de contratação: é apagado de vez (com fotos e solicitações antigas).
    - Com contratos: fica marcado como removido e some de todo o site, mas o registro é mantido
      para que os contratos e as avaliações de quem já contratou não se percam.

    Retorna 'apagado' ou 'oculto'.
    """
    Solicitacao.query.filter_by(servico_id=servico.id).delete(synchronize_session=False)

    if Contrato.query.filter_by(servico_id=servico.id).count() == 0:
        db.session.delete(servico)
        return 'apagado'

    # Pedidos que o prestador ainda nem respondeu deixam de fazer sentido
    Contrato.query.filter_by(servico_id=servico.id, status='pendente').update(
        {'status': 'cancelado'}, synchronize_session=False
    )
    servico.removido = True
    servico.destaque = False
    servico.destaque_pago = False
    servico.destaque_data_fim = None
    servico.imagem_base64 = None
    servico.imagens_extras.clear()
    return 'oculto'


def bloquear_usuario(usuario):
    """Impede o login e tira o perfil e os serviços do ar, sem apagar nada. Não faz commit."""
    usuario.bloqueada = True
    usuario.desativada = True   # é o que esconde o perfil e os serviços e derruba as sessões abertas


def desbloquear_usuario(usuario):
    usuario.bloqueada = False
    usuario.desativada = False
