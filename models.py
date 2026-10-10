import zlib
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
    is_admin = db.Column(db.Boolean, default=False)
    desativada = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())  # conta "dormindo" ou excluída
    bloqueada = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())  # bloqueada pelo administrador
    # Prestador escolhe se o telefone e o e-mail aparecem no perfil público (LGPD).
    # Contas novas começam ocultas; as que já existiam continuam como estavam (visíveis) até o dono mudar.
    mostrar_telefone = db.Column(db.Boolean, default=False, nullable=False, server_default=db.true())
    mostrar_email = db.Column(db.Boolean, default=False, nullable=False, server_default=db.true())
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    foto_perfil = db.Column(db.String(200), default='default.jpg')
    foto_url = db.Column(db.String(500), nullable=True)
    descricao = db.Column(db.Text)
    
    # Relacionamentos
    # Só os serviços que estão no ar (os removidos pelo administrador ficam de fora)
    servicos_oferecidos = db.relationship(
        'Servico', back_populates='prestador', lazy=True,
        primaryjoin='and_(Usuario.id == Servico.prestador_id, Servico.removido == False)'
    )
    avaliacoes_recebidas = db.relationship('Avaliacao', foreign_keys='Avaliacao.prestador_id', back_populates='prestador', lazy=True)
    avaliacoes_feitas = db.relationship('Avaliacao', foreign_keys='Avaliacao.cliente_id', back_populates='cliente', lazy=True)
    favoritos = db.relationship('Favorito', foreign_keys='Favorito.cliente_id', back_populates='cliente', lazy=True)
    contratos_como_cliente = db.relationship('Contrato', foreign_keys='Contrato.cliente_id', back_populates='cliente', lazy=True)
    contratos_como_prestador = db.relationship('Contrato', foreign_keys='Contrato.prestador_id', back_populates='prestador', lazy=True)
    
    @property
    def excluida(self):
        """Conta excluída: o registro fica só para preservar o histórico de outras pessoas"""
        return (self.email or '').endswith('@removido.invalid')
    
    def set_password(self, password):
        self.senha_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)
    
    def marca_da_senha(self):
        """Trecho do hash da senha: muda quando a senha muda"""
        return (self.senha_hash or '')[-10:]
    
    def get_id(self):
        # Entra no cookie de login. Com a marca da senha, trocar a senha encerra os logins
        # em outros aparelhos (importante agora que o login pode durar 30 dias).
        return f'{self.id}:{self.marca_da_senha()}'
    
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
        from models import Contrato, Avaliacao
        contrato = Contrato.query.get(contrato_id)
        if contrato and contrato.cliente_id == self.id and contrato.status == 'concluido':
            avaliacao_existente = Avaliacao.query.filter_by(
                contrato_id=contrato_id,
                cliente_id=self.id
            ).first()
            return avaliacao_existente is None
        return False
    
    # ============================================
    # MÉTODOS PARA ASSINATURA
    # ============================================
    
    def assinatura_ativa(self):
        """Verifica se o prestador tem assinatura ativa"""
        if self.tipo != 'prestador':
            return False
        assinatura = Assinatura.query.filter_by(
            prestador_id=self.id,
            status='ativa'
        ).first()
        return assinatura is not None and assinatura.is_ativa()
    
    def plano_atual(self):
        """Retorna o plano atual do prestador"""
        if self.tipo != 'prestador':
            return None
        assinatura = Assinatura.query.filter_by(
            prestador_id=self.id,
            status='ativa'
        ).first()
        return assinatura.plano if assinatura and assinatura.is_ativa() else None
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'


