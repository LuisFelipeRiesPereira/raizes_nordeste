from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.infrastructure.database.base import Base
from app.domain.enums.enums import (
    PerfilUsuario, CanalPedido, StatusPedido,
    StatusPagamento, TipoMovimentacao
)

# -----------
# todas as tabelas do banco definidas aqui como classes
# o sqlalchemy cria as tabelas e cuida dos relacionamentos
# -----------

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)  # nunca salvar senha pura
    perfil = Column(SAEnum(PerfilUsuario), nullable=False, default=PerfilUsuario.CLIENTE)
    consentimento_lgpd = Column(Boolean, default=False)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    pedidos = relationship("Pedido", back_populates="cliente", foreign_keys="Pedido.cliente_id")
    fidelidade = relationship("Fidelidade", back_populates="cliente", uselist=False)
    logs = relationship("LogAuditoria", back_populates="usuario")


class Unidade(Base):
    __tablename__ = "unidades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(120), nullable=False)
    cidade = Column(String(100), nullable=False)
    estado = Column(String(2), nullable=False)
    endereco = Column(String(255), nullable=False)
    ativa = Column(Boolean, default=True)
    criada_em = Column(DateTime, default=datetime.utcnow)
    estoques = relationship("Estoque", back_populates="unidade")
    pedidos = relationship("Pedido", back_populates="unidade")


class Produto(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text)
    preco = Column(Float, nullable=False)
    categoria = Column(String(80))
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    estoques = relationship("Estoque", back_populates="produto")
    itens_pedido = relationship("ItemPedido", back_populates="produto")


# -----------
# estoque e por unidade
# cada loja tem o proprio saldo separado
# -----------

class Estoque(Base):
    __tablename__ = "estoques"
    id = Column(Integer, primary_key=True, autoincrement=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=0)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    produto = relationship("Produto", back_populates="estoques")
    unidade = relationship("Unidade", back_populates="estoques")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="estoque")
    # cada produto so pode ter UM registro de estoque por unidade
    __table_args__ = (
        UniqueConstraint("produto_id", "unidade_id", name="uq_estoque_produto_unidade"),
    )


class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacoes_estoque"
    id = Column(Integer, primary_key=True, autoincrement=True)
    estoque_id = Column(Integer, ForeignKey("estoques.id"), nullable=False)
    tipo = Column(SAEnum(TipoMovimentacao), nullable=False)
    quantidade = Column(Integer, nullable=False)
    motivo = Column(String(200))
    criado_em = Column(DateTime, default=datetime.utcnow)
    estoque = relationship("Estoque", back_populates="movimentacoes")


# -----------
# pedido tem que ter canal_pedido obrigatorio
# e o status começa sempre em aguardando pagamento
# -----------

class Pedido(Base):
    __tablename__ = "pedidos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    canal_pedido = Column(SAEnum(CanalPedido), nullable=False)
    status = Column(SAEnum(StatusPedido), nullable=False, default=StatusPedido.AGUARDANDO_PAGAMENTO)
    valor_total = Column(Float, nullable=False, default=0.0)
    observacao = Column(Text)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cliente = relationship("Usuario", back_populates="pedidos", foreign_keys=[cliente_id])
    unidade = relationship("Unidade", back_populates="pedidos")
    itens = relationship("ItemPedido", back_populates="pedido", cascade="all, delete-orphan")
    pagamento = relationship("Pagamento", back_populates="pedido", uselist=False)


class ItemPedido(Base):
    __tablename__ = "itens_pedido"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Float, nullable=False)
    pedido = relationship("Pedido", back_populates="itens")
    produto = relationship("Produto", back_populates="itens_pedido")


class Pagamento(Base):
    __tablename__ = "pagamentos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), unique=True, nullable=False)
    status = Column(SAEnum(StatusPagamento), nullable=False, default=StatusPagamento.PENDENTE)
    codigo_transacao = Column(String(100))
    valor = Column(Float, nullable=False)
    forma_pagamento = Column(String(50), default="MOCK")
    criado_em = Column(DateTime, default=datetime.utcnow)
    processado_em = Column(DateTime)
    pedido = relationship("Pedido", back_populates="pagamento")


class Fidelidade(Base):
    __tablename__ = "fidelidade"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False)
    pontos_acumulados = Column(Integer, default=0)
    pontos_resgatados = Column(Integer, default=0)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cliente = relationship("Usuario", back_populates="fidelidade")


# -----------
# todo evento importante vira um log aqui
# nao apaga nenhum registro dessa tabela
# -----------

class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    acao = Column(String(100), nullable=False)
    recurso = Column(String(100))
    recurso_id = Column(Integer)
    detalhes = Column(Text)
    ip_origem = Column(String(50))
    criado_em = Column(DateTime, default=datetime.utcnow)
    usuario = relationship("Usuario", back_populates="logs")
