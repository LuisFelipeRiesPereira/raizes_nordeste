import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.domain.models.models import (
    Pedido, ItemPedido, Produto, Estoque, Pagamento,
    MovimentacaoEstoque, Fidelidade, LogAuditoria
)
from app.domain.enums.enums import (
    CanalPedido, StatusPedido, StatusPagamento, TipoMovimentacao
)

# -----------
# criar pedido
# entra cliente unidade canal e lista de itens
# sai pedido salvo com estoque decrementado
# -----------

def criar_pedido(db: Session, cliente_id: int, unidade_id: int,
                 canal_pedido: CanalPedido, itens: List[dict],
                 observacao: str = None) -> Pedido:
    if not itens:
        raise ValueError("ITENS_OBRIGATORIOS")

    valor_total = 0.0
    itens_validados = []

    # valida cada item antes de salvar qualquer coisa
    for item in itens:
        produto = db.query(Produto).filter(
            Produto.id == item["produto_id"], Produto.ativo == True
        ).first()
        if not produto:
            raise LookupError(f"PRODUTO_NAO_ENCONTRADO:{item['produto_id']}")

        estoque = db.query(Estoque).filter(
            Estoque.produto_id == item["produto_id"],
            Estoque.unidade_id == unidade_id
        ).first()
        if not estoque or estoque.quantidade < item["quantidade"]:
            disponivel = estoque.quantidade if estoque else 0
            raise OverflowError(f"ESTOQUE_INSUFICIENTE:{produto.id}:{disponivel}")

        valor_total += produto.preco * item["quantidade"]
        itens_validados.append((produto, estoque, item["quantidade"]))

    pedido = Pedido(
        cliente_id=cliente_id, unidade_id=unidade_id,
        canal_pedido=canal_pedido,
        status=StatusPedido.AGUARDANDO_PAGAMENTO,
        valor_total=round(valor_total, 2),
        observacao=observacao,
    )
    db.add(pedido)
    db.flush()

    # salva os itens e desconta do estoque
    for produto, estoque, quantidade in itens_validados:
        db.add(ItemPedido(
            pedido_id=pedido.id, produto_id=produto.id,
            quantidade=quantidade, preco_unitario=produto.preco,
        ))
        estoque.quantidade -= quantidade
        estoque.atualizado_em = datetime.utcnow()
        db.add(MovimentacaoEstoque(
            estoque_id=estoque.id, tipo=TipoMovimentacao.SAIDA,
            quantidade=quantidade, motivo=f"Pedido #{pedido.id}",
        ))

    db.add(LogAuditoria(
        usuario_id=cliente_id, acao="PEDIDO_CRIADO",
        recurso="pedidos", recurso_id=pedido.id,
        detalhes=f"canal={canal_pedido.value}",
    ))
    db.commit()
    db.refresh(pedido)
    return pedido


# -----------
# pagamento mock
# valor ate 200 aprova acima recusa
# serve pra testar os dois cenarios sem gateway real
# -----------

def processar_pagamento_mock(db: Session, pedido_id: int, usuario_id: int) -> Pagamento:
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise LookupError("PEDIDO_NAO_ENCONTRADO")
    if pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO:
        raise ValueError("STATUS_INVALIDO_PARA_PAGAMENTO")

    existente = db.query(Pagamento).filter(Pagamento.pedido_id == pedido_id).first()
    if existente and existente.status == StatusPagamento.APROVADO:
        raise ValueError("PAGAMENTO_JA_PROCESSADO")

    status_mock = StatusPagamento.APROVADO if pedido.valor_total <= 200.0 else StatusPagamento.RECUSADO
    codigo = f"TRX-{uuid.uuid4().hex[:12].upper()}"

    if existente:
        existente.status = status_mock
        existente.codigo_transacao = codigo
        existente.processado_em = datetime.utcnow()
        pagamento = existente
    else:
        pagamento = Pagamento(
            pedido_id=pedido_id, status=status_mock,
            codigo_transacao=codigo, valor=pedido.valor_total,
            processado_em=datetime.utcnow(),
        )
        db.add(pagamento)

    if status_mock == StatusPagamento.APROVADO:
        pedido.status = StatusPedido.PAGO
        pedido.atualizado_em = datetime.utcnow()
        _creditar_pontos(db, pedido.cliente_id, pedido.valor_total)
        db.add(LogAuditoria(
            usuario_id=usuario_id, acao="PAGAMENTO_APROVADO",
            recurso="pagamentos", recurso_id=pedido_id,
        ))
    else:
        db.add(LogAuditoria(
            usuario_id=usuario_id, acao="PAGAMENTO_RECUSADO",
            recurso="pagamentos", recurso_id=pedido_id,
            detalhes=f"valor={pedido.valor_total}",
        ))

    db.commit()
    db.refresh(pagamento)
    return pagamento


