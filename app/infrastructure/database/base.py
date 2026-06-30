import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# -----------
# pega a url do banco do .env
# se nao achar usa o padrao local mesmo
# -----------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raizes_user:raizes_pass@localhost:5432/raizes_nordeste"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    # abre a sessao usa e fecha
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
