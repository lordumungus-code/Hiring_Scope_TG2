from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, Response, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import secrets

from extensions import db, limiter, socketio
from models import Contrato, ContratoFormal
from services.mercado_pago_service import criar_preferencia, verificar_pagamento
from services.email_service import enviar_email
from services import contrato_formal_service as servico_formal
from services.contrato_formal_service import PRECO_CONTRATO_FORMAL, VALIDADE_CODIGO, MAX_TENTATIVAS_CODIGO
from utils.validators import validar_cpf_cnpj

formal_bp = Blueprint('contrato_formal', __name__, url_prefix='/contrato')


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def obter_contrato(contrato_id, papeis=('prestador', 'cliente', 'admin')):
    """Retorna (contrato, papel do usuário logado). 404 para quem não participa do contrato."""
    contrato = Contrato.query.get_or_404(contrato_id)

    if current_user.id == contrato.prestador_id:
        papel = 'prestador'
    elif current_user.id == contrato.cliente_id:
        papel = 'cliente'
    elif current_user.is_admin:
        papel = 'admin'   # só leitura
    else:
        abort(404)

    if papel not in papeis:
        abort(403)
    return contrato, papel


def pagina(contrato_id):
    return redirect(url_for('contrato_formal.ver', contrato_id=contrato_id))


def limpar_assinaturas(formal):
    for parte in ('cliente', 'prestador'):
        setattr(formal, f'{parte}_assinou_em', None)
        setattr(formal, f'{parte}_ip', None)
        setattr(formal, f'{parte}_dispositivo', None)
        setattr(formal, f'{parte}_codigo_hash', None)
        setattr(formal, f'{parte}_codigo_expira', None)
        setattr(formal, f'{parte}_codigo_tentativas', 0)


def avisar(usuario_id, titulo, mensagem):
    """Aviso em tempo real para a outra parte (aparece como notificação no site)"""
    socketio.emit('notification', {'titulo': titulo, 'mensagem': mensagem}, room=f'user_{usuario_id}')


def numero_valido(texto, maximo):
    """Lê um valor em reais ou percentual do formulário; None se inválido"""
    try:
        valor = float(str(texto or '0').replace(',', '.'))
    except ValueError:
        return None
    return valor if 0 <= valor <= maximo else None


# ============================================
# PÁGINA DO CONTRATO FORMAL
# ============================================

@formal_bp.route('/formal/<int:contrato_id>')
@login_required
def ver(contrato_id):
    contrato, papel = obter_contrato(contrato_id)
    formal = contrato.formal

    termos = servico_formal.carregar_termos(formal) if formal else {}
    if formal and formal.status == 'rascunho':
        # Enquanto é rascunho, nome/e-mail/telefone acompanham o cadastro
        termos['contratante'] = servico_formal.dados_da_parte(contrato.cliente, termos.get('contratante'))
        termos['contratado'] = servico_formal.dados_da_parte(contrato.prestador, termos.get('contratado'))

    return render_template(
        'contratos/formal.html',
        contrato=contrato,
        formal=formal,
        papel=papel,
        termos=termos,
        clausulas=servico_formal.montar_clausulas(termos) if termos else [],
        pendencias=servico_formal.pendencias(termos) if termos else [],
        assinaturas=servico_formal.assinaturas(formal) if formal else [],
        preco=PRECO_CONTRATO_FORMAL,
        pode_iniciar=contrato.status in ('aceito', 'em_andamento'),
        formas_pagamento=servico_formal.FORMAS_PAGAMENTO,
        validade_codigo=VALIDADE_CODIGO,
        brl=servico_formal.brl,
        data_br=servico_formal.data_br,
        horario_brasilia=servico_formal.horario_brasilia,
        descricao_da_parte=servico_formal.descricao_da_parte
    )


# ============================================
# PAGAMENTO DA TAXA (prestador)
# ============================================