# -----------
# maquina de estados do pedido
# so deixa transicoes validas acontecerem
# -----------

def atualizar_status_pedido(db: Session, pedido_id: int,
                             novo_status: StatusPedido, usuario_id: int) -> Pedido:
    TRANSICOES = {
        StatusPedido.AGUARDANDO_PAGAMENTO: [StatusPedido.CANCELADO],
        StatusPedido.PAGO: [StatusPedido.EM_PREPARO, StatusPedido.CANCELADO],
        StatusPedido.EM_PREPARO: [StatusPedido.PRONTO],
        StatusPedido.PRONTO: [StatusPedido.ENTREGUE],
        StatusPedido.ENTREGUE: [],
        StatusPedido.CANCELADO: [],
    }
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise LookupError("PEDIDO_NAO_ENCONTRADO")
    if novo_status not in TRANSICOES.get(pedido.status, []):
        raise ValueError(f"TRANSICAO_INVALIDA:{pedido.status.value}->{novo_status.value}")

    status_anterior = pedido.status
    pedido.status = novo_status
    pedido.atualizado_em = datetime.utcnow()
    db.add(LogAuditoria(
        usuario_id=usuario_id, acao="STATUS_PEDIDO_ALTERADO",
        recurso="pedidos", recurso_id=pedido_id,
        detalhes=f"{status_anterior.value}->{novo_status.value}",
    ))
    db.commit()
    db.refresh(pedido)
    return pedido


def _creditar_pontos(db: Session, cliente_id: int, valor: float):
    # 1 real gasto vira 1 ponto
    pontos = int(valor)
    fidelidade = db.query(Fidelidade).filter(Fidelidade.cliente_id == cliente_id).first()
    if fidelidade:
        fidelidade.pontos_acumulados += pontos
        fidelidade.atualizado_em = datetime.utcnow()


# -----------
# cancelar pedido
# operacao sensivel exige motivo
# devolve o estoque pra unidade
# registra log com a categoria CANCELAMENTO
# -----------

def cancelar_pedido(db: Session, pedido_id: int, motivo: str, usuario_id: int) -> Pedido:
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise LookupError("PEDIDO_NAO_ENCONTRADO")

    # so deixa cancelar enquanto nao foi pra cozinha
    # depois disso a comida ja esta sendo preparada
    if pedido.status not in [StatusPedido.AGUARDANDO_PAGAMENTO, StatusPedido.PAGO]:
        raise ValueError(f"CANCELAMENTO_NAO_PERMITIDO:{pedido.status.value}")

    if not motivo or len(motivo.strip()) < 5:
        raise ValueError("MOTIVO_OBRIGATORIO")

    status_anterior = pedido.status
    pedido.status = StatusPedido.CANCELADO
    pedido.atualizado_em = datetime.utcnow()

    # devolve o estoque que tinha sido reservado
    for item in pedido.itens:
        estoque = db.query(Estoque).filter(
            Estoque.produto_id == item.produto_id,
            Estoque.unidade_id == pedido.unidade_id
        ).first()
        if estoque:
            estoque.quantidade += item.quantidade
            estoque.atualizado_em = datetime.utcnow()
            db.add(MovimentacaoEstoque(
                estoque_id=estoque.id,
                tipo=TipoMovimentacao.ENTRADA,
                quantidade=item.quantidade,
                motivo=f"Cancelamento Pedido #{pedido.id}",
            ))

    # log de auditoria sensivel
    # essa categoria CANCELAMENTO eh acompanhada pela matriz
    db.add(LogAuditoria(
        usuario_id=usuario_id,
        acao="PEDIDO_CANCELADO",
        recurso="pedidos",
        recurso_id=pedido_id,
        detalhes=f"de={status_anterior.value} motivo={motivo}",
    ))

    db.commit()
    db.refresh(pedido)
    return pedido
