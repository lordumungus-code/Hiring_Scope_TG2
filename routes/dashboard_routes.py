from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Servico, Solicitacao

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    if current_user.tipo == 'prestador':
        servicos = Servico.query.filter_by(prestador_id=current_user.id).order_by(Servico.data_postagem.desc()).all()
        return render_template('dashboard_prestador.html', servicos=servicos)
    else:
        solicitacoes = Solicitacao.query.filter_by(cliente_id=current_user.id).all()
        return render_template('dashboard_cliente.html', solicitacoes=solicitacoes)