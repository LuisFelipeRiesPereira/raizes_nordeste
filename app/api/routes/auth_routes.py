from datetime import datetime
from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session

from app.infrastructure.database.base import SessionLocal
from app.application.services import auth_service
from app.domain.enums.enums import PerfilUsuario
from app.api.middleware.auth_middleware import requer_autenticacao

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _erro(codigo, mensagem, status, detalhes=None):
    # padrao de erro igual em todos os endpoints
    return jsonify({
        "error": codigo, "message": mensagem,
        "details": detalhes or [],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "path": request.path,
    }), status


# -----------
# registro
# entra nome email senha e consentimento lgpd
# sai usuario criado com 201
# -----------

@auth_bp.post("/register")
def registrar():
    dados = request.get_json(silent=True) or {}
    erros = [{"field": c, "issue": "obrigatorio"}
             for c in ["nome", "email", "senha"] if not dados.get(c)]
    if not dados.get("consentimento_lgpd"):
        erros.append({"field": "consentimento_lgpd", "issue": "consentimento lgpd obrigatorio"})
    if erros:
        return _erro("DADOS_INVALIDOS", "Campos obrigatorios ausentes.", 422, erros)

    perfil_str = dados.get("perfil", "CLIENTE").upper()
    try:
        perfil = PerfilUsuario(perfil_str)
    except ValueError:
        return _erro("PERFIL_INVALIDO", f"Perfil {perfil_str} nao reconhecido.", 422)

    db: Session = SessionLocal()
    try:
        usuario = auth_service.registrar_usuario(
            db=db, nome=dados["nome"], email=dados["email"],
            senha=dados["senha"], perfil=perfil,
            consentimento=bool(dados.get("consentimento_lgpd")),
        )
        return jsonify({
            "id": usuario.id, "nome": usuario.nome,
            "email": usuario.email, "perfil": usuario.perfil.value,
            "criado_em": usuario.criado_em.isoformat() + "Z",
        }), 201
    except ValueError as e:
        if "EMAIL_JA_CADASTRADO" in str(e):
            return _erro("EMAIL_JA_CADASTRADO", "Este email ja esta em uso.", 409)
        return _erro("ERRO_CADASTRO", str(e), 400)
    finally:
        db.close()


# -----------
# login
# entra email e senha
# sai token jwt pra usar nos outros endpoints
# -----------

@auth_bp.post("/login")
def login():
    dados = request.get_json(silent=True) or {}
    if not dados.get("email") or not dados.get("senha"):
        return _erro("DADOS_INVALIDOS", "Email e senha sao obrigatorios.", 422)

    db: Session = SessionLocal()
    try:
        usuario = auth_service.autenticar_usuario(db, dados["email"], dados["senha"])
        token = auth_service.criar_token({"sub": usuario.id, "perfil": usuario.perfil.value})
        return jsonify({
            "accessToken": token, "tokenType": "Bearer",
            "expiresIn": auth_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "usuario": {"id": usuario.id, "nome": usuario.nome, "perfil": usuario.perfil.value}
        }), 200
    except ValueError:
        return _erro("CREDENCIAIS_INVALIDAS", "Email ou senha invalidos.", 401)
    finally:
        db.close()


@auth_bp.get("/me")
@requer_autenticacao()
def perfil_atual():
    # retorna os dados do usuario logado sem expor o hash da senha
    u = g.usuario_atual
    return jsonify({
        "id": u.id, "nome": u.nome,
        "email": u.email, "perfil": u.perfil.value,
        "criado_em": u.criado_em.isoformat() + "Z",
    }), 200
