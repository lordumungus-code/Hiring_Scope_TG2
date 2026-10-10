from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user
from extensions import db, limiter
from models import Servico, ServicoImagem, Usuario, Solicitacao, Assinatura, servicos_visiveis
from utils.imagens import processar_imagem
from sqlalchemy import or_, func
import base64
from datetime import datetime, timedelta

servico_bp = Blueprint('servico', __name__, url_prefix='/servico')

MAX_FOTOS_SERVICO = 6
GEMINI_MODEL = 'gemini-3.8-flash'


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def get_assinatura_ativa(prestador_id):
    """Retorna a assinatura ativa (e dentro da validade) do prestador, ou None"""
    assinatura = Assinatura.query.filter_by(
        prestador_id=prestador_id,
        status='ativa'
    ).first()
    return assinatura if assinatura and assinatura.is_ativa() else None


def adicionar_fotos(servico, arquivos):
    """Processa as imagens enviadas e adiciona ao serviço, respeitando o limite de fotos.
    
    A primeira foto vira a capa (imagem_base64); as demais vão para imagens_extras.
    Retorna (quantas foram adicionadas, quantas foram ignoradas).
    """
    adicionadas = ignoradas = 0
    total = len(servico.fotos())
    proxima_ordem = max([img.ordem or 0 for img in servico.imagens_extras], default=0) + 1
    
    for arquivo in arquivos:
        if not arquivo or arquivo.filename == '':
            continue
        if total >= MAX_FOTOS_SERVICO:
            ignoradas += 1
            continue
        
        imagem = processar_imagem(arquivo)
        if not imagem:
            ignoradas += 1
            continue
        
        if not servico.imagem_base64:
            servico.imagem_base64 = imagem
        else:
            servico.imagens_extras.append(ServicoImagem(imagem_base64=imagem, ordem=proxima_ordem))
            proxima_ordem += 1
        total += 1
        adicionadas += 1
    
    return adicionadas, ignoradas


