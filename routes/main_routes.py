from flask import Blueprint, render_template
from models import Servico

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    servicos_destaque = Servico.query.filter_by(destaque=True).order_by(Servico.data_postagem.desc()).limit(6).all()
    servicos_recentes = Servico.query.order_by(Servico.data_postagem.desc()).limit(8).all()
    return render_template('index.html', 
                         servicos_destaque=servicos_destaque,
                         servicos_recentes=servicos_recentes)