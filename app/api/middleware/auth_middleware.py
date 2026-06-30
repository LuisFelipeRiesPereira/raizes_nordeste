from functools import wraps
from typing import List, Optional
from flask import request, g, jsonify
from sqlalchemy.orm import Session

from app.application.services.auth_service import decodificar_token
from app.domain.models.models import Usuario
from app.domain.enums.enums import PerfilUsuario
from app.infrastructure.database.base import SessionLocal

# -----------
# decorator que protege qualquer rota
# uso simples: @requer_autenticacao()
# com perfil: @requer_autenticacao([PerfilUsuario.ADMIN])
# -----------

def _obter_usuario_do_token() -> Optional[Usuario]:
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif auth_header.strip():
        token = auth_header.strip()

    if not token:
        return None

    payload = decodificar_token(token)
    if not payload:
        return None

    db: Session = SessionLocal()
    try:
        return db.query(Usuario).filter(
            Usuario.id == payload.get("sub"),
            Usuario.ativo == True
        ).first()
    finally:
        db.close()


def requer_autenticacao(perfis: List[PerfilUsuario] = None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            usuario = _obter_usuario_do_token()
            if not usuario:
                return jsonify({
                    "error": "NAO_AUTENTICADO",
                    "message": "Token invalido ou ausente.",
                    "details": [], "path": request.path
                }), 401

            # -----------
            # verifica se o perfil tem permissao pra acessar a rota
            # -----------
            if perfis and usuario.perfil not in perfis:
                return jsonify({
                    "error": "SEM_PERMISSAO",
                    "message": "Seu perfil nao possui acesso a este recurso.",
                    "details": [], "path": request.path
                }), 403
            g.usuario_atual = usuario
            return f(*args, **kwargs)
        return wrapper
    return decorator
