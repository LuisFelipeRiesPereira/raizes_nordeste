"""
seed.py - popula o banco com dados iniciais pra testar
executar: python seed.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.infrastructure.database.base import SessionLocal, Base, engine
from app.domain.models.models import Usuario, Unidade, Produto, Estoque, Fidelidade
from app.domain.enums.enums import PerfilUsuario
from app.application.services.auth_service import hash_senha

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # -----------
    # usuarios de teste um de cada perfil
    # -----------
    admin = Usuario(nome="Admin Raizes", email="admin@raizes.com",
                    senha_hash=hash_senha("Admin@2026"), perfil=PerfilUsuario.ADMIN,
                    consentimento_lgpd=True)
    gerente = Usuario(nome="Gerente Fortaleza", email="gerente@raizes.com",
                      senha_hash=hash_senha("Gerente@2026"), perfil=PerfilUsuario.GERENTE,
                      consentimento_lgpd=True)
    cozinha = Usuario(nome="Equipe Cozinha", email="cozinha@raizes.com",
                      senha_hash=hash_senha("Cozinha@2026"), perfil=PerfilUsuario.COZINHA,
                      consentimento_lgpd=True)
    cliente1 = Usuario(nome="Maria Nordeste", email="maria@cliente.com",
                       senha_hash=hash_senha("Cliente@2026"), perfil=PerfilUsuario.CLIENTE,
                       consentimento_lgpd=True)
    cliente2 = Usuario(nome="Joao Sertao", email="joao@cliente.com",
                       senha_hash=hash_senha("Joao@2026"), perfil=PerfilUsuario.CLIENTE,
                       consentimento_lgpd=True)
    db.add_all([admin, gerente, cozinha, cliente1, cliente2])
    db.flush()

    db.add(Fidelidade(cliente_id=cliente1.id, pontos_acumulados=0))
    db.add(Fidelidade(cliente_id=cliente2.id, pontos_acumulados=0))

    # -----------
    # 3 unidades pelo nordeste
    # -----------
    u1 = Unidade(nome="Raizes Fortaleza Centro", cidade="Fortaleza", estado="CE",
                 endereco="Rua Dragao do Mar 100")
    u2 = Unidade(nome="Raizes Recife Boa Viagem", cidade="Recife", estado="PE",
                 endereco="Av. Boa Viagem 500")
    u3 = Unidade(nome="Raizes Salvador Pelourinho", cidade="Salvador", estado="BA",
                 endereco="Largo do Pelourinho 22")
    db.add_all([u1, u2, u3])
    db.flush()

    # -----------
    # produtos do cardapio
    # p2 custa 49.90 entao 5 unidades dao 249.50 que e maior que 200
    # isso serve pra testar o pagamento recusado no postman
    # -----------
    p1 = Produto(nome="Baiao de Dois",
                 descricao="Arroz com feijao de corda queijo e carne seca",
                 preco=29.90, categoria="Pratos Principais")
    p2 = Produto(nome="Carne de Sol na Pedra",
                 descricao="Carne de sol grelhada com manteiga de garrafa",
                 preco=49.90, categoria="Pratos Principais")
    p3 = Produto(nome="Tapioca Nordestina",
                 descricao="Tapioca recheada com queijo coalho e coco",
                 preco=15.90, categoria="Lanches")
    p4 = Produto(nome="Suco de Caja",
                 descricao="Suco natural de caja gelado 500ml",
                 preco=9.90, categoria="Bebidas")
    p5 = Produto(nome="Buchada de Bode",
                 descricao="Prato tipico nordestino com miudos temperados",
                 preco=39.90, categoria="Pratos Tipicos")
    p6 = Produto(nome="Combo Familia",
                 descricao="2 Baiao de Dois e 2 Sucos",
                 preco=79.80, categoria="Combos")
    db.add_all([p1, p2, p3, p4, p5, p6])
    db.flush()

    # cada unidade tem estoque proprio
    for produto, qtd in [(p1, 50), (p2, 30), (p3, 100), (p4, 80), (p5, 20), (p6, 15)]:
        db.add(Estoque(produto_id=produto.id, unidade_id=u1.id, quantidade=qtd))
        db.add(Estoque(produto_id=produto.id, unidade_id=u2.id, quantidade=max(qtd - 10, 5)))
        db.add(Estoque(produto_id=produto.id, unidade_id=u3.id, quantidade=max(qtd - 15, 5)))

    db.commit()
    print("seed executado com sucesso")
    print("usuarios: admin@raizes.com / gerente@raizes.com / cozinha@raizes.com")
    print("clientes: maria@cliente.com / joao@cliente.com")
    print("senhas: Admin@2026 / Gerente@2026 / Cozinha@2026 / Cliente@2026 / Joao@2026")
except Exception as e:
    db.rollback()
    print(f"erro no seed: {e}")
    raise
finally:
    db.close()
