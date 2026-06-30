from datetime import datetime
from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session

from app.infrastructure.database.base import SessionLocal
from app.domain.models.models import Produto, Unidade, Estoque, Pagamento, Fidelidade
from app.domain.enums.enums import PerfilUsuario, TipoMovimentacao
from app.api.middleware.auth_middleware import requer_autenticacao
from app.application.services import estoque_service, pedido_service

produtos_bp = Blueprint("produtos", __name__, url_prefix="/produtos")
unidades_bp = Blueprint("unidades", __name__, url_prefix="/unidades")
estoque_bp = Blueprint("estoque", __name__, url_prefix="/estoque")
pagamentos_bp = Blueprint("pagamentos", __name__, url_prefix="/pagamentos")
fidelidade_bp = Blueprint("fidelidade", __name__, url_prefix="/fidelidade")

_ADMIN_GERENTE = [PerfilUsuario.ADMIN, PerfilUsuario.GERENTE]


def _erro(codigo, mensagem, status, detalhes=None):
    return jsonify({
        "error": codigo, "message": mensagem,
        "details": detalhes or [],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "path": request.path,
    }), status


# -----------
# produtos
# listagem e publica criacao exige admin ou gerente
# -----------

# -----------
# listar produtos
# se passar ?unidade_id=N filtra so o que tem estoque naquela loja
# isso atende o requisito de cardapio por unidade
# unidades com cozinha reduzida nao mostram produtos sem estoque
# -----------

@produtos_bp.get("")
def listar_produtos():
    db: Session = SessionLocal()
    try:
        page = max(int(request.args.get("page", 1)), 1)
        limit = min(int(request.args.get("limit", 10)), 100)
        unidade_id = request.args.get("unidade_id")
        categoria = request.args.get("categoria")

        query = db.query(Produto).filter(Produto.ativo == True)

        # filtro de cardapio por unidade
        # retorna so produtos com estoque > 0 naquela unidade
        if unidade_id:
            try:
                uid = int(unidade_id)
            except ValueError:
                return _erro("UNIDADE_INVALIDA", "unidade_id deve ser numero inteiro.", 422)
            query = query.join(Estoque, Estoque.produto_id == Produto.id) \
                         .filter(Estoque.unidade_id == uid) \
                         .filter(Estoque.quantidade > 0)

        if categoria:
            query = query.filter(Produto.categoria.ilike(f"%{categoria}%"))

        total = query.count()
        produtos = query.order_by(Produto.nome).offset((page - 1) * limit).limit(limit).all()

        # se filtrou por unidade vou anexar o saldo de estoque na resposta
        # ajuda a cozinha e o app a mostrarem quantos itens ainda tem
        data = []
        for p in produtos:
            item = {"id": p.id, "nome": p.nome, "descricao": p.descricao,
                    "preco": p.preco, "categoria": p.categoria}
            if unidade_id:
                est = db.query(Estoque).filter(
                    Estoque.produto_id == p.id,
                    Estoque.unidade_id == int(unidade_id)
                ).first()
                item["estoque_disponivel"] = est.quantidade if est else 0
            data.append(item)

        return jsonify({
            "data": data,
            "pagina": page, "limite": limit, "total": total,
            "unidade_id": int(unidade_id) if unidade_id else None,
        }), 200
    finally:
        db.close()


@produtos_bp.get("/<int:produto_id>")
def obter_produto(produto_id):
    db: Session = SessionLocal()
    try:
        p = db.query(Produto).filter(Produto.id == produto_id, Produto.ativo == True).first()
        if not p:
            return _erro("PRODUTO_NAO_ENCONTRADO", "Produto nao encontrado.", 404)
        return jsonify({"id": p.id, "nome": p.nome, "descricao": p.descricao,
                        "preco": p.preco, "categoria": p.categoria}), 200
    finally:
        db.close()


@produtos_bp.post("")
@requer_autenticacao(_ADMIN_GERENTE)
def criar_produto():
    dados = request.get_json(silent=True) or {}
    erros = [{"field": c, "issue": "obrigatorio"} for c in ["nome", "preco"] if not dados.get(c)]
    if erros:
        return _erro("DADOS_INVALIDOS", "Campos invalidos.", 422, erros)
    db: Session = SessionLocal()
    try:
        p = Produto(nome=dados["nome"], descricao=dados.get("descricao"),
                    preco=float(dados["preco"]), categoria=dados.get("categoria"))
        db.add(p)
        db.commit()
        db.refresh(p)
        return jsonify({"id": p.id, "nome": p.nome, "preco": p.preco}), 201
    finally:
        db.close()