def parse_preco(valor):
    """Converte o preço do formulário em float; None se vazio ou inválido"""
    try:
        preco = float(str(valor).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return preco if 0 < preco < 10_000_000 else None


def get_limite_destaques(assinatura):
    """Retorna o limite de destaques conforme o plano"""
    if not assinatura:
        return 0
    return 1 if assinatura.plano == 'basico' else 3


def get_total_destaques(prestador_id, ignorar_servico_id=None):
    """Conta quantos serviços em destaque o prestador já tem"""
    query = Servico.query.filter_by(prestador_id=prestador_id, destaque=True)
    if ignorar_servico_id:
        query = query.filter(Servico.id != ignorar_servico_id)
    return query.count()


# ============================================
# ROTAS DE SERVIÇOS
# ============================================

@servico_bp.route('/cadastro', methods=['GET', 'POST'])
@login_required
def cadastro():
    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem cadastrar serviços', 'danger')
        return redirect(url_for('main.index'))
    
    # Verifica a assinatura ativa e os destaques atuais
    assinatura_ativa = get_assinatura_ativa(current_user.id)
    servicos_em_destaque = Servico.query.filter_by(
        prestador_id=current_user.id,
        destaque=True
    ).all()
    limite_plano = get_limite_destaques(assinatura_ativa)
    
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        categoria = request.form.get('categoria')
        tipo_preco = request.form.get('tipo_preco', 'fixo')
        preco = request.form.get('preco')
        quer_destaque = request.form.get('destaque') == 'on'
        
        # Sem preço válido, o serviço fica como "a combinar" (evita preço vazio nas telas)
        preco = parse_preco(preco) if tipo_preco != 'consulta' else None
        if tipo_preco != 'consulta' and preco is None:
            tipo_preco = 'consulta'
            flash('Preço não informado ou inválido: o serviço foi salvo como "A combinar".', 'warning')
        
        # === VALIDAÇÃO DE DESTAQUE NO BACKEND ===
        if quer_destaque:
            if not assinatura_ativa:
                flash('Você precisa de um plano de destaque para destacar serviços.', 'warning')
                quer_destaque = False
            elif len(servicos_em_destaque) >= limite_plano:
                flash(f'Você já atingiu o limite de {limite_plano} destaque(s) do plano {assinatura_ativa.plano.capitalize()}.', 'warning')
                quer_destaque = False
        

        # Cria o serviço
        novo_servico = Servico(
            prestador_id=current_user.id,
            titulo=titulo,
            descricao=descricao,
            categoria=categoria,
            tipo_preco=tipo_preco,
            preco=preco,
            destaque=quer_destaque,
            data_postagem=datetime.utcnow()
        )
        
        # Se foi destacado com sucesso, marca como destaque pago também
        if quer_destaque:
            novo_servico.destaque_pago = True
            novo_servico.plano_destaque = assinatura_ativa.plano
            if assinatura_ativa.data_fim:
                novo_servico.destaque_data_fim = assinatura_ativa.data_fim
        
        # Fotos (a primeira é a capa)
        _, fotos_ignoradas = adicionar_fotos(novo_servico, request.files.getlist('imagens'))
        if fotos_ignoradas:
            flash(f'{fotos_ignoradas} foto(s) não foram adicionadas (arquivo inválido ou acima do limite de {MAX_FOTOS_SERVICO} fotos).', 'warning')
        
        db.session.add(novo_servico)
        db.session.commit()
        
        if quer_destaque:
            flash('Serviço cadastrado e destacado com sucesso!', 'success')
        else:
            flash('Serviço cadastrado com sucesso!', 'success')
        
        return redirect(url_for('servico.meus_servicos'))
    
    # GET: renderiza o template passando as variáveis necessárias
    return render_template(
        'cadastro_servico.html',
        assinatura_ativa=assinatura_ativa,
        servicos_em_destaque=servicos_em_destaque,
        max_fotos=MAX_FOTOS_SERVICO
    )


@servico_bp.route('/meus-servicos')
@login_required
def meus_servicos():
    if current_user.tipo != 'prestador':
        flash('Acesso negado', 'danger')
        return redirect(url_for('main.index'))
    
    servicos = Servico.query.filter_by(prestador_id=current_user.id, removido=False).order_by(Servico.data_postagem.desc()).all()
    return render_template('meus_servicos.html', servicos=servicos)


@servico_bp.route('/')
@servico_bp.route('/lista')
def lista():
    categoria = request.args.get('categoria')
    q = request.args.get('q', '').strip()
    prestador_id = request.args.get('prestador')
    
    query = servicos_visiveis()
    if categoria:
        query = query.filter(Servico.categoria == categoria)
    if prestador_id:
        query = query.filter(Servico.prestador_id == prestador_id)
    if q:
        query = query.filter(
            or_(Servico.titulo.ilike(f'%{q}%'),
                Servico.descricao.ilike(f'%{q}%'),
                Usuario.nome.ilike(f'%{q}%'))
        )
    
    servicos = query.order_by(Servico.data_postagem.desc()).all()
    categorias = servicos_visiveis().with_entities(Servico.categoria, func.count(Servico.id).label('total')).group_by(Servico.categoria).all()
    
    return render_template('lista_servicos.html',
                         servicos=servicos, categoria=categoria,
                         categorias=categorias, termo_busca=q)


@servico_bp.route('/<int:id>')
def detalhe(id):
    servico = Servico.query.get_or_404(id)
    if servico.prestador.desativada or servico.removido:
        abort(404)
    return render_template('detalhe_servico.html', servico=servico)


@servico_bp.route('/<int:id>/foto/<int:n>')
def foto(id, n):
    """Entrega a foto número n do serviço (0 = capa) como imagem, para a galeria"""
    servico = Servico.query.get_or_404(id)
    fotos = servico.fotos()
    if servico.prestador.desativada or servico.removido or n < 0 or n >= len(fotos):
        abort(404)
    
    resposta = Response(base64.b64decode(fotos[n]), mimetype='image/jpeg')
    # A URL leva um código de versão (?v=), então pode ficar em cache por bastante tempo
    resposta.headers['Cache-Control'] = 'public, max-age=86400'
    return resposta


@servico_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    servico = Servico.query.get_or_404(id)
    if servico.removido:
        abort(404)
    
    if servico.prestador_id != current_user.id:
        flash('Você não tem permissão para editar este serviço', 'danger')
        return redirect(url_for('servico.detalhe', id=id))
    
    # Verifica assinatura (ignorando o próprio serviço na contagem)
    assinatura_ativa = get_assinatura_ativa(current_user.id)
    limite_plano = get_limite_destaques(assinatura_ativa)
    total_destaques_outros = get_total_destaques(current_user.id, ignorar_servico_id=id)
    
    if request.method == 'POST':
        servico.titulo = request.form.get('titulo')
        servico.descricao = request.form.get('descricao')
        servico.categoria = request.form.get('categoria')
        servico.tipo_preco = request.form.get('tipo_preco', 'fixo')
        
        preco = request.form.get('preco')
        servico.preco = parse_preco(preco) if servico.tipo_preco != 'consulta' else None
        
        # Sem preço válido, o serviço fica como "a combinar" (evita preço vazio nas telas)
        if servico.tipo_preco != 'consulta' and servico.preco is None:
            servico.tipo_preco = 'consulta'
            flash('Preço não informado ou inválido: o serviço foi salvo como "A combinar".', 'warning')
        
        # === VALIDAÇÃO DE DESTAQUE NO BACKEND ===
        quer_destaque = request.form.get('destaque') == 'on'
        
        if quer_destaque:
            if not assinatura_ativa:
                flash('Você precisa de um plano de destaque para destacar serviços.', 'warning')
                quer_destaque = False
            elif total_destaques_outros >= limite_plano:
                flash(f'Você já atingiu o limite de {limite_plano} destaque(s) do plano {assinatura_ativa.plano.capitalize()}.', 'warning')
                quer_destaque = False
        
        servico.destaque = quer_destaque

        # O destaque pago vem sempre da assinatura, nunca de um campo do formulário
        if quer_destaque:
            servico.destaque_pago = True
            servico.plano_destaque = assinatura_ativa.plano
            servico.destaque_data_fim = assinatura_ativa.data_fim
        else:
            servico.destaque_pago = False
            servico.destaque_data_fim = None

        # Fotos: remove as marcadas ("capa" ou o id da foto extra)...
        remover = request.form.getlist('remover_fotos')
        if 'capa' in remover:
            servico.imagem_base64 = None
        for imagem in list(servico.imagens_extras):
            if str(imagem.id) in remover:
                servico.imagens_extras.remove(imagem)
        
        # ...se ficou sem capa, a primeira foto restante assume...
        if not servico.imagem_base64 and servico.imagens_extras:
            nova_capa = servico.imagens_extras[0]
            servico.imagem_base64 = nova_capa.imagem_base64
            servico.imagens_extras.remove(nova_capa)

        # ...e adiciona as novas
        _, fotos_ignoradas = adicionar_fotos(servico, request.files.getlist('imagens'))
        if fotos_ignoradas:
            flash(f'{fotos_ignoradas} foto(s) não foram adicionadas (arquivo inválido ou acima do limite de {MAX_FOTOS_SERVICO} fotos).', 'warning')

        db.session.commit()
        flash('Serviço atualizado com sucesso!', 'success')
        return redirect(url_for('servico.detalhe', id=servico.id))
    
    # GET: renderiza o template passando as variáveis necessárias
    return render_template(
        'editar_servico.html',
        servico=servico,
        now=datetime.utcnow(),
        assinatura_ativa=assinatura_ativa,
        servicos_em_destaque=Servico.query.filter_by(
            prestador_id=current_user.id,
            destaque=True
        ).all(),
        max_fotos=MAX_FOTOS_SERVICO
    )


@servico_bp.route('/solicitar/<int:servico_id>', methods=['POST'])
@login_required
def solicitar(servico_id):
    if current_user.tipo != 'cliente':
        flash('Apenas clientes podem solicitar serviços', 'danger')
        return redirect(url_for('servico.detalhe', id=servico_id))
    
    servico = Servico.query.get_or_404(servico_id)
    
    solicitacao_existente = Solicitacao.query.filter_by(
        cliente_id=current_user.id, servico_id=servico_id
    ).first()
    
    if solicitacao_existente:
        flash('Você já solicitou este serviço', 'warning')
        return redirect(url_for('servico.detalhe', id=servico_id))
    
    solicitacao = Solicitacao(
        cliente_id=current_user.id, servico_id=servico_id,
        mensagem=request.form.get('mensagem'), data_solicitacao=datetime.utcnow()
    )
    db.session.add(solicitacao)
    db.session.commit()
    
    flash('Solicitação enviada com sucesso!', 'success')
    return redirect(url_for('servico.detalhe', id=servico_id))

@servico_bp.route('/prestador/<int:prestador_id>')
def perfil_prestador(prestador_id):
    """Página de perfil público do prestador"""
    prestador = Usuario.query.get_or_404(prestador_id)
    if prestador.desativada:
        abort(404)
    
    # Verifica se é realmente um prestador
    if prestador.tipo != 'prestador':
        flash('Este usuário não é um prestador.', 'warning')
        return redirect(url_for('main.index'))
    
    # Buscar os serviços do prestador
    servicos = Servico.query.filter_by(prestador_id=prestador_id, removido=False).order_by(
        Servico.destaque.desc(),
        Servico.data_postagem.desc()
    ).all()
    
    # Média de avaliações (com verificação)
    media_avaliacoes = prestador.media_avaliacoes() if hasattr(prestador, 'media_avaliacoes') else 0
    total_avaliacoes = prestador.total_avaliacoes() if hasattr(prestador, 'total_avaliacoes') else 0
    
    return render_template(
        'perfil_prestador.html',
        prestador=prestador,
        servicos=servicos,
        media_avaliacoes=media_avaliacoes,
        total_avaliacoes=total_avaliacoes
    )


# ============================================
# ROTAS DE PLANOS DE DESTAQUE
# ============================================

@servico_bp.route('/planos')
@login_required
def planos_destaque():
    """Página de planos de destaque para prestadores"""
    if current_user.tipo != 'prestador':
        flash('Apenas prestadores podem acessar os planos de destaque', 'warning')
        return redirect(url_for('main.index'))
    
    return render_template('servico/planos_destaque.html')


@servico_bp.route('/assinar/<plano>')
@login_required
def assinar_plano(plano):
    """Redireciona para o checkout da assinatura no blueprint assinatura"""
    return redirect(url_for('assinatura.checkout', plano=plano))

# ============================================
# IA: SUGESTÃO DE DESCRIÇÃO COM GOOGLE GEMINI
# ============================================

@servico_bp.route('/api/sugerir-descricao', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def sugerir_descricao_ia():
    """Usa Google Gemini para escrever (ou melhorar) a descrição do serviço"""
    from flask import jsonify
    import os
    import json
    import time
    
    dados = request.get_json(silent=True) or {}
    titulo = str(dados.get('titulo') or '').strip()[:200]
    categoria = str(dados.get('categoria') or '').strip()[:100]
    rascunho = str(dados.get('rascunho') or '').strip()[:1500]
    tipo_preco = dados.get('tipo_preco', 'fixo')
    
    if not titulo:
        return jsonify({'erro': 'Título é obrigatório'}), 400
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'erro': 'A ajuda da IA não está disponível no momento.'}), 503
    
    forma_cobranca = {
        'fixo': 'preço fixo pelo serviço completo',
        'hora': 'cobrança por hora',
        'dia': 'cobrança por diária',
        'metro': 'cobrança por metro quadrado',
        'consulta': 'preço a combinar com o cliente'
    }.get(tipo_preco, 'preço fixo')
    
    if rascunho:
        tarefa = f"""O prestador já escreveu este rascunho:
\"\"\"
{rascunho}
\"\"\"

Reescreva o rascunho deixando-o claro, organizado e convincente.
Mantenha TODAS as informações que ele deu e não acrescente fatos novos."""
    else:
        tarefa = """O prestador ainda não escreveu nada.
Escreva uma descrição explicando o que o serviço costuma incluir e como o cliente é atendido."""
    
    prompt = f"""Você escreve descrições de anúncios para uma plataforma brasileira de prestadores de serviços (HiringScope).

SERVIÇO:
- Título: "{titulo}"
- Categoria: {categoria or 'não informada'}
- Forma de cobrança: {forma_cobranca}

{tarefa}

REGRAS:
- Português do Brasil, em primeira pessoa (quem fala é o prestador), tom profissional e simpático
- Entre 400 e 700 caracteres, em 2 ou 3 parágrafos curtos, texto simples (sem markdown, sem emojis, sem listas)
- NÃO invente fatos que o prestador não informou: anos de experiência, certificados, garantia, prazos, preços, cidade ou telefone
- Não cite valores em reais
- Termine convidando o cliente a chamar pelo chat

Responda APENAS com JSON no formato:
{{"descricao": "texto aqui"}}"""
    
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            response_mime_type='application/json',
            temperature=0.8
        )

        try:
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config)
        except Exception as e:
            # O Gemini às vezes responde "sobrecarregado"; uma segunda tentativa costuma passar
            print(f"⚠️ Gemini falhou na 1ª tentativa (descrição): {e}")
            time.sleep(1.5)
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config)

        descricao = str(json.loads(response.text).get('descricao') or '').strip()
        if not descricao:
            raise ValueError('resposta vazia')
        
        return jsonify({'sucesso': True, 'descricao': descricao[:2000]})
        
    except Exception as e:
        print(f"❌ Erro Gemini (descrição): {e}")
        return jsonify({'erro': 'Não foi possível gerar a descrição agora. Tente novamente em instantes.'}), 502


