from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    telefone = db.Column(db.String(20))
    tipo = db.Column(db.String(20), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    foto_perfil = db.Column(db.String(200), default='default.jpg')
    foto_url = db.Column(db.String(500), nullable=True)  # URL da foto do Google
    descricao = db.Column(db.Text)
    
    # Relacionamentos
    servicos_oferecidos = db.relationship('Servico', backref='prestador_rel', lazy=True)
    avaliacoes_recebidas = db.relationship('Avaliacao', foreign_keys='Avaliacao.prestador_id', backref='avaliado_rel', lazy=True)
    avaliacoes_feitas = db.relationship('Avaliacao', foreign_keys='Avaliacao.cliente_id', backref='avaliador_rel', lazy=True)
    favoritos = db.relationship('Favorito', foreign_keys='Favorito.cliente_id', backref='cliente_rel', lazy=True)
    
    def set_password(self, password):
        self.senha_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)
    
    def media_avaliacoes(self):
        """Calcula a média das avaliações recebidas"""
        if hasattr(self, 'avaliacoes_recebidas') and self.avaliacoes_recebidas:
            total = sum([a.nota for a in self.avaliacoes_recebidas])
            return total / len(self.avaliacoes_recebidas)
        return 0
    
    def total_avaliacoes(self):
        """Retorna o total de avaliações recebidas"""
        if hasattr(self, 'avaliacoes_recebidas'):
            return len(self.avaliacoes_recebidas)
        return 0
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'


class Servico(db.Model):
    __tablename__ = 'servicos'
    
    id = db.Column(db.Integer, primary_key=True)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(100))
    preco = db.Column(db.Float)
    destaque = db.Column(db.Boolean, default=False)
    destaque_pago = db.Column(db.Boolean, default=False)
    destaque_data_fim = db.Column(db.DateTime, nullable=True)
    data_postagem = db.Column(db.DateTime, default=datetime.utcnow)
    imagem_base64 = db.Column(db.Text, nullable=True)
    
    # Relacionamentos
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id], back_populates='servicos_oferecidos')
    solicitacoes = db.relationship('Solicitacao', backref='servico_rel', lazy=True)
    avaliacoes = db.relationship('Avaliacao', backref='servico_rel', lazy=True)
    
    def is_destaque_ativo(self):
        """Verifica se o destaque pago ainda está ativo"""
        if self.destaque_pago and self.destaque_data_fim:
            return datetime.utcnow() < self.destaque_data_fim
        return self.destaque
    
    def __repr__(self):
        return f'<Servico {self.titulo}>'


class Solicitacao(db.Model):
    __tablename__ = 'solicitacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    mensagem = db.Column(db.Text)
    status = db.Column(db.String(20), default='pendente')  # pendente, aceito, recusado
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])
    servico = db.relationship('Servico', foreign_keys=[servico_id])
    
    def __repr__(self):
        return f'<Solicitacao {self.id}>'


class Avaliacao(db.Model):
    __tablename__ = 'avaliacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    data_avaliacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id])
    servico = db.relationship('Servico', foreign_keys=[servico_id])
    
    def __repr__(self):
        return f'<Avaliacao {self.id} - Nota: {self.nota}>'


class Favorito(db.Model):
    __tablename__ = 'favoritos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    data_adicao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id])
    
    __table_args__ = (db.UniqueConstraint('cliente_id', 'prestador_id', name='unique_favorito'),)
    
    def __repr__(self):
        return f'<Favorito {self.id}>'


class Mensagem(db.Model):
    __tablename__ = 'mensagens'
    
    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    lida = db.Column(db.Boolean, default=False)
    
    # Relacionamentos
    remetente = db.relationship('Usuario', foreign_keys=[remetente_id])
    destinatario = db.relationship('Usuario', foreign_keys=[destinatario_id])
    
    def __repr__(self):
        return f'<Mensagem {self.id}>'