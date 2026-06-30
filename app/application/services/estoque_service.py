from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.models.models import (
    Estoque, MovimentacaoEstoque, Produto, Unidade, LogAuditoria
)
from app.domain.enums.enums import TipoMovimentacao

# -----------
# toda movimentacao de estoque passa por aqui
# entra produto unidade tipo e quantidade
# sai estoque atualizado e historico registrado
# -----------

def movimentar_estoque(db: Session, produto_id: int, unidade_id: int,
                       tipo: TipoMovimentacao, quantidade: int,
                       motivo: str, usuario_id: int) -> Estoque:
    if quantidade <= 0:
        raise ValueError("QUANTIDADE_INVALIDA")

    produto = db.query(Produto).filter(Produto.id == produto_id, Produto.ativo == True).first()
    if not produto:
        raise LookupError("PRODUTO_NAO_ENCONTRADO")

    unidade = db.query(Unidade).filter(Unidade.id == unidade_id, Unidade.ativa == True).first()
    if not unidade:
        raise LookupError("UNIDADE_NAO_ENCONTRADA")

    # busca o estoque dessa unidade
    # se nao existir cria do zero com quantidade 0
    estoque = db.query(Estoque).filter(
        Estoque.produto_id == produto_id,
        Estoque.unidade_id == unidade_id
    ).first()

    if not estoque:
        estoque = Estoque(produto_id=produto_id, unidade_id=unidade_id, quantidade=0)
        db.add(estoque)
        db.flush()

    if tipo == TipoMovimentacao.SAIDA:
        if estoque.quantidade < quantidade:
            raise OverflowError(f"ESTOQUE_INSUFICIENTE:{estoque.quantidade}")
        estoque.quantidade -= quantidade
    else:
        estoque.quantidade += quantidade

    estoque.atualizado_em = datetime.utcnow()

    # -----------
    # registra a movimentacao e o log de auditoria
    # -----------
    db.add(MovimentacaoEstoque(
        estoque_id=estoque.id, tipo=tipo,
        quantidade=quantidade, motivo=motivo,
    ))
    db.add(LogAuditoria(
        usuario_id=usuario_id,
        acao=f"ESTOQUE_{tipo.value}",
        recurso="estoques", recurso_id=estoque.id,
        detalhes=f"produto={produto_id} unidade={unidade_id} qtd={quantidade}",
    ))
    db.commit()
    db.refresh(estoque)
    return estoque
