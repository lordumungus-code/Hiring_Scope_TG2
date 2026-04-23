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
    tipo = db.Column(db.String(20), nullable=False)  # cliente, prestador
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    foto_perfil = db.Column(db.String(200), default='default.jpg')
    foto_url = db.Column(db.String(500), nullable=True)  # URL da foto do Google
    descricao = db.Column(db.Text)
    
    # Relacionamentos
    servicos_oferecidos = db.relationship('Servico', backref='prestador_rel', lazy=True)
    avaliacoes_recebidas = db.relationship('Avaliacao', foreign_keys='Avaliacao.prestador_id', backref='avaliado_rel', lazy=True)
    avaliacoes_feitas = db.relationship('Avaliacao', foreign_keys='Avaliacao.cliente_id', backref='avaliador_rel', lazy=True)
    favoritos = db.relationship('Favorito', foreign_keys='Favorito.cliente_id', backref='cliente_rel', lazy=True)
    
    # NOVOS RELACIONAMENTOS PARA CONTRATOS
    contratos_como_cliente = db.relationship('Contrato', foreign_keys='Contrato.cliente_id', backref='cliente_rel', lazy=True)
    contratos_como_prestador = db.relationship('Contrato', foreign_keys='Contrato.prestador_id', backref='prestador_rel', lazy=True)
    
    def set_password(self, password):
        self.senha_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)
    
    def media_avaliacoes(self):
        """Calcula a média das avaliações recebidas"""
        if self.avaliacoes_recebidas:
            total = sum([a.nota for a in self.avaliacoes_recebidas])
            return round(total / len(self.avaliacoes_recebidas), 1)
        return 0
    
    def total_avaliacoes(self):
        """Retorna o total de avaliações recebidas"""
        return len(self.avaliacoes_recebidas) if self.avaliacoes_recebidas else 0
    
    def avaliacoes_por_nota(self, nota):
        """Retorna quantidade de avaliações com determinada nota"""
        if self.avaliacoes_recebidas:
            return len([a for a in self.avaliacoes_recebidas if a.nota == nota])
        return 0
    
    def percentual_avaliacoes(self, nota):
        """Retorna o percentual de avaliações com determinada nota"""
        total = self.total_avaliacoes()
        if total > 0:
            return round((self.avaliacoes_por_nota(nota) / total) * 100)
        return 0
    
    def contratos_concluidos_como_prestador(self):
        """Retorna contratos concluídos como prestador"""
        return [c for c in self.contratos_como_prestador if c.status == 'concluido']
    
    def contratos_concluidos_como_cliente(self):
        """Retorna contratos concluídos como cliente"""
        return [c for c in self.contratos_como_cliente if c.status == 'concluido']
    
    def pode_avaliar(self, contrato_id):
        """Verifica se o cliente pode avaliar um contrato específico"""
        contrato = Contrato.query.get(contrato_id)
        if contrato and contrato.cliente_id == self.id and contrato.status == 'concluido':
            # Verifica se já não avaliou
            avaliacao_existente = Avaliacao.query.filter_by(
                contrato_id=contrato_id,
                cliente_id=self.id
            ).first()
            return avaliacao_existente is None
        return False
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'


class Servico(db.Model):
    __tablename__ = 'servicos'
    
    id = db.Column(db.Integer, primary_key=True)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(100))
    
    # NOVOS CAMPOS DE PRECIFICAÇÃO
    tipo_preco = db.Column(db.String(20), default='fixo')  # fixo, hora, dia, metro, consulta
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
    contratos = db.relationship('Contrato', backref='servico_rel', lazy=True)
    
    def is_destaque_ativo(self):
        """Verifica se o destaque pago ainda está ativo"""
        if self.destaque_pago and self.destaque_data_fim:
            return datetime.utcnow() < self.destaque_data_fim
        return self.destaque
    
    def media_avaliacoes(self):
        """Média das avaliações do serviço"""
        if self.avaliacoes:
            total = sum([a.nota for a in self.avaliacoes])
            return round(total / len(self.avaliacoes), 1)
        return 0
    
    def total_avaliacoes(self):
        return len(self.avaliacoes) if self.avaliacoes else 0
    
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


# ============================================
# CONTRATO (ordem de serviço formal)
# ============================================

