# promocoes e campanhas — raizes do nordeste

documento que descreve as regras de promocoes e campanhas conforme
estudo de caso da rede raizes do nordeste.

esse arquivo atende o RF08 do projeto que pede no minimo a documentacao
das regras conceituais de como aplicar promocoes mesmo que nao tenham
sido implementadas no MVP.

-----------
1. visao geral
-----------

a raizes do nordeste oferece 3 tipos de promocoes pra fidelizar clientes
e movimentar canais especificos da rede. todas elas tem regras claras de
elegibilidade e podem ser combinadas (ou nao) dependendo da campanha
ativa no momento.

-----------
2. tipos de promocao
-----------

### 2.1 — desconto por canal

incentivo para uso dos canais digitais. exemplo:

- desconto de 20% para pedidos feitos via APP em unidades selecionadas
- desconto de 10% para pedidos via TOTEM em horarios fora do pico
- desconto de 5% para pedidos via WEB com retirada PICKUP

regra de aplicacao:

| campo | valor |
|---|---|
| ativa em | canal_pedido especifico |
| ativa para | lista de unidade_id elegiveis |
| valor minimo do pedido | configuravel (ex R$30) |
| valor maximo de desconto | configuravel (ex R$50) |
| acumula com fidelidade | sim |

### 2.2 — promocao por categoria

incentivo para produtos especificos ou linhas de produto. exemplo:

- combo familia com 15% off nas tercas
- 2 tapiocas pelo preco de 1 nos sabados
- cafe da manha completo com 10% off ate 10h

regra de aplicacao:

| campo | valor |
|---|---|
| ativa para | categoria do produto |
| dias da semana | configuravel |
| horario | configuravel |
| acumula com desconto por canal | nao |

### 2.3 — campanhas sazonais

campanhas tematicas em datas especiais. exemplo:

- festa junina: 20% em todos os pratos tipicos durante junho
- semana do nordestino: combo especial com 25% off
- aniversario da rede: desconto progressivo por tempo de cliente

regra de aplicacao:

| campo | valor |
|---|---|
| periodo | data_inicio e data_fim |
| produtos elegiveis | tag especial (ex categoria=Pratos Tipicos) |
| acumula com fidelidade | sim |

-----------
3. como seria implementado
-----------

caso o RF08 fosse promovido para implementacao no proximo sprint a
estrutura seria a seguinte:

### 3.1 — nova tabela: promocoes

```sql
CREATE TABLE promocoes (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT,
    tipo VARCHAR(30) NOT NULL,  -- CANAL, CATEGORIA, SAZONAL
    desconto_percentual NUMERIC(5,2),  -- ex 20.00 para 20%
    valor_minimo NUMERIC(10,2),
    desconto_maximo NUMERIC(10,2),
    canal_pedido VARCHAR(20),  -- se aplicavel
    categoria VARCHAR(80),  -- se aplicavel
    unidades_elegiveis INTEGER[],  -- array de unidade_id
    data_inicio TIMESTAMP NOT NULL,
    data_fim TIMESTAMP NOT NULL,
    acumula_com_fidelidade BOOLEAN DEFAULT TRUE,
    ativa BOOLEAN DEFAULT TRUE,
    criada_em TIMESTAMP DEFAULT NOW()
);
```

### 3.2 — novos endpoints

| metodo | rota | perfil | descricao |
|---|---|---|---|
| GET | /promocoes | publico | lista promocoes ativas |
| GET | /promocoes/aplicaveis | publico | dada uma combinacao canal+unidade+itens retorna promocoes elegiveis |
| POST | /promocoes | ADMIN | cria nova promocao |
| PATCH | /promocoes/{id} | ADMIN | edita promocao |
| DELETE | /promocoes/{id} | ADMIN | desativa promocao |

### 3.3 — integracao com criacao de pedido

o endpoint POST /pedidos passaria a:

1. validar itens e estoque (como hoje)
2. calcular valor_total bruto (como hoje)
3. **buscar promocoes aplicaveis** considerando canal_pedido + unidade_id + itens
4. **aplicar a melhor promocao automaticamente** (ou a indicada pelo cliente)
5. registrar valor_total_bruto e valor_total_liquido no pedido
6. registrar promocao_id no item_pedido para rastreabilidade

### 3.4 — exemplo de aplicacao

cenario: cliente faz pedido via APP em uma unidade que tem desconto APP
ativo de 20% e o pedido tem R$80 em itens.

```json
{
  "canal_pedido": "APP",
  "unidade_id": 1,
  "itens": [{"produto_id": 1, "quantidade": 2}]
}
```

resposta:

```json
{
  "id": 10,
  "valor_total_bruto": 80.00,
  "promocao_aplicada": {
    "id": 5,
    "nome": "20% off no APP",
    "desconto_percentual": 20
  },
  "valor_desconto": 16.00,
  "valor_total_liquido": 64.00,
  "status": "AGUARDANDO_PAGAMENTO"
}
```

-----------
4. regras de negocio importantes
-----------

- promocao so e aplicada se o cliente atender TODOS os criterios
- na duvida o sistema aplica a promocao de MAIOR desconto pro cliente
- promocoes nao se acumulam exceto quando explicitamente permitido
- pontos de fidelidade sao calculados sobre o valor_total_liquido
- promocoes sao registradas no log de auditoria com a categoria PROMOCAO_APLICADA

-----------
5. justificativa de nao implementacao no MVP
-----------

as promocoes foram tratadas como RF08 de prioridade baixa porque:

1. nao integram o fluxo critico avaliado pelo roteiro
2. exigiriam uma nova tabela e um motor de regras de promocao
3. o tempo do MVP foi priorizado para fluxos obrigatorios
4. uma vez que a regra esta documentada aqui a implementacao futura
   segue como evolucao natural sem retrabalho de modelagem

a arquitetura atual permite adicionar essa funcionalidade sem alterar o
restante do sistema apenas inserindo um novo service (promocao_service)
e um blueprint dedicado.