@formal_bp.route('/formal/<int:contrato_id>/pagar', methods=['POST'])
@login_required
def pagar(contrato_id):
    contrato, _ = obter_contrato(contrato_id, papeis=('prestador',))

    if contrato.status not in ('aceito', 'em_andamento'):
        flash('O contrato formal só pode ser gerado depois de aceitar o serviço e antes de concluí-lo.', 'warning')
        return pagina(contrato_id)

    formal = contrato.formal
    if formal and formal.pago_em:
        return pagina(contrato_id)

    if not formal:
        formal = ContratoFormal(contrato_id=contrato.id, status='aguardando_pagamento')
        db.session.add(formal)
        db.session.flush()
        formal.numero = f'HS-{datetime.utcnow().year}-{formal.id:05d}'
        db.session.commit()

    retorno = f'/contrato/formal/{contrato.id}/pagamento'
    resultado = criar_preferencia(
        titulo=f'Contrato formal nº {formal.numero} - HiringScope',
        descricao=f'Contrato com assinatura eletrônica para o serviço "{contrato.servico.titulo[:80]}"',
        valor=PRECO_CONTRATO_FORMAL,
        email=current_user.email,
        nome=current_user.nome,
        referencia=f'contrato_{contrato.id}',
        retorno={'success': retorno, 'failure': retorno, 'pending': retorno}
    )

    if resultado and resultado.get('success') and resultado.get('url'):
        return redirect(resultado['url'])

    print(f"❌ Erro no pagamento do contrato formal: {resultado}")
    flash('Erro ao criar o link de pagamento. Tente novamente.', 'danger')
    return pagina(contrato_id)


@formal_bp.route('/formal/<int:contrato_id>/pagamento')
@login_required
def retorno_pagamento(contrato_id):
    """Volta do Mercado Pago: o contrato só é liberado se o pagamento for confirmado"""
    obter_contrato(contrato_id, papeis=('prestador',))

    payment_id = request.args.get('payment_id') or request.args.get('collection_id')
    resultado = confirmar_pagamento_contrato(payment_id, contrato_id_esperado=contrato_id) if payment_id else 'invalido'

    if resultado in ('liberado', 'ja_processado'):
        flash('✅ Pagamento confirmado! Agora preencha as condições do contrato.', 'success')
    elif resultado == 'pendente':
        flash('Seu pagamento está em análise. O contrato será liberado assim que for aprovado.', 'info')
    else:
        flash('Não foi possível confirmar o pagamento. Se você já pagou, o contrato será liberado assim que o Mercado Pago confirmar.', 'warning')

    return pagina(contrato_id)


def confirmar_pagamento_contrato(payment_id, contrato_id_esperado=None):
    """Consulta o pagamento no Mercado Pago e libera o contrato formal se estiver aprovado.

    Retorna 'liberado', 'ja_processado', 'pendente' ou 'invalido'.
    """
    payment = verificar_pagamento(payment_id)
    if not payment:
        return 'invalido'

    status = payment.get('status')
    if status in ('pending', 'in_process'):
        return 'pendente'
    if status != 'approved':
        return 'invalido'

    # external_reference = contrato_<id do contrato>
    parts = (payment.get('external_reference') or '').split('_')
    if len(parts) != 2 or parts[0] != 'contrato' or not parts[1].isdigit():
        return 'invalido'

    contrato_id = int(parts[1])
    if contrato_id_esperado is not None and contrato_id != contrato_id_esperado:
        return 'invalido'
    if float(payment.get('transaction_amount') or 0) + 0.01 < PRECO_CONTRATO_FORMAL:
        return 'invalido'

    formal = ContratoFormal.query.filter_by(contrato_id=contrato_id).first()
    if not formal:
        return 'invalido'
    if formal.pago_em:
        return 'ja_processado'

    formal.pagamento_id = str(payment_id)
    formal.pago_em = datetime.utcnow()
    formal.status = 'rascunho'
    formal.termos_json = json.dumps(servico_formal.termos_iniciais(formal.contrato), ensure_ascii=False)
    db.session.commit()
    return 'liberado'


# ============================================
# CONDIÇÕES DO CONTRATO (prestador)
# ============================================

