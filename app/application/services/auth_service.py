import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
import jwt as pyjwt
import bcrypt
from sqlalchemy.orm import Session

from app.domain.models.models import Usuario, Fidelidade, LogAuditoria
from app.domain.enums.enums import PerfilUsuario

SECRET_KEY = os.getenv("SECRET_KEY", "raizes-nordeste-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# -----------
# hash e verificacao de senha
# usa bcrypt direto sem wrapper
# mesma SECRET_KEY tem que estar no env
# -----------

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, hash_: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), hash_.encode("utf-8"))


def criar_token(data: dict, expira_em: Optional[int] = None) -> str:
    payload = data.copy()
    expires = datetime.utcnow() + timedelta(minutes=expira_em or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expires, "jti": str(uuid.uuid4())})
    token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decodificar_token(token: str) -> Optional[dict]:
    try:
        return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        print(f"[debug] erro ao decodificar token: {e}")
        return None


# -----------
# cadastro entra nome email e senha
# sai usuario salvo no banco com hash da senha
# cria fidelidade automatico pra cliente novo
# -----------

def registrar_usuario(db: Session, nome: str, email: str, senha: str,
                      perfil: PerfilUsuario = PerfilUsuario.CLIENTE,
                      consentimento: bool = True) -> Usuario:
    existente = db.query(Usuario).filter(Usuario.email == email).first()
    if existente:
        raise ValueError("EMAIL_JA_CADASTRADO")

    usuario = Usuario(
        nome=nome, email=email,
        senha_hash=hash_senha(senha),
        perfil=perfil,
        consentimento_lgpd=consentimento,
    )
    db.add(usuario)
    db.flush()

    if perfil == PerfilUsuario.CLIENTE:
        db.add(Fidelidade(cliente_id=usuario.id, pontos_acumulados=0, pontos_resgatados=0))

    _log(db, usuario.id, "CADASTRO_USUARIO", "usuarios", usuario.id)
    db.commit()
    db.refresh(usuario)
    return usuario


# -----------
# login entra email e senha
# sai o usuario ou lanca erro
# loga tentativa falha tambem
# -----------

def autenticar_usuario(db: Session, email: str, senha: str) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.ativo == True).first()
    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        _log(db, None, "LOGIN_FALHOU", "auth", detalhes=f"email={email}")
        db.commit()
        raise ValueError("CREDENCIAIS_INVALIDAS")
    _log(db, usuario.id, "LOGIN_SUCESSO", "auth", usuario.id)
    db.commit()
    return usuario


def _log(db: Session, usuario_id, acao: str, recurso: str = None,
         recurso_id: int = None, detalhes: str = None):
    db.add(LogAuditoria(
        usuario_id=usuario_id, acao=acao,
        recurso=recurso, recurso_id=recurso_id, detalhes=detalhes,
    ))