class Servico(db.Model):
    __tablename__ = 'servicos'
    
    id = db.Column(db.Integer, primary_key=True)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(100))
    
    # Precificação
    tipo_preco = db.Column(db.String(20), default='fixo')  # fixo, hora, dia, metro, consulta
    preco = db.Column(db.Float)
    
    # Destaque
    destaque = db.Column(db.Boolean, default=False)
    destaque_pago = db.Column(db.Boolean, default=False)
    destaque_data_fim = db.Column(db.DateTime, nullable=True)
    plano_destaque = db.Column(db.String(20), nullable=True)  # 'basico', 'pro'
    
    data_postagem = db.Column(db.DateTime, default=datetime.utcnow)
    imagem_base64 = db.Column(db.Text, nullable=True)
    # Removido pelo administrador: some do site, mas o registro fica por causa dos contratos já feitos
    removido = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())
    
    # Relacionamentos
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id], back_populates='servicos_oferecidos')
    solicitacoes = db.relationship('Solicitacao', back_populates='servico', lazy=True)
    avaliacoes = db.relationship('Avaliacao', back_populates='servico', lazy=True)
    contratos = db.relationship('Contrato', back_populates='servico', lazy=True)
    # Fotos além da capa (a capa continua em imagem_base64, usada nos cards)
    imagens_extras = db.relationship('ServicoImagem', order_by='ServicoImagem.ordem, ServicoImagem.id',
                                     cascade='all, delete-orphan', lazy=True)
    
    def fotos(self):
        """Todas as fotos do serviço em base64: a capa primeiro, depois as extras"""
        capa = [self.imagem_base64] if self.imagem_base64 else []
        return capa + [img.imagem_base64 for img in self.imagens_extras]
    
    def fotos_versoes(self):
        """Um código por foto, que muda quando a foto muda (evita o navegador mostrar foto antiga em cache)"""
        return [format(zlib.crc32(foto.encode()), 'x') for foto in self.fotos()]
    
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
    
    def pode_ativar_destaque(self):
        """Verifica se o serviço pode ser destacado pelo plano"""
        if not self.prestador.assinatura_ativa():
            return False
        
        plano = self.prestador.plano_atual()
        limites = {'basico': 1, 'pro': 3}
        limite = limites.get(plano, 1)
        
        # Contar quantos serviços já estão em destaque
        destaque_ativos = Servico.query.filter_by(
            prestador_id=self.prestador_id,
            destaque=True
        ).count()
        
        return destaque_ativos < limite
    
    def __repr__(self):
        return f'<Servico {self.titulo}>'


class ServicoImagem(db.Model):
    """Foto adicional de um serviço"""
    __tablename__ = 'servico_imagens'
    
    id = db.Column(db.Integer, primary_key=True)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False, index=True)
    imagem_base64 = db.Column(db.Text, nullable=False)
    ordem = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<ServicoImagem {self.id} do servico {self.servico_id}>'


class Solicitacao(db.Model):
    __tablename__ = 'solicitacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    mensagem = db.Column(db.Text)
    status = db.Column(db.String(20), default='pendente')
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])
    servico = db.relationship('Servico', foreign_keys=[servico_id], back_populates='solicitacoes')
    
    def __repr__(self):
        return f'<Solicitacao {self.id}>'