# -----------
# unidades
# listagem publica criacao so admin
# -----------

@unidades_bp.get("")
def listar_unidades():
    db: Session = SessionLocal()
    try:
        unidades = db.query(Unidade).filter(Unidade.ativa == True).all()
        return jsonify({
            "data": [{"id": u.id, "nome": u.nome, "cidade": u.cidade,
                      "estado": u.estado, "endereco": u.endereco} for u in unidades]
        }), 200
    finally:
        db.close()


@unidades_bp.post("")
@requer_autenticacao([PerfilUsuario.ADMIN])
def criar_unidade():
    dados = request.get_json(silent=True) or {}
    erros = [{"field": c, "issue": "obrigatorio"}
             for c in ["nome", "cidade", "estado", "endereco"] if not dados.get(c)]
    if erros:
        return _erro("DADOS_INVALIDOS", "Campos obrigatorios ausentes.", 422, erros)
    db: Session = SessionLocal()
    try:
        u = Unidade(nome=dados["nome"], cidade=dados["cidade"],
                    estado=dados["estado"], endereco=dados["endereco"])
        db.add(u)
        db.commit()
        db.refresh(u)
        return jsonify({"id": u.id, "nome": u.nome, "cidade": u.cidade}), 201
    finally:
        db.close()


# -----------
# estoque
# so admin e gerente movimentam
# entra produto unidade e quantidade
# sai quantidade atualizada
# -----------

@estoque_bp.get("")
@requer_autenticacao(_ADMIN_GERENTE)
def consultar_estoque():
    db: Session = SessionLocal()
    try:
        query = db.query(Estoque)
        if request.args.get("unidade_id"):
            query = query.filter(Estoque.unidade_id == int(request.args["unidade_id"]))
        if request.args.get("produto_id"):
            query = query.filter(Estoque.produto_id == int(request.args["produto_id"]))
        estoques = query.all()
        return jsonify({
            "data": [{"id": e.id, "produto_id": e.produto_id, "unidade_id": e.unidade_id,
                      "quantidade": e.quantidade} for e in estoques]
        }), 200
    finally:
        db.close()


@estoque_bp.post("/entrada")
@requer_autenticacao(_ADMIN_GERENTE)
def entrada_estoque():
    dados = request.get_json(silent=True) or {}
    erros = [{"field": c, "issue": "obrigatorio"}
             for c in ["produto_id", "unidade_id", "quantidade"] if not dados.get(c)]
    if erros:
        return _erro("DADOS_INVALIDOS", "Campos obrigatorios ausentes.", 422, erros)
    db: Session = SessionLocal()
    try:
        e = estoque_service.movimentar_estoque(
            db=db, produto_id=int(dados["produto_id"]),
            unidade_id=int(dados["unidade_id"]),
            tipo=TipoMovimentacao.ENTRADA,
            quantidade=int(dados["quantidade"]),
            motivo=dados.get("motivo", "Entrada manual"),
            usuario_id=g.usuario_atual.id,
        )
        return jsonify({"estoque_id": e.id, "produto_id": e.produto_id,
                        "unidade_id": e.unidade_id, "quantidade_atual": e.quantidade}), 200
    except LookupError as err:
        return _erro("RECURSO_NAO_ENCONTRADO", str(err), 404)
    except ValueError as err:
        return _erro("QUANTIDADE_INVALIDA", str(err), 422)
    finally:
        db.close()


@estoque_bp.post("/saida")
@requer_autenticacao(_ADMIN_GERENTE)
def saida_estoque():
    dados = request.get_json(silent=True) or {}
    erros = [{"field": c, "issue": "obrigatorio"}
             for c in ["produto_id", "unidade_id", "quantidade"] if not dados.get(c)]
    if erros:
        return _erro("DADOS_INVALIDOS", "Campos obrigatorios ausentes.", 422, erros)
    db: Session = SessionLocal()
    try:
        e = estoque_service.movimentar_estoque(
            db=db, produto_id=int(dados["produto_id"]),
            unidade_id=int(dados["unidade_id"]),
            tipo=TipoMovimentacao.SAIDA,
            quantidade=int(dados["quantidade"]),
            motivo=dados.get("motivo", "Saida manual"),
            usuario_id=g.usuario_atual.id,
        )
        return jsonify({"estoque_id": e.id, "produto_id": e.produto_id,
                        "unidade_id": e.unidade_id, "quantidade_atual": e.quantidade}), 200
    except LookupError as err:
        return _erro("RECURSO_NAO_ENCONTRADO", str(err), 404)
    except OverflowError as err:
        disponivel = str(err).split(":")[-1]
        return _erro("ESTOQUE_INSUFICIENTE", "Estoque insuficiente.", 409,
                     [{"field": "quantidade", "issue": f"Disponivel: {disponivel}"}])
    except ValueError as err:
        return _erro("QUANTIDADE_INVALIDA", str(err), 422)
    finally:
        db.close()


