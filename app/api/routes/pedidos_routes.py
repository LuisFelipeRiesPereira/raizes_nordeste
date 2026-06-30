from datetime import datetime
from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session

from app.infrastructure.database.base import SessionLocal
from app.application.services import pedido_service
from app.domain.models.models import Pedido
from app.domain.enums.enums import CanalPedido, StatusPedido, PerfilUsuario
from app.api.middleware.auth_middleware import requer_autenticacao

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")

# quem pode mudar status de pedido
_GESTAO = [PerfilUsuario.ADMIN, PerfilUsuario.GERENTE,
           PerfilUsuario.COZINHA, PerfilUsuario.ATENDENTE]


def _erro(codigo, mensagem, status, detalhes=None):
    return jsonify({
        "error": codigo, "message": mensagem,
        "details": detalhes or [],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "path": request.path,
    }), status


def _serial(p: Pedido) -> dict:
    # monta o json do pedido sem dados sensiveis
    return {
        "id": p.id, "cliente_id": p.cliente_id,
        "unidade_id": p.unidade_id,
        "canal_pedido": p.canal_pedido.value,
        "status": p.status.value,
        "valor_total": p.valor_total,
        "observacao": p.observacao,
        "criado_em": p.criado_em.isoformat() + "Z",
        "atualizado_em": p.atualizado_em.isoformat() + "Z" if p.atualizado_em else None,
        "itens": [{"produto_id": i.produto_id, "quantidade": i.quantidade,
                   "preco_unitario": i.preco_unitario,
                   "subtotal": round(i.quantidade * i.preco_unitario, 2)}
                  for i in p.itens],
    }


# -----------
# criar pedido
# canal_pedido e obrigatorio sem ele retorna 422
# valida estoque antes de salvar qualquer coisa
# -----------

@pedidos_bp.post("")
@requer_autenticacao([PerfilUsuario.CLIENTE, PerfilUsuario.ADMIN, PerfilUsuario.ATENDENTE])
def criar_pedido():
    dados = request.get_json(silent=True) or {}
    erros = [{"field": c, "issue": "obrigatorio"}
             for c in ["unidade_id", "canal_pedido", "itens"] if c not in dados or dados[c] is None]
    if erros:
        return _erro("DADOS_INVALIDOS", "Campos obrigatorios ausentes.", 422, erros)

    try:
        canal = CanalPedido(str(dados["canal_pedido"]).upper())
    except ValueError:
        return _erro("CANAL_INVALIDO",
                     f"canalPedido invalido. Valores: {[c.value for c in CanalPedido]}", 422,
                     [{"field": "canal_pedido", "issue": "valor invalido"}])

    itens = dados.get("itens", [])
    if not isinstance(itens, list) or len(itens) == 0:
        return _erro("ITENS_INVALIDOS", "O pedido deve ter ao menos um item.", 422,
                     [{"field": "itens", "issue": "lista vazia"}])

    db: Session = SessionLocal()
    try:
        pedido = pedido_service.criar_pedido(
            db=db, cliente_id=g.usuario_atual.id,
            unidade_id=int(dados["unidade_id"]),
            canal_pedido=canal, itens=itens,
            observacao=dados.get("observacao"),
        )
        return jsonify(_serial(pedido)), 201
    except LookupError as e:
        msg = str(e)
        if "PRODUTO" in msg:
            pid = msg.split(":")[-1]
            return _erro("PRODUTO_NAO_ENCONTRADO", f"Produto id={pid} nao encontrado.", 404)
        return _erro("RECURSO_NAO_ENCONTRADO", msg, 404)
    except OverflowError as e:
        partes = str(e).split(":")
        return _erro("ESTOQUE_INSUFICIENTE", "Estoque insuficiente.", 409,
                     [{"field": f"produto_id={partes[1] if len(partes)>1 else '?'}",
                       "issue": f"Disponivel: {partes[2] if len(partes)>2 else '0'}"}])
    except ValueError as e:
        return _erro("ERRO_PEDIDO", str(e), 400)
    finally:
        db.close()


# -----------
# listagem com filtros
# cliente so ve os proprios pedidos
# admin ve todos
# -----------