class Contrato(db.Model):
    """Modelo para contratos de serviço entre cliente e prestador"""
    __tablename__ = 'contratos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    
    # Status do contrato
    status = db.Column(db.String(20), default='pendente')
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_aceite = db.Column(db.DateTime, nullable=True)
    data_inicio = db.Column(db.DateTime, nullable=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    
    # Detalhes do contrato
    mensagem_cliente = db.Column(db.Text, nullable=True)
    mensagem_prestador = db.Column(db.Text, nullable=True)
    preco_acordado = db.Column(db.Float, nullable=True)
    
    # Pagamento
    valor_servico = db.Column(db.Float, nullable=True)
    comissao_plataforma = db.Column(db.Float, default=10.0)
    valor_comissao = db.Column(db.Float, default=0.0)
    valor_liquido_prestador = db.Column(db.Float, default=0.0)
    pagamento_status = db.Column(db.String(20), default='pendente')
    transacao_id = db.Column(db.String(100), nullable=True)
    data_pagamento_cliente = db.Column(db.DateTime, nullable=True)
    data_pagamento_prestador = db.Column(db.DateTime, nullable=True)
    
    # Relacionamentos
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id], back_populates='contratos_como_cliente')
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id], back_populates='contratos_como_prestador')
    servico = db.relationship('Servico', foreign_keys=[servico_id], back_populates='contratos')
    avaliacao = db.relationship('Avaliacao', back_populates='contrato', uselist=False, cascade='all, delete-orphan')
    # Contrato formal com assinatura eletrônica (opcional, pago pelo prestador)
    formal = db.relationship('ContratoFormal', back_populates='contrato', uselist=False, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Contrato {self.id} - {self.status}>'
    
    def get_status_icon(self):
        icons = {
            'pendente': 'fa-clock',
            'aceito': 'fa-check-circle',
            'em_andamento': 'fa-spinner',
            'concluido': 'fa-star',
            'cancelado': 'fa-times-circle'
        }
        return icons.get(self.status, 'fa-file-contract')
    
    def get_status_color(self):
        colors = {
            'pendente': 'warning',
            'aceito': 'info',
            'em_andamento': 'primary',
            'concluido': 'success',
            'cancelado': 'danger'
        }
        return colors.get(self.status, 'secondary')
    
    def pode_avaliar(self, usuario_id):
        if self.status == 'concluido':
            if self.cliente_id == usuario_id:
                from models import Avaliacao
                avaliacao_existente = Avaliacao.query.filter_by(
                    contrato_id=self.id,
                    cliente_id=usuario_id
                ).first()
                return avaliacao_existente is None
        return False


class ContratoFormal(db.Model):
    """Contrato formal de prestação de serviços, com assinatura eletrônica das duas partes.
    
    status: aguardando_pagamento -> rascunho -> aguardando_assinaturas -> assinado
    """
    __tablename__ = 'contratos_formais'
    
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos.id'), nullable=False, unique=True)
    numero = db.Column(db.String(30), unique=True)
    status = db.Column(db.String(30), default='aguardando_pagamento', nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Taxa paga pelo prestador para liberar o contrato
    pagamento_id = db.Column(db.String(100), nullable=True)
    pago_em = db.Column(db.DateTime, nullable=True)
    
    # Dados das partes e condições (JSON). Congelado quando vai para assinatura.
    termos_json = db.Column(db.Text, nullable=True)
    motivo_reabertura = db.Column(db.Text, nullable=True)
    
    # Assinatura de cada parte: quando, de onde e com qual navegador
    cliente_assinou_em = db.Column(db.DateTime, nullable=True)
    cliente_ip = db.Column(db.String(60), nullable=True)
    cliente_dispositivo = db.Column(db.String(300), nullable=True)
    prestador_assinou_em = db.Column(db.DateTime, nullable=True)
    prestador_ip = db.Column(db.String(60), nullable=True)
    prestador_dispositivo = db.Column(db.String(300), nullable=True)
    
    # Código de confirmação enviado por e-mail (guardado só como hash)
    cliente_codigo_hash = db.Column(db.String(200), nullable=True)
    cliente_codigo_expira = db.Column(db.DateTime, nullable=True)
    cliente_codigo_tentativas = db.Column(db.Integer, default=0)
    prestador_codigo_hash = db.Column(db.String(200), nullable=True)
    prestador_codigo_expira = db.Column(db.DateTime, nullable=True)
    prestador_codigo_tentativas = db.Column(db.Integer, default=0)
    
    # Selo: hash SHA-256 do conteúdo + assinaturas, gerado quando os dois assinam
    hash_documento = db.Column(db.String(64), nullable=True, index=True)
    selado_em = db.Column(db.DateTime, nullable=True)
    
    contrato = db.relationship('Contrato', back_populates='formal')
    
    def __repr__(self):
        return f'<ContratoFormal {self.numero} - {self.status}>'


class Avaliacao(db.Model):
    __tablename__ = 'avaliacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contratos.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=True)
    
    nota = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    
    # Avaliações detalhadas
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
    servico = db.relationship('Servico', foreign_keys=[servico_id], back_populates='avaliacoes')
    contrato = db.relationship('Contrato', foreign_keys=[contrato_id], back_populates='avaliacao')
    
    def __repr__(self):
        return f'<Avaliacao {self.id} - Nota: {self.nota}>'
    
    def pode_editar(self, usuario_id):
        if self.cliente_id == usuario_id:
            dias_passados = (datetime.utcnow() - self.data_avaliacao).days
            return dias_passados <= 7
        return False
    
    def get_media_categorias(self):
        categorias = [self.qualidade, self.pontualidade, self.comunicacao, self.preco_justo]
        validas = [c for c in categorias if c is not None]
        if validas:
            return round(sum(validas) / len(validas), 1)
        return None


class Reclamacao(db.Model):
    __tablename__ = 'reclamacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    avaliacao_id = db.Column(db.Integer, db.ForeignKey('avaliacoes.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pendente')
    data_reclamacao = db.Column(db.DateTime, default=datetime.utcnow)
    resposta_admin = db.Column(db.Text, nullable=True)
    data_resposta = db.Column(db.DateTime, nullable=True)
    
    avaliacao = db.relationship('Avaliacao', backref='reclamacoes')
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    
    def __repr__(self):
        return f'<Reclamacao {self.id} - {self.status}>'


class Favorito(db.Model):
    __tablename__ = 'favoritos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    data_adicao = db.Column(db.DateTime, default=datetime.utcnow)
    
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id], back_populates='favoritos')
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id])
    
    __table_args__ = (db.UniqueConstraint('cliente_id', 'prestador_id', name='unique_favorito'),)
    
    def __repr__(self):
        return f'<Favorito {self.id}>'