@formal_bp.route('/formal/<int:contrato_id>/termos', methods=['POST'])
@login_required
def salvar_termos(contrato_id):
    contrato, _ = obter_contrato(contrato_id, papeis=('prestador',))
    formal = contrato.formal

    if not formal or formal.status != 'rascunho':
        flash('Este contrato não está em edição.', 'warning')
        return pagina(contrato_id)

    termos = servico_formal.carregar_termos(formal)
    for campo, tamanho in servico_formal.CAMPOS_TERMOS.items():
        termos[campo] = request.form.get(campo, '').strip()[:tamanho]
    if termos['forma_pagamento'] not in servico_formal.FORMAS_PAGAMENTO:
        termos['forma_pagamento'] = 'A combinar'

    erros = []
    for campo, rotulo, maximo in (('valor_total', 'Valor total', 10_000_000), ('entrada', 'Sinal', 10_000_000), ('multa', 'Multa', 100)):
        valor = numero_valido(request.form.get(campo), maximo)
        if valor is None:
            erros.append(f'{rotulo} inválido.')
        else:
            termos[campo] = valor
    if not erros and termos['entrada'] > termos['valor_total']:
        erros.append('O sinal não pode ser maior que o valor total.')

    # Nome, e-mail e telefone vêm do cadastro; CPF e endereço do prestador vêm deste formulário
    termos['contratante'] = servico_formal.dados_da_parte(contrato.cliente, termos.get('contratante'))
    termos['contratado'] = servico_formal.dados_da_parte(contrato.prestador, termos.get('contratado'))
    termos['contratado']['endereco'] = request.form.get('contratado_endereco', '').strip()[:300]

    doc = request.form.get('contratado_doc', '').strip()
    if doc:
        valido, doc_formatado = validar_cpf_cnpj(doc)
        if valido:
            termos['contratado']['doc'] = doc_formatado
        else:
            erros.append('CPF ou CNPJ inválido.')
    else:
        termos['contratado']['doc'] = ''

    formal.termos_json = json.dumps(termos, ensure_ascii=False)
    enviar = request.form.get('acao') == 'enviar'

    faltando = servico_formal.pendencias(termos) if enviar else []
    if erros or faltando:
        db.session.commit()   # o que já foi digitado fica salvo
        for erro in erros:
            flash(erro, 'danger')
        if faltando:
            flash('Para enviar o contrato, falta preencher: ' + ', '.join(faltando) + '.', 'danger')
        return pagina(contrato_id)

    if enviar:
        formal.status = 'aguardando_assinaturas'
        formal.motivo_reabertura = None
        limpar_assinaturas(formal)
        db.session.commit()
        avisar(contrato.cliente_id, 'Contrato para assinar',
               f'{contrato.prestador.nome} enviou o contrato do serviço "{contrato.servico.titulo}" para sua assinatura.')
        flash('Contrato enviado! Agora você e o cliente podem assinar.', 'success')
    else:
        db.session.commit()
        flash('Rascunho salvo.', 'success')

    return pagina(contrato_id)


@formal_bp.route('/formal/<int:contrato_id>/reabrir', methods=['POST'])
@login_required
def reabrir(contrato_id):
    """Qualquer das partes pode pedir alteração antes de as duas assinarem; as assinaturas já feitas são desfeitas"""
    contrato, papel = obter_contrato(contrato_id, papeis=('prestador', 'cliente'))
    formal = contrato.formal

    if not formal or formal.status != 'aguardando_assinaturas':
        flash('Este contrato não pode mais ser alterado.', 'warning')
        return pagina(contrato_id)

    motivo = request.form.get('motivo', '').strip()[:1000]
    if papel == 'cliente' and not motivo:
        flash('Explique ao prestador o que precisa ser alterado.', 'danger')
        return pagina(contrato_id)

    formal.status = 'rascunho'
    formal.motivo_reabertura = f'{current_user.nome}: {motivo}' if motivo else None
    limpar_assinaturas(formal)
    db.session.commit()

    if papel == 'cliente':
        avisar(contrato.prestador_id, 'Alteração pedida no contrato', f'{current_user.nome} pediu uma alteração: {motivo[:120]}')
        flash('Pedido de alteração enviado ao prestador.', 'success')
    else:
        avisar(contrato.cliente_id, 'Contrato em alteração', f'{current_user.nome} reabriu o contrato para fazer alterações.')
        flash('Contrato reaberto para edição. As assinaturas feitas foram desfeitas.', 'info')
    return pagina(contrato_id)