# ============================================
# IA: SUGESTÃO DE PREÇO COM GOOGLE GEMINI
# ============================================

@servico_bp.route('/api/sugerir-preco', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def sugerir_preco_ia():
    """Usa Google Gemini para sugerir um preço justo baseado em serviços similares"""
    from flask import jsonify
    import os
    import json

    dados = request.get_json(silent=True) or {}
    titulo = str(dados.get('titulo') or '').strip()[:200]
    categoria = str(dados.get('categoria') or '').strip()[:100]
    tipo_preco = dados.get('tipo_preco', 'fixo')

    if not titulo:
        return jsonify({'erro': 'Título é obrigatório'}), 400

    # ============================================
    # 1. ANALISAR SERVIÇOS SIMILARES
    # ============================================
    palavras_titulo = [p.lower() for p in titulo.split() if len(p) > 3]

    # Só as colunas necessárias (sem carregar as imagens em base64)
    servicos_com_preco = db.session.query(
        Servico.titulo, Servico.categoria, Servico.preco
    ).filter(Servico.preco > 0, Servico.removido == False).all()

    precos = [
        s.preco for s in servicos_com_preco
        if s.categoria == categoria
        or any(palavra in s.titulo.lower() for palavra in palavras_titulo)
    ]

    if precos:
        media = sum(precos) / len(precos)
        minimo = min(precos)
        maximo = max(precos)
        total = len(precos)
    else:
        media = None
        minimo = None
        maximo = None
        total = 0
    
    # ============================================
    # 2. CHAMAR O GEMINI
    # ============================================
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if api_key:
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=api_key)
            
            # Contexto com dados da plataforma
            if total > 0:
                contexto = f"""
DADOS DA PLATAFORMA (HiringScope - Cruzeiro/SP):
- Serviços similares cadastrados: {total}
- Preço médio: R$ {media:.2f}
- Preço mínimo: R$ {minimo:.2f}
- Preço máximo: R$ {maximo:.2f}
"""
            else:
                contexto = """
DADOS DA PLATAFORMA:
- Ainda não há serviços similares cadastrados com preço.
- Use conhecimento geral do mercado brasileiro (2026).
"""
            
            tipo_preco_descricao = {
                'fixo': 'preço fixo pelo serviço completo',
                'hora': 'valor cobrado por hora trabalhada',
                'dia': 'valor por diária (8h de trabalho)',
                'metro': 'valor por metro quadrado',
                'consulta': 'sob consulta'
            }.get(tipo_preco, 'preço fixo')
            
            prompt = f"""Você é um especialista em precificação de serviços no Brasil.

SERVIÇO A SER PRECIFICADO:
- Título: "{titulo}"
- Categoria: {categoria}
- Tipo de cobrança: {tipo_preco_descricao}

{contexto}

TAREFA:
1. Analise o serviço e o mercado brasileiro
2. Sugira uma FAIXA de preço justa (mínimo e máximo em reais)
3. Sugira um valor IDEAL para começar
4. Dê uma justificativa CURTA (máximo 3 linhas)
5. Dê 2 dicas práticas para o prestador

Responda APENAS com JSON no formato:
{{
    "preco_minimo": 100.00,
    "preco_maximo": 250.00,
    "preco_ideal": 180.00,
    "justificativa": "texto curto aqui",
    "dicas": ["dica 1", "dica 2"]
}}

Use valores REALISTAS do mercado brasileiro de 2026."""

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.7
                )
            )
            
            dados_ia = json.loads(response.text)
            
            return jsonify({
                'sucesso': True,
                'preco_minimo': dados_ia.get('preco_minimo'),
                'preco_maximo': dados_ia.get('preco_maximo'),
                'preco_ideal': dados_ia.get('preco_ideal'),
                'justificativa': dados_ia.get('justificativa', ''),
                'dicas': dados_ia.get('dicas', []),
                'servicos_similares': total,
                'fonte': 'IA'
            })
            
        except Exception as e:
            print(f"❌ Erro Gemini: {e}")
            import traceback
            traceback.print_exc()
            # Cai no fallback abaixo
    
    # ============================================
    # 3. FALLBACK: calcular sem IA
    # ============================================
    precos_base = {
        'fixo': {'min': 80, 'max': 300, 'ideal': 150},
        'hora': {'min': 40, 'max': 120, 'ideal': 70},
        'dia': {'min': 150, 'max': 400, 'ideal': 250},
        'metro': {'min': 20, 'max': 80, 'ideal': 45},
    }
    base = precos_base.get(tipo_preco, precos_base['fixo'])
    
    if total > 0 and media:
        return jsonify({
            'sucesso': True,
            'preco_minimo': round(minimo, 2),
            'preco_maximo': round(maximo, 2),
            'preco_ideal': round(media, 2),
            'justificativa': f'Baseado em {total} serviços similares na plataforma.',
            'dicas': ['Preços competitivos recebem mais contatos', 'Você pode ajustar depois'],
            'servicos_similares': total,
            'fonte': 'plataforma'
        })
    
    return jsonify({
        'sucesso': True,
        'preco_minimo': base['min'],
        'preco_maximo': base['max'],
        'preco_ideal': base['ideal'],
        'justificativa': f'Valores médios do mercado para {tipo_preco}.',
        'dicas': ['Pesquise concorrentes na sua região', 'Considere incluir material no preço'],
        'servicos_similares': 0,
        'fonte': 'mercado'
    })