@pedidos_bp.get("")
@requer_autenticacao()
def listar_pedidos():
    db: Session = SessionLocal()
    usuario = g.usuario_atual
    try:
        query = db.query(Pedido)
        if usuario.perfil == PerfilUsuario.CLIENTE:
            query = query.filter(Pedido.cliente_id == usuario.id)

        canal_str = request.args.get("canal_pedido", "").upper()
        if canal_str:
            try:
                query = query.filter(Pedido.canal_pedido == CanalPedido(canal_str))
            except ValueError:
                return _erro("CANAL_INVALIDO", f"canalPedido {canal_str} invalido.", 422)

        status_str = request.args.get("status", "").upper()
        if status_str:
            try:
                query = query.filter(Pedido.status == StatusPedido(status_str))
            except ValueError:
                return _erro("STATUS_INVALIDO", f"status {status_str} invalido.", 422)

        page = max(int(request.args.get("page", 1)), 1)
        limit = min(int(request.args.get("limit", 10)), 100)
        total = query.count()
        pedidos = query.order_by(Pedido.criado_em.desc()).offset((page-1)*limit).limit(limit).all()
        return jsonify({"data": [_serial(p) for p in pedidos],
                        "pagina": page, "limite": limit, "total": total}), 200
    finally:
        db.close()


@pedidos_bp.get("/<int:pedido_id>")
@requer_autenticacao()
def obter_pedido(pedido_id):
    db: Session = SessionLocal()
    usuario = g.usuario_atual
    try:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            return _erro("PEDIDO_NAO_ENCONTRADO", f"Pedido {pedido_id} nao encontrado.", 404)
        if usuario.perfil == PerfilUsuario.CLIENTE and pedido.cliente_id != usuario.id:
            return _erro("SEM_PERMISSAO", "Acesso negado.", 403)
        return jsonify(_serial(pedido)), 200
    finally:
        db.close()


# -----------
# atualizar status
# so perfis de gestao podem mudar
# transicoes invalidas retornam 409
# -----------

@pedidos_bp.patch("/<int:pedido_id>/status")
@requer_autenticacao(_GESTAO)
def atualizar_status(pedido_id):
    dados = request.get_json(silent=True) or {}
    if not dados.get("status"):
        return _erro("DADOS_INVALIDOS", "Campo status obrigatorio.", 422,
                     [{"field": "status", "issue": "obrigatorio"}])
    try:
        novo_status = StatusPedido(dados["status"].upper())
    except ValueError:
        return _erro("STATUS_INVALIDO", f"Status {dados['status']} invalido.", 422)

    db: Session = SessionLocal()
    try:
        pedido = pedido_service.atualizar_status_pedido(
            db=db, pedido_id=pedido_id,
            novo_status=novo_status, usuario_id=g.usuario_atual.id
        )
        return jsonify(_serial(pedido)), 200
    except LookupError as e:
        return _erro("PEDIDO_NAO_ENCONTRADO", str(e), 404)
    except ValueError as e:
        return _erro("TRANSICAO_INVALIDA", str(e), 409)
    finally:
        db.close()


# -----------
# cancelar pedido
# rota dedicada porque cancelamento eh operacao sensivel
# exige motivo no body devolve o estoque e gera log de categoria CANCELAMENTO
# cliente pode cancelar so o proprio pedido gestao pode cancelar qualquer um
# -----------

@pedidos_bp.post("/<int:pedido_id>/cancelar")
@requer_autenticacao()
def cancelar_pedido(pedido_id):
    dados = request.get_json(silent=True) or {}
    motivo = dados.get("motivo", "").strip()

    if not motivo:
        return _erro("DADOS_INVALIDOS", "Motivo do cancelamento e obrigatorio.", 422,
                     [{"field": "motivo", "issue": "obrigatorio (minimo 5 caracteres)"}])

    db: Session = SessionLocal()
    usuario = g.usuario_atual
    try:
        # cliente so pode cancelar o proprio pedido
        pedido_check = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido_check:
            return _erro("PEDIDO_NAO_ENCONTRADO", f"Pedido {pedido_id} nao encontrado.", 404)
        if usuario.perfil == PerfilUsuario.CLIENTE and pedido_check.cliente_id != usuario.id:
            return _erro("SEM_PERMISSAO", "Voce so pode cancelar seus proprios pedidos.", 403)

        pedido = pedido_service.cancelar_pedido(
            db=db, pedido_id=pedido_id,
            motivo=motivo, usuario_id=usuario.id
        )
        return jsonify({
            "mensagem": "Pedido cancelado com sucesso.",
            "pedido": _serial(pedido),
            "motivo": motivo,
            "estoque_devolvido": True,
        }), 200
    except LookupError as e:
        return _erro("PEDIDO_NAO_ENCONTRADO", str(e), 404)
    except ValueError as e:
        msg = str(e)
        if "CANCELAMENTO_NAO_PERMITIDO" in msg:
            return _erro("CANCELAMENTO_NAO_PERMITIDO",
                         f"Pedido nao pode ser cancelado no status atual: {msg.split(':')[1]}",
                         409)
        return _erro("DADOS_INVALIDOS", msg, 422)
    finally:
        db.close()