class InscricaoPush(db.Model):
    """Um navegador/aparelho em que o usuário ativou as notificações push"""
    __tablename__ = 'inscricoes_push'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    endpoint = db.Column(db.String(1000), nullable=False, unique=True)
    p256dh = db.Column(db.String(200), nullable=False)
    auth = db.Column(db.String(100), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InscricaoPush {self.id} do usuario {self.usuario_id}>'


class PedidoOrcamento(db.Model):
    """Pedido de orçamento: o cliente descreve o que precisa e os prestadores respondem"""
    __tablename__ = 'pedidos_orcamento'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, index=True)
    categoria = db.Column(db.String(100), nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False)
    local = db.Column(db.String(200), nullable=False)
    urgencia = db.Column(db.String(20), default='flexivel')  # urgente, semana, mes, flexivel
    status = db.Column(db.String(20), default='aberto', nullable=False)  # aberto, fechado
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])
    respostas = db.relationship('RespostaOrcamento', back_populates='pedido', order_by='RespostaOrcamento.criado_em',
                                cascade='all, delete-orphan', lazy=True)
    
    def __repr__(self):
        return f'<PedidoOrcamento {self.id} - {self.categoria}>'


class RespostaOrcamento(db.Model):
    """Proposta de um prestador para um pedido de orçamento"""
    __tablename__ = 'respostas_orcamento'
    
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos_orcamento.id'), nullable=False, index=True)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    valor = db.Column(db.Float, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    pedido = db.relationship('PedidoOrcamento', back_populates='respostas')
    prestador = db.relationship('Usuario', foreign_keys=[prestador_id])
    
    __table_args__ = (db.UniqueConstraint('pedido_id', 'prestador_id', name='uma_resposta_por_prestador'),)
    
    def __repr__(self):
        return f'<RespostaOrcamento {self.id}>'


class Mensagem(db.Model):
    __tablename__ = 'mensagens'
    
    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    lida = db.Column(db.Boolean, default=False)
    imagem_base64 = db.Column(db.Text, nullable=True)  # foto enviada pelo chat (JPEG)
    # "Apagar conversa" vale só para quem apagou; a outra pessoa continua vendo
    apagada_remetente = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())
    apagada_destinatario = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())
    
    remetente = db.relationship('Usuario', foreign_keys=[remetente_id])
    destinatario = db.relationship('Usuario', foreign_keys=[destinatario_id])
    
    def __repr__(self):
        return f'<Mensagem {self.id}>'


class Assinatura(db.Model):
    __tablename__ = 'assinaturas'
    
    id = db.Column(db.Integer, primary_key=True)
    prestador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    plano = db.Column(db.String(20), nullable=False)  # 'basico', 'pro'
    status = db.Column(db.String(20), default='ativa')  # 'ativa', 'cancelada', 'expirada'
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_fim = db.Column(db.DateTime, nullable=False)
    ultimo_pagamento = db.Column(db.DateTime, nullable=True)
    pagamento_id = db.Column(db.String(100), nullable=True)
    
    prestador = db.relationship('Usuario', backref='assinatura', foreign_keys=[prestador_id])
    
    def is_ativa(self):
        return self.status == 'ativa' and datetime.utcnow() < self.data_fim
    
    def dias_restantes(self):
        if not self.is_ativa():
            return 0
        return (self.data_fim - datetime.utcnow()).days
    
    def __repr__(self):
        return f'<Assinatura {self.id} - {self.plano} - {self.status}>'


def servicos_visiveis():
    """Serviços de contas ativas (os de contas desativadas ou excluídas ficam ocultos)"""
    return Servico.query.join(Usuario, Servico.prestador_id == Usuario.id).filter(
        Usuario.desativada == False, Servico.removido == False
    )


def servicos_ativos():
    """Serviços que não foram removidos (inclui os de contas desativadas; use nas telas do dono e do admin)"""
    return Servico.query.filter(Servico.removido == False)
