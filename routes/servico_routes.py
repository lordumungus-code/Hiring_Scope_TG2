from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Servico, Usuario, Solicitacao, Assinatura
from sqlalchemy import or_, func
import base64
from datetime import datetime, timedelta

servico_bp = Blueprint('servico', __name__, url_prefix='/servico')


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def get_assinatura_ativa(prestador_id):
    """Retorna a assinatura ativa do prestador, ou None"""
    return Assinatura.query.filter_by(
        prestador_id=prestador_id,
        status='ativa'
    ).first()


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
        
        # === VALIDAÇÃO DE DESTAQUE NO BACKEND ===
        if quer_destaque:
            if not assinatura_ativa:
                flash('Você precisa de um plano de destaque para destacar serviços.', 'warning')
                quer_destaque = False
            elif len(servicos_em_destaque) >= limite_plano:
                flash(f'Você já atingiu o limite de {limite_plano} destaque(s) do plano {assinatura_ativa.plano.capitalize()}.', 'warning')
                quer_destaque = False
        
        # Processa a imagem
        imagem_base64 = None
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '':
                file_data = file.read()
                imagem_base64 = base64.b64encode(file_data).decode('utf-8')
        
        # Cria o serviço
        novo_servico = Servico(
            prestador_id=current_user.id,
            titulo=titulo,
            descricao=descricao,
            categoria=categoria,
            tipo_preco=tipo_preco,
            preco=float(preco) if preco and tipo_preco != 'consulta' else None,
            imagem_base64=imagem_base64,
            destaque=quer_destaque,
            data_postagem=datetime.utcnow()
        )
        
        # Se foi destacado com sucesso, marca como destaque pago também
        if quer_destaque:
            novo_servico.destaque_pago = True
            novo_servico.plano_destaque = assinatura_ativa.plano
            if assinatura_ativa.data_fim:
                novo_servico.destaque_data_fim = assinatura_ativa.data_fim
        
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
        servicos_em_destaque=servicos_em_destaque
    )


@servico_bp.route('/meus-servicos')
@login_required
def meus_servicos():
    if current_user.tipo != 'prestador':
        flash('Acesso negado', 'danger')
        return redirect(url_for('main.index'))
    
    servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
    return render_template('meus_servicos.html', servicos=servicos)


@servico_bp.route('/')
@servico_bp.route('/lista')
def lista():
    categoria = request.args.get('categoria')
    q = request.args.get('q', '').strip()
    prestador_id = request.args.get('prestador')
    
    query = Servico.query
    if categoria:
        query = query.filter_by(categoria=categoria)
    if prestador_id:
        query = query.filter_by(prestador_id=prestador_id)
    if q:
        query = query.join(Usuario).filter(
            or_(Servico.titulo.ilike(f'%{q}%'),
                Servico.descricao.ilike(f'%{q}%'),
                Usuario.nome.ilike(f'%{q}%'))
        )
    
    servicos = query.order_by(Servico.data_postagem.desc()).all()
    categorias = db.session.query(Servico.categoria, func.count(Servico.id).label('total')).group_by(Servico.categoria).all()
    
    return render_template('lista_servicos.html',
                         servicos=servicos, categoria=categoria,
                         categorias=categorias, termo_busca=q)


@servico_bp.route('/<int:id>')
def detalhe(id):
    servico = Servico.query.get_or_404(id)
    return render_template('detalhe_servico.html', servico=servico)


@servico_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    servico = Servico.query.get_or_404(id)
    
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
        if servico.tipo_preco != 'consulta' and preco:
            servico.preco = float(preco)
        else:
            servico.preco = None
        
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
        
        # Lógica de destaque pago (mantida como estava)
        destaque_pago = request.form.get('destaque_pago') == 'on'
        if destaque_pago and not servico.destaque_pago:
            servico.destaque_pago = True
            servico.destaque_data_fim = datetime.utcnow() + timedelta(days=30)
            servico.destaque = True
            flash('Destaque Premium ativado! Seu serviço ficará em destaque por 30 dias.', 'success')
        elif not destaque_pago:
            servico.destaque_pago = False
            servico.destaque_data_fim = None
        
        if request.form.get('remover_imagem') == 'true':
            servico.imagem_base64 = None
        
        if 'imagem' in request.files:
            file = request.files['imagem']
            if file and file.filename != '':
                file_data = file.read()
                servico.imagem_base64 = base64.b64encode(file_data).decode('utf-8')
        
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
        ).all()
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
    
    # Verifica se é realmente um prestador
    if prestador.tipo != 'prestador':
        flash('Este usuário não é um prestador.', 'warning')
        return redirect(url_for('main.index'))
    
    # Buscar os serviços do prestador
    servicos = Servico.query.filter_by(prestador_id=prestador_id).order_by(
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
# IA: SUGESTÃO DE PREÇO COM GOOGLE GEMINI
# ============================================

@servico_bp.route('/api/sugerir-preco', methods=['POST'])
@login_required
def sugerir_preco_ia():
    """Usa Google Gemini para sugerir um preço justo baseado em serviços similares"""
    from flask import jsonify
    import os
    import json
    
    dados = request.get_json()
    titulo = dados.get('titulo', '').strip()
    categoria = dados.get('categoria', '').strip()
    tipo_preco = dados.get('tipo_preco', 'fixo')
    
    if not titulo:
        return jsonify({'erro': 'Título é obrigatório'}), 400
    
    # ============================================
    # 1. ANALISAR SERVIÇOS SIMILARES
    # ============================================
    servicos_similares = Servico.query.filter(
        Servico.categoria == categoria,
        Servico.preco.isnot(None),
        Servico.preco > 0
    ).all()
    
    palavras_titulo = [p.lower() for p in titulo.split() if len(p) > 3]
    servicos_mesmo_titulo = []
    
    for servico in Servico.query.filter(Servico.preco.isnot(None)).all():
        for palavra in palavras_titulo:
            if palavra in servico.titulo.lower():
                servicos_mesmo_titulo.append(servico)
                break
    
    todos_relevantes = list(set(servicos_similares + servicos_mesmo_titulo))
    
    if todos_relevantes:
        precos = [s.preco for s in todos_relevantes if s.preco]
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
                model='gemini-3.8-flash',
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