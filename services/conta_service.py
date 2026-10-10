import secrets

from sqlalchemy import or_

from extensions import db
from services.moderacao_service import remover_servico
from models import (Servico, Solicitacao, Contrato, Reclamacao, Favorito, Mensagem, Assinatura,
                    PedidoOrcamento, RespostaOrcamento, InscricaoPush)


def excluir_conta(usuario):
    """Exclui a conta: apaga os dados pessoais e o conteúdo do usuário.

    O registro do usuário é mantido anonimizado ("Usuário removido") para não quebrar
    os contratos e avaliações de outras pessoas que negociaram com ele.
    """
    uid = usuario.id

    Mensagem.query.filter(
        or_(Mensagem.remetente_id == uid, Mensagem.destinatario_id == uid)
    ).delete(synchronize_session=False)
    Favorito.query.filter(
        or_(Favorito.cliente_id == uid, Favorito.prestador_id == uid)
    ).delete(synchronize_session=False)
    Reclamacao.query.filter_by(usuario_id=uid).delete(synchronize_session=False)
    InscricaoPush.query.filter_by(usuario_id=uid).delete(synchronize_session=False)
    Solicitacao.query.filter_by(cliente_id=uid).delete(synchronize_session=False)

    # Pedidos de orçamento do usuário (com as propostas recebidas) e as propostas que ele enviou
    RespostaOrcamento.query.filter_by(prestador_id=uid).delete(synchronize_session=False)
    for pedido in PedidoOrcamento.query.filter_by(cliente_id=uid).all():
        db.session.delete(pedido)

    Assinatura.query.filter_by(prestador_id=uid, status='ativa').update(
        {'status': 'cancelada'}, synchronize_session=False
    )

    # Contratos em aberto são cancelados; os concluídos ficam no histórico da outra parte
    Contrato.query.filter(
        or_(Contrato.cliente_id == uid, Contrato.prestador_id == uid),
        Contrato.status.in_(['pendente', 'aceito', 'em_andamento'])
    ).update({'status': 'cancelado'}, synchronize_session=False)

    for servico in Servico.query.filter_by(prestador_id=uid, removido=False).all():
        remover_servico(servico)

    usuario.nome = 'Usuário removido'
    usuario.email = f'removido-{uid}-{secrets.token_hex(8)}@removido.invalid'
    usuario.telefone = None
    usuario.foto_perfil = None
    usuario.foto_url = None
    usuario.descricao = None
    usuario.is_admin = False
    usuario.set_password(secrets.token_urlsafe(32))
    usuario.desativada = True
    usuario.bloqueada = False

    db.session.commit()
