# Api raízes do nordeste

## Projeto multidisciplinar UNINTER 2026 — Trilha back-end

Api rest completa pra rede de lanchonetes nordestinas com pedidos multicanal pagamento mock fidelidade e controle de estoque por unidade.

-----------
1. requisitos
-----------

o que voce precisa ter instalado pra rodar o projeto:

| componente | versao | observacao |
|---|---|---|
| python | 3.10 ou superior | testado ate 3.14 |
| postgresql | 15 ou superior | banco relacional |
| pgadmin | qualquer versao | pra criar usuario e banco |
| git | qualquer versao | pra clonar o repositorio |

dependencias python (instaladas via pip):

| pacote | versao | pra que serve |
|---|---|---|
| flask | 3.0.3 | framework web |
| sqlalchemy | 2.0.31 | orm pro banco |
| alembic | 1.13.2 | migrations |
| pyjwt | 2.8.0 | geracao e validacao de token |
| bcrypt | 4.2.0 | hash da senha |
| psycopg2-binary | 2.9.9 | driver postgres |
| pyyaml | 6.0.2 | leitura do swagger.yaml |
| python-dotenv | 1.0.1 | leitura do .env |

todas elas ja estao no requirements.txt e sao instaladas no passo 3.

-----------
2. configurar variaveis de ambiente
-----------

primeiro copia o arquivo modelo:

```bash
cp .env.example .env
```

Abre o arquivo .env e confere os valores. Está explicado no próprio arquivo cada variável

-----------
3. instalar dependencias
-----------

Cria o ambiente virtual e instala tudo:

```bash
python -m venv venv
pip install -r requirements.txt
```

-----------
4. criar o banco e popular com seed
-----------

abre o pgadmin e conecta no servidor com hostname "localhost" como usuario **postgres** (o superusuario).

**4.1 — cria o usuario e o banco**

Vai no caminho Database -> **postgres** e clica com botao direito em **postgres** → Query Tool e roda:

```sql
CREATE USER raizes_user WITH PASSWORD 'raizes_pass';
```
E depois rode
```sql
CREATE DATABASE raizes_nordeste OWNER raizes_user;
```
**4.2 — da as permissoes no schema public**

Com o banco criado, clica com botao direito em raizes_nordeste → Query Tool (importante: tem que entrar dentro do banco raizes_nordeste agora) e roda:

```sql
GRANT ALL PRIVILEGES ON DATABASE raizes_nordeste TO raizes_user;
GRANT ALL ON SCHEMA public TO raizes_user;
ALTER SCHEMA public OWNER TO raizes_user;
```

**4.3 — roda o seed**

volta no terminal com o venv ativado e roda:

```bash
python seed.py
```

isso cria automaticamente as 10 tabelas (via SQLAlchemy create_all que funciona como migration) e popula com:
- 5 usuarios de teste (1 pra cada tipo)
- 3 unidades da rede
- 6 produtos no cardapio
- estoque inicial em todas as unidades

-----------
5. iniciar a api
-----------

```bash
python run.py
```

a api fica disponivel em:

- http://localhost:5000/health (verifica se ta de pe)
- http://localhost:5000 (rota base)

pra parar aperta Ctrl+C no terminal.

-----------
6. documentacao da api (swagger)
-----------

com a api rodando acessa no navegador:

```
http://localhost:5000/docs/
```

o swagger ui 5 abre listando todos os 19 endpoints. da pra:
- ver os esquemas de request e response
- testar qualquer endpoint direto na interface (clica em "Try it out")
- copiar exemplos prontos de payload
- ver os codigos de erro padronizados

a especificacao OpenAPI bruta fica em docs/swagger.yaml caso queira importar em outra ferramenta.

-----------
7. Como rodar os testes
-----------

Os testes ficam na coleção postman do projeto. Passo a passo:

**7.1 — pre-requisitos**

- api rodando (passo 5)
- seed executado (passo 4.3)
- postman instalado (https://www.postman.com/downloads/)

**7.2 — importar a coleção**

no postman clica em **Import** e seleciona o arquivo:

```
docs/raizes_nordeste_collection.json
```

a colecao aparece na barra lateral organizada em 9 pastas:
- Auth (login e cadastro)
- Produtos (cardapio)
- Pedidos (criacao e listagem)
- Pagamento (mock aprovado e recusado)
- Status (transicoes do pedido)
- Erros (cenarios negativos)
- Cardapio por Unidade (filtro por loja)
- Cancelamento (operacao sensivel)
- Fidelidade (pontos)

**7.3 — executar na ordem**

abre a colecao e roda os testes em ordem de T01 ate T18. cada teste tem script pm.test que valida o status code e o conteudo da resposta.

ordem dos testes:
- T01 a T03: login com cada perfil (token fica salvo)
- T04 e T05: erros de autenticacao (negativos)
- T06: listar produtos
- T07 e T08: criar pedido APP e TOTEM
- T09 e T10: validacoes (negativos)
- T11 e T12: pagamento aprovado e recusado
- T13: filtrar por canal
- T14: mudar status
- T15: tentar mudar status sem permissao (negativo)
- T16: consultar fidelidade
- T17: cardapio filtrado por unidade (so produtos com estoque)
- T18: cancelar pedido com motivo (devolve estoque)
- T19: pedido com estoque insuficiente (negativo - 409 ESTOQUE_INSUFICIENTE)

**7.4 — rodar tudo de uma vez**

clica com botao direito na colecao → **Run Collection** → **Run raizes nordeste**.

todos os 19 testes rodam em sequencia e mostram quantos passaram. o esperado e 19 verdes.

-----------
usuarios criados pelo seed
-----------

| email | senha | perfil |
|---|---|---|
| admin@raizes.com | Admin@2026 | ADMIN |
| gerente@raizes.com | Gerente@2026 | GERENTE |
| cozinha@raizes.com | Cozinha@2026 | COZINHA |
| maria@cliente.com | Cliente@2026 | CLIENTE |
| joao@cliente.com | Joao@2026 | CLIENTE |

-----------
fluxo principal da api
-----------

```
POST /auth/login              -> pega o token jwt
POST /pedidos                 -> cria pedido com canal_pedido
POST /pagamentos/mock         -> aprova ou recusa pelo valor
PATCH /pedidos/{id}/status    -> muda o status
GET  /fidelidade/{id}         -> consulta pontos creditados
```

**regra do pagamento mock:**
- valor ate R$200 = APROVADO
- valor acima de R$200 = RECUSADO

deterministico de proposito pra testar os dois cenarios sem ambiguidade.

-----------
estrutura do projeto
-----------

```
raizes_nordeste/
├── app/
│   ├── domain/          enums e modelos sqlalchemy
│   ├── application/     services (auth pedido estoque)
│   ├── infrastructure/  conexao com o banco
│   └── api/             rotas e middleware
├── migrations/          migration alembic
├── docs/                swagger e colecao postman
├── seed.py              dados de teste
├── run.py               entrypoint da api
├── requirements.txt     dependencias
├── .env.example         modelo de variaveis de ambiente
└── README.md            este arquivo
```
Projeto acadêmico — UNINTER, 2026.