# -----------
# pagamento mock
# entra pedido_id
# sai aprovado se valor ate 200 recusado se acima
# -----------

@pagamentos_bp.post("/mock")
@requer_autenticacao([PerfilUsuario.CLIENTE, PerfilUsuario.ADMIN, PerfilUsuario.ATENDENTE])
def processar_pagamento():
    dados = request.get_json(silent=True) or {}
    if not dados.get("pedido_id"):
        return _erro("DADOS_INVALIDOS", "pedido_id e obrigatorio.", 422,
                     [{"field": "pedido_id", "issue": "obrigatorio"}])
    db: Session = SessionLocal()
    try:
        pagamento = pedido_service.processar_pagamento_mock(
            db=db, pedido_id=int(dados["pedido_id"]),
            usuario_id=g.usuario_atual.id
        )
        return jsonify({
            "pagamento_id": pagamento.id,
            "pedido_id": pagamento.pedido_id,
            "status": pagamento.status.value,
            "codigo_transacao": pagamento.codigo_transacao,
            "valor": pagamento.valor,
            "processado_em": pagamento.processado_em.isoformat() + "Z" if pagamento.processado_em else None,
        }), 200
    except LookupError as err:
        return _erro("PEDIDO_NAO_ENCONTRADO", str(err), 404)
    except ValueError as err:
        return _erro("PAGAMENTO_INVALIDO", str(err), 409)
    finally:
        db.close()


# -----------
# fidelidade
# 1 real gasto vira 1 ponto
# resgate minimo de 100 pontos vale R$10
# -----------

@fidelidade_bp.get("/<int:cliente_id>")
@requer_autenticacao()
def consultar_fidelidade(cliente_id):
    usuario = g.usuario_atual
    if usuario.perfil == PerfilUsuario.CLIENTE and usuario.id != cliente_id:
        return _erro("SEM_PERMISSAO", "Acesso negado.", 403)
    db: Session = SessionLocal()
    try:
        f = db.query(Fidelidade).filter(Fidelidade.cliente_id == cliente_id).first()
        if not f:
            return _erro("FIDELIDADE_NAO_ENCONTRADA", "Programa de fidelidade nao encontrado.", 404)
        saldo = f.pontos_acumulados - f.pontos_resgatados
        return jsonify({
            "cliente_id": f.cliente_id,
            "pontos_acumulados": f.pontos_acumulados,
            "pontos_resgatados": f.pontos_resgatados,
            "saldo_pontos": saldo,
            "equivalente_reais": round(saldo * 0.10, 2),
        }), 200
    finally:
        db.close()


@fidelidade_bp.post("/resgatar")
@requer_autenticacao([PerfilUsuario.CLIENTE])
def resgatar_pontos():
    dados = request.get_json(silent=True) or {}
    pontos = int(dados.get("pontos", 0))
    if pontos < 100:
        return _erro("PONTOS_INSUFICIENTES", "Minimo de 100 pontos para resgate.", 422,
                     [{"field": "pontos", "issue": "minimo 100"}])
    db: Session = SessionLocal()
    try:
        usuario = g.usuario_atual
        f = db.query(Fidelidade).filter(Fidelidade.cliente_id == usuario.id).first()
        if not f:
            return _erro("FIDELIDADE_NAO_ENCONTRADA", "Programa nao encontrado.", 404)
        saldo = f.pontos_acumulados - f.pontos_resgatados
        if saldo < pontos:
            return _erro("PONTOS_INSUFICIENTES",
                         f"Saldo insuficiente. Disponivel: {saldo} pontos.", 409,
                         [{"field": "pontos", "issue": f"saldo={saldo}"}])
        f.pontos_resgatados += pontos
        desconto = round(pontos * 0.10, 2)
        db.commit()
        return jsonify({
            "pontos_resgatados": pontos,
            "desconto_aplicado": desconto,
            "saldo_restante": f.pontos_acumulados - f.pontos_resgatados,
        }), 200
    finally:
        db.close()