# ============================================
# ASSINATURA ELETRÔNICA (senha + código por e-mail)
# ============================================

@formal_bp.route('/formal/<int:contrato_id>/codigo', methods=['POST'])
@login_required
@limiter.limit('5 per minute')
def enviar_codigo(contrato_id):
    contrato, papel = obter_contrato(contrato_id, papeis=('prestador', 'cliente'))
    formal = contrato.formal

    if not formal or formal.status != 'aguardando_assinaturas':
        return jsonify({'erro': 'Este contrato não está aguardando assinaturas.'}), 400
    if getattr(formal, f'{papel}_assinou_em'):
        return jsonify({'erro': 'Você já assinou este contrato.'}), 400

    codigo = f'{secrets.randbelow(1_000_000):06d}'
    setattr(formal, f'{papel}_codigo_hash', generate_password_hash(codigo))
    setattr(formal, f'{papel}_codigo_expira', datetime.utcnow() + timedelta(minutes=VALIDADE_CODIGO))
    setattr(formal, f'{papel}_codigo_tentativas', 0)
    db.session.commit()

    enviado = enviar_email(
        current_user.email,
        f'Código para assinar o contrato {formal.numero} - HiringScope',
        render_template('emails/codigo_assinatura.html', usuario=current_user, formal=formal,
                        codigo=codigo, validade=VALIDADE_CODIGO, servico=contrato.servico.titulo)
    )

    if not enviado:
        if current_app.debug:
            # Desenvolvimento local sem e-mail configurado: o código sai no terminal
            print(f"🔑 Código de assinatura para {current_user.email}: {codigo}")
            return jsonify({'sucesso': True, 'mensagem': 'Modo local: o código foi impresso no terminal do servidor.'})
        return jsonify({'erro': 'Não foi possível enviar o código por e-mail agora. Tente novamente em instantes.'}), 503

    return jsonify({'sucesso': True, 'mensagem': f'Código enviado para {current_user.email}. Vale por {VALIDADE_CODIGO} minutos.'})