class Contrato(db.Model):
    """Modelo para contratos de serviço entre cliente e prestador"""
    __tablename__ = 'contratos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    
    # Status do contrato
    status = db.Column(db.String(20), default='pendente')  # pendente, aceito, em_andamento, concluido, cancelado
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_aceite = db.Column(db.DateTime, nullable=True)
    data_inicio = db.Column(db.DateTime, nullable=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    
    # Detalhes do contrato
    mensagem_cliente = db.Column(db.Text, nullable=True)
    mensagem_prestador = db.Column(db.Text, nullable=True)
    preco_acordado = db.Column(db.Float, nullable=True)
    
    # Relacionamentos
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id], back_populates='contratos_como_cliente')
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id], back_populates='contratos_como_prestador')
    servico = db.relationship('Servico', foreign_keys=[servico_id], back_populates='contratos')
    avaliacao = db.relationship('Avaliacao', backref='contrato', uselist=False, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Contrato {self.id} - {self.status}>'
    
    def get_status_icon(self):
        """Retorna o ícone correspondente ao status"""
        icons = {
            'pendente': 'fa-clock',
            'aceito': 'fa-check-circle',
            'em_andamento': 'fa-spinner',
            'concluido': 'fa-star',
            'cancelado': 'fa-times-circle'
        }
        return icons.get(self.status, 'fa-file-contract')
    
    def get_status_color(self):
        """Retorna a cor correspondente ao status"""
        colors = {
            'pendente': 'warning',
            'aceito': 'info',
            'em_andamento': 'primary',
            'concluido': 'success',
            'cancelado': 'danger'
        }
        return colors.get(self.status, 'secondary')
    
    def pode_avaliar(self, usuario_id):
        """Verifica se o usuário pode avaliar este contrato"""
        if self.status == 'concluido':
            if self.cliente_id == usuario_id:
                # Verifica se já não avaliou
                avaliacao_existente = Avaliacao.query.filter_by(
                    contrato_id=self.id,
                    cliente_id=usuario_id
                ).first()
                return avaliacao_existente is None
        return False


# ============================================
# AVALIAÇÃO (com link para contrato)
# ============================================

class Avaliacao(db.Model):
    __tablename__ = 'avaliacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos.id'), nullable=False)  # link com contrato
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=True)  # Opcional
    
    # Nota principal (1-5 estrelas)
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    
    # Avaliações detalhadas por categoria (1-5)
    qualidade = db.Column(db.Integer, nullable=True)
    pontualidade = db.Column(db.Integer, nullable=True)
    comunicacao = db.Column(db.Integer, nullable=True)
    preco_justo = db.Column(db.Integer, nullable=True)
    
    data_avaliacao = db.Column(db.DateTime, default=datetime.utcnow)
    editado = db.Column(db.Boolean, default=False)
    data_edicao = db.Column(db.DateTime, nullable=True)
    
    # Relacionamentos
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id], back_populates='avaliacoes_feitas')
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id], back_populates='avaliacoes_recebidas')
    servico = db.relationship('Servico', foreign_keys=[servico_id])
    
    def __repr__(self):
        return f'<Avaliacao {self.id} - Nota: {self.nota}>'
    
    def pode_editar(self, usuario_id):
        """Verifica se a avaliação pode ser editada (até 7 dias após criação)"""
        if self.cliente_id == usuario_id:  # Mude de avaliador_id para cliente_id
            dias_passados = (datetime.utcnow() - self.data_avaliacao).days
            return dias_passados <= 7
        return False
    
    def get_media_categorias(self):
        """Calcula a média das avaliações por categoria"""
        categorias = [self.qualidade, self.pontualidade, self.comunicacao, self.preco_justo]
        validas = [c for c in categorias if c is not None]
        if validas:
            return round(sum(validas) / len(validas), 1)
        return None


# ============================================
# RECLAMAÇÃO/CONTESTAÇÃO DE AVALIAÇÃO
# ============================================

class Reclamacao(db.Model):
    """Modelo para reclamações/contestações de avaliações"""
    __tablename__ = 'reclamacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    avaliacao_id = db.Column(db.Integer, db.ForeignKey('avaliacoes.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pendente')  # pendente, analisando, resolvido, rejeitado
    data_reclamacao = db.Column(db.DateTime, default=datetime.utcnow)
    resposta_admin = db.Column(db.Text, nullable=True)
    data_resposta = db.Column(db.DateTime, nullable=True)
    
    # Relacionamentos
    avaliacao = db.relationship('Avaliacao', backref='reclamacoes')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    
    def __repr__(self):
        return f'<Reclamacao {self.id} - {self.status}>'


# ============================================
# FAVORITO
# ============================================

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


# ============================================
# MENSAGEM
# ============================================

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