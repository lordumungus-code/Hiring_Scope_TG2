from flask import Blueprint, render_template
from models import Servico
from extensions import db
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Busca serviços em destaque
    servicos_destaque = Servico.query.filter_by(destaque=True).order_by(Servico.data_postagem.desc()).limit(6).all()
    
    # Busca todos os serviços recentes
    servicos_recentes = Servico.query.order_by(Servico.data_postagem.desc()).limit(8).all()
    
    # Busca serviços por categoria com contagem (para mostrar categorias populares)
    categorias = db.session.query(
        Servico.categoria, 
        func.count(Servico.id).label('total')
    ).group_by(Servico.categoria).order_by(func.count(Servico.id).desc()).limit(6).all()
    
    return render_template('index.html', 
                         servicos_destaque=servicos_destaque,
                         servicos_recentes=servicos_recentes,
                         categorias=categorias)