@formal_bp.route('/formal/<int:contrato_id>/assinar', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def assinar(contrato_id):
    contrato, papel = obter_contrato(contrato_id, papeis=('prestador', 'cliente'))
    formal = contrato.formal

    if not formal or formal.status != 'aguardando_assinaturas':
        flash('Este contrato não está aguardando assinaturas.', 'warning')
        return pagina(contrato_id)
    if getattr(formal, f'{papel}_assinou_em'):
        flash('Você já assinou este contrato.', 'info')
        return pagina(contrato_id)

    termos = servico_formal.carregar_termos(formal)

    # O cliente informa o próprio CPF e endereço no momento em que assina
    if papel == 'cliente':
        valido, doc_formatado = validar_cpf_cnpj(request.form.get('doc', ''))
        endereco = request.form.get('endereco', '').strip()[:300]
        if not valido:
            flash('CPF ou CNPJ inválido.', 'danger')
            return pagina(contrato_id)
        if not endereco:
            flash('Informe seu endereço.', 'danger')
            return pagina(contrato_id)

    if not current_user.check_password(request.form.get('senha', '')):
        flash('Senha incorreta.', 'danger')
        return pagina(contrato_id)

    codigo_hash = getattr(formal, f'{papel}_codigo_hash')
    expira = getattr(formal, f'{papel}_codigo_expira')
    tentativas = getattr(formal, f'{papel}_codigo_tentativas') or 0

    if not codigo_hash or not expira or expira < datetime.utcnow():
        flash('Peça um código novo: o anterior não existe ou já expirou.', 'danger')
        return pagina(contrato_id)
    if tentativas >= MAX_TENTATIVAS_CODIGO:
        flash('Muitas tentativas com código errado. Peça um código novo.', 'danger')
        return pagina(contrato_id)
    if not check_password_hash(codigo_hash, request.form.get('codigo', '').strip()):
        setattr(formal, f'{papel}_codigo_tentativas', tentativas + 1)
        db.session.commit()
        flash('Código incorreto.', 'danger')
        return pagina(contrato_id)

    if papel == 'cliente':
        termos['contratante']['doc'] = doc_formatado
        termos['contratante']['endereco'] = endereco
        formal.termos_json = json.dumps(termos, ensure_ascii=False)

    setattr(formal, f'{papel}_assinou_em', datetime.utcnow())
    setattr(formal, f'{papel}_ip', (request.remote_addr or '')[:60])
    setattr(formal, f'{papel}_dispositivo', (request.user_agent.string or '')[:300])
    setattr(formal, f'{papel}_codigo_hash', None)   # o código só vale uma vez
    setattr(formal, f'{papel}_codigo_expira', None)

    if formal.cliente_assinou_em and formal.prestador_assinou_em:
        # As duas partes assinaram: o documento é selado e não muda mais
        formal.status = 'assinado'
        formal.selado_em = datetime.utcnow()
        formal.hash_documento = servico_formal.calcular_hash(formal)
        db.session.commit()
        enviar_contrato_assinado(contrato, formal)
        flash('✅ Contrato assinado pelas duas partes! O PDF está disponível e foi enviado por e-mail.', 'success')
    else:
        db.session.commit()
        outra_parte = contrato.cliente_id if papel == 'prestador' else contrato.prestador_id
        avisar(outra_parte, 'Contrato assinado', f'{current_user.nome} assinou o contrato. Falta a sua assinatura.')
        flash('Sua assinatura foi registrada. Falta a outra parte assinar.', 'success')

    return pagina(contrato_id)


def enviar_contrato_assinado(contrato, formal):
    """Manda o PDF assinado por e-mail para as duas partes (se o e-mail falhar, o PDF continua no site)"""
    try:
        pdf = servico_formal.gerar_pdf(formal)
        link = f"{servico_formal.site_url()}{url_for('contrato_formal.ver', contrato_id=contrato.id)}"
        for usuario in (contrato.cliente, contrato.prestador):
            enviar_email(
                usuario.email,
                f'Contrato {formal.numero} assinado - HiringScope',
                render_template('emails/contrato_assinado.html', usuario=usuario, formal=formal,
                                servico=contrato.servico.titulo, link=link,
                                verificar=f"{servico_formal.site_url()}/contrato/verificar"),
                anexos=[(f'contrato-{formal.numero}.pdf', pdf)]
            )
    except Exception as e:
        print(f"❌ Erro ao enviar contrato assinado: {e}")


# ============================================
# PDF E VERIFICAÇÃO
# ============================================

@formal_bp.route('/formal/<int:contrato_id>/pdf')
@login_required
def pdf(contrato_id):
    contrato, _ = obter_contrato(contrato_id)
    formal = contrato.formal

    if not formal or formal.status not in ('aguardando_assinaturas', 'assinado'):
        abort(404)

    resposta = Response(servico_formal.gerar_pdf(formal), mimetype='application/pdf')
    disposicao = 'attachment' if request.args.get('baixar') else 'inline'
    resposta.headers['Content-Disposition'] = f'{disposicao}; filename="contrato-{formal.numero}.pdf"'
    resposta.headers['Cache-Control'] = 'private, no-store'
    return resposta


@formal_bp.route('/verificar', methods=['GET', 'POST'])
@formal_bp.route('/verificar/<codigo>')
@limiter.limit('20 per minute')
def verificar(codigo=None):
    """Página pública: confere se um hash corresponde a um contrato assinado na plataforma"""
    codigo = (codigo or request.form.get('hash') or '').strip().lower()
    formal = None
    integro = False

    if codigo:
        formal = ContratoFormal.query.filter_by(hash_documento=codigo, status='assinado').first()
        if formal:
            # Recalcula o hash a partir do que está guardado: se alguém alterou o registro, não bate
            integro = servico_formal.calcular_hash(formal) == formal.hash_documento

    return render_template(
        'contratos/verificar.html',
        codigo=codigo,
        formal=formal,
        integro=integro,
        termos=servico_formal.carregar_termos(formal) if formal else {},
        assinaturas=servico_formal.assinaturas(formal) if formal else [],
        horario_brasilia=servico_formal.horario_brasilia
    )
