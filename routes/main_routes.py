from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import Servico, Usuario, Avaliacao, Contrato
from sqlalchemy import desc

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    servicos_destaque = Servico.query.filter_by(destaque=True).order_by(Servico.data_postagem.desc()).all()
    
    # Buscar 50 serviços para mostrar inicialmente
    servicos_recentes = Servico.query.order_by(Servico.data_postagem.desc()).limit(50).all()
    
    # Total de serviços (para saber se tem mais)
    total_servicos = Servico.query.count()
    
    # Depoimentos reais (notas 4 ou 5)
    depoimentos = Avaliacao.query.filter(
        Avaliacao.nota >= 4,
        Avaliacao.comentario.isnot(None),
        Avaliacao.comentario != ''
    ).order_by(desc(Avaliacao.data_avaliacao)).limit(6).all()
    
    if not depoimentos:
        depoimentos = [
            {'nome': 'Maria Silva', 'texto': 'Excelente plataforma! Encontrei um profissional qualificado em poucos minutos. Recomendo!', 'nota': 5, 'tipo': 'Cliente'},
            {'nome': 'João Santos', 'texto': 'Como prestador, consegui vários clientes através da plataforma. Ótimo sistema de chat!', 'nota': 5, 'tipo': 'Prestador'},
            {'nome': 'Ana Oliveira', 'texto': 'Interface intuitiva e fácil de usar. O suporte é rápido e eficiente. Estou muito satisfeito!', 'nota': 4, 'tipo': 'Cliente'}
        ]
    else:
        depoimentos = [{
            'nome': d.cliente.nome if d.cliente else 'Cliente',
            'texto': d.comentario,
            'nota': d.nota,
            'tipo': 'Cliente',
            'data': d.data_avaliacao.strftime('%d/%m/%Y')
        } for d in depoimentos]
    
    # Top prestadores
    prestadores = Usuario.query.filter(
        Usuario.tipo == 'prestador',
        Usuario.avaliacoes_recebidas.any()
    ).all()
    
    top_prestadores = []
    for prestador in prestadores:
        media = prestador.media_avaliacoes()
        total = prestador.total_avaliacoes()
        if media > 0:
            top_prestadores.append({
                'prestador': prestador,
                'media': media,
                'total_avaliacoes': total,
                'servicos_count': len(prestador.servicos_oferecidos)
            })
    
    top_prestadores = sorted(top_prestadores, key=lambda x: x['media'], reverse=True)[:10]
    
    # Categorias com contagem
    from sqlalchemy import func
    categorias_com_contagem = db.session.query(
        Servico.categoria, 
        func.count(Servico.id).label('total')
    ).group_by(Servico.categoria).all()
    
    return render_template('index.html',
                         servicos_destaque=servicos_destaque,
                         servicos_recentes=servicos_recentes,
                         total_servicos=total_servicos,
                         top_prestadores=top_prestadores,
                         depoimentos=depoimentos,
                         categorias_com_contagem=categorias_com_contagem,
                         total_usuarios=Usuario.query.count(),
                         total_avaliacoes=Avaliacao.query.count(),
                         servicos_concluidos=Contrato.query.filter_by(status='concluido').count())

@main_bp.route('/dashboard')
@login_required
def dashboard():
    from models import Contrato
    
    if current_user.tipo == 'prestador':
        servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
        contratos = Contrato.query.filter_by(prestador_id=current_user.id).order_by(Contrato.data_solicitacao.desc()).all()
        
        return render_template('dashboard_prestador.html',
                             servicos=servicos,
                             contratos=contratos,
                             contratos_pendentes=[c for c in contratos if c.status == 'pendente'],
                             contratos_andamento=[c for c in contratos if c.status in ['aceito', 'em_andamento']],
                             contratos_concluidos=[c for c in contratos if c.status == 'concluido'],
                             media_avaliacoes=current_user.media_avaliacoes())
    else:
        contratos = Contrato.query.filter_by(cliente_id=current_user.id).order_by(Contrato.data_solicitacao.desc()).all()
        return render_template('dashboard_cliente.html',
                             contratos=contratos,
                             contratos_pendentes=[c for c in contratos if c.status == 'pendente'],
                             contratos_andamento=[c for c in contratos if c.status in ['aceito', 'em_andamento']],
                             contratos_concluidos=[c for c in contratos if c.status == 'concluido'])


@main_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    from models import Usuario
    import base64
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        descricao = request.form.get('descricao')
        
        if email != current_user.email:
            email_existente = Usuario.query.filter_by(email=email).first()
            if email_existente:
                flash('Este e-mail já está em uso por outra conta.', 'danger')
                return redirect(url_for('main.perfil'))
        
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                file_data = file.read()
                if len(file_data) > 5 * 1024 * 1024:
                    flash('A imagem deve ter no máximo 5MB.', 'danger')
                    return redirect(url_for('main.perfil'))
                foto_base64 = base64.b64encode(file_data).decode('utf-8')
                current_user.foto_perfil = foto_base64
        
        current_user.nome = nome
        current_user.email = email
        current_user.telefone = telefone
        current_user.descricao = descricao
        
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('main.perfil'))
    
    return render_template('perfil.html', usuario=current_user)


@main_bp.route('/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    confirmar_senha = request.form.get('confirmar_senha')
    
    if not current_user.check_password(senha_atual):
        flash('Senha atual incorreta.', 'danger')
        return redirect(url_for('main.perfil'))
    
    if nova_senha != confirmar_senha:
        flash('As novas senhas não coincidem.', 'danger')
        return redirect(url_for('main.perfil'))
    
    current_user.set_password(nova_senha)
    db.session.commit()
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('main.perfil'))


@main_bp.route('/perfil/<int:prestador_id>')
def perfil_prestador(prestador_id):
    prestador = Usuario.query.get_or_404(prestador_id)
    if prestador.tipo != 'prestador':
        flash('Usuário não é um prestador de serviços', 'warning')
        return redirect(url_for('main.index'))
    return render_template('perfil_prestador.html', prestador=prestador)


# ============================================
# ROTA PARA LISTA DE PRESTADORES - ADICIONADA
# ============================================

@main_bp.route('/prestadores')
def lista_prestadores():
    """Lista todos os prestadores com ranking"""
    from models import Usuario, Contrato
    
    prestadores = Usuario.query.filter_by(tipo='prestador').all()
    ranking = []
    for p in prestadores:
        ranking.append({
            'prestador': p,
            'media': p.media_avaliacoes(),
            'total_avaliacoes': p.total_avaliacoes(),
            'total_servicos': len(p.servicos_oferecidos),
            'total_concluidos': Contrato.query.filter_by(prestador_id=p.id, status='concluido').count()
        })
    ranking = sorted(ranking, key=lambda x: x['media'], reverse=True)
    return render_template('prestadores.html', ranking=ranking)

@main_bp.route('/servicos/recentes')
def servicos_recentes_api():
    """API para carregar mais serviços (paginação)"""
    from flask import request, jsonify
    from models import Servico
    
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 8, type=int)  # Carrega 8 por vez
    
    servicos = Servico.query.order_by(Servico.data_postagem.desc()).offset(offset).limit(limit).all()
    total = Servico.query.count()
    
    resultado = []
    for servico in servicos:
        resultado.append({
            'id': servico.id,
            'titulo': servico.titulo,
            'categoria': servico.categoria,
            'preco': servico.preco,
            'prestador_id': servico.prestador_id,
            'prestador_nome': servico.prestador.nome,
            'imagem_base64': servico.imagem_base64
        })
    
    return jsonify({
        'servicos': resultado,
        'total': total,
        'offset': offset,
        'limit': limit
    })