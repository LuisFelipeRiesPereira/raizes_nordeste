import enum

# -----------
# todos os enums ficam aqui
# qualquer valor novo de canal status ou perfil entra nessa lista
# -----------

class PerfilUsuario(str, enum.Enum):
    ADMIN = "ADMIN"
    GERENTE = "GERENTE"
    CLIENTE = "CLIENTE"
    COZINHA = "COZINHA"
    ATENDENTE = "ATENDENTE"


# -----------
# de onde veio o pedido
# obrigatorio em todo pedido criado
# -----------

class CanalPedido(str, enum.Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedido(str, enum.Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    PAGO = "PAGO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class StatusPagamento(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"


class TipoMovimentacao(str, enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
