"""Criação inicial das tabelas - Raízes do Nordeste

Revision ID: 001_inicial
Revises: 
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_inicial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'usuarios',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('email', sa.String(180), nullable=False),
        sa.Column('senha_hash', sa.String(255), nullable=False),
        sa.Column('perfil', sa.Enum('ADMIN', 'GERENTE', 'CLIENTE', 'COZINHA', 'ATENDENTE',
                                    name='perfilusuario'), nullable=False),
        sa.Column('consentimento_lgpd', sa.Boolean(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_usuarios_email', 'usuarios', ['email'])

    op.create_table(
        'unidades',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('cidade', sa.String(100), nullable=False),
        sa.Column('estado', sa.String(2), nullable=False),
        sa.Column('endereco', sa.String(255), nullable=False),
        sa.Column('ativa', sa.Boolean(), nullable=True),
        sa.Column('criada_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'produtos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.String(150), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('preco', sa.Float(), nullable=False),
        sa.Column('categoria', sa.String(80), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'estoques',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('produto_id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['produto_id'], ['produtos.id']),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidades.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('produto_id', 'unidade_id', name='uq_estoque_produto_unidade'),
    )

    op.create_table(
        'movimentacoes_estoque',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('estoque_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.Enum('ENTRADA', 'SAIDA', name='tipomovimentacao'), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('motivo', sa.String(200), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['estoque_id'], ['estoques.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'pedidos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), nullable=False),
        sa.Column('canal_pedido', sa.Enum('APP', 'TOTEM', 'BALCAO', 'PICKUP', 'WEB',
                                          name='canalpedido'), nullable=False),
        sa.Column('status', sa.Enum('AGUARDANDO_PAGAMENTO', 'PAGO', 'EM_PREPARO', 'PRONTO',
                                    'ENTREGUE', 'CANCELADO', name='statuspedido'), nullable=False),
        sa.Column('valor_total', sa.Float(), nullable=False),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidades.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'itens_pedido',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pedido_id', sa.Integer(), nullable=False),
        sa.Column('produto_id', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.Column('preco_unitario', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id']),
        sa.ForeignKeyConstraint(['produto_id'], ['produtos.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'pagamentos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pedido_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDENTE', 'APROVADO', 'RECUSADO',
                                    name='statuspagamento'), nullable=False),
        sa.Column('codigo_transacao', sa.String(100), nullable=True),
        sa.Column('valor', sa.Float(), nullable=False),
        sa.Column('forma_pagamento', sa.String(50), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('processado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pedido_id'),
    )

    op.create_table(
        'fidelidade',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('pontos_acumulados', sa.Integer(), nullable=True),
        sa.Column('pontos_resgatados', sa.Integer(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['cliente_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cliente_id'),
    )

    op.create_table(
        'logs_auditoria',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('acao', sa.String(100), nullable=False),
        sa.Column('recurso', sa.String(100), nullable=True),
        sa.Column('recurso_id', sa.Integer(), nullable=True),
        sa.Column('detalhes', sa.Text(), nullable=True),
        sa.Column('ip_origem', sa.String(50), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    for table in ['logs_auditoria', 'fidelidade', 'pagamentos', 'itens_pedido',
                  'pedidos', 'movimentacoes_estoque', 'estoques', 'produtos', 'unidades', 'usuarios']:
        op.drop_table(table)
    for enum in ['perfilusuario', 'canalpedido', 'statuspedido', 'statuspagamento', 'tipomovimentacao']:
        op.execute(f'DROP TYPE IF EXISTS {enum}')
