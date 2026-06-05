# Microsserviço de Logística — Portal B2B

Microsserviço responsável pelo ciclo completo de cotação, contratação e rastreio de frete no Portal B2B. Desenvolvido pela Equipe 8 no contexto da disciplina CMP1896 — Sistemas Distribuídos.

---

## Visao Geral

O `logistica-service` opera como um microsserviço assíncrono dentro da arquitetura do Portal B2B. Seu fluxo principal segue o modelo descentralizado (v2):

1. Recebe solicitações de cotação de frete via API REST ou por consumo de eventos Kafka publicados pela equipe de Demandas.
2. Gera três cotações simuladas com base no tipo de veículo e publica o tópico `cotacoes_frete_disponiveis`.
3. Aguarda a decisão explícita do microsserviço de Demandas, que chega pelo tópico `frete_contratado`.
4. Grava o `frete_selecionado` no banco de dados e inicia a simulação de rastreio, transitando o status de `SELECIONADO` para `EM_TRANSITO` e, por fim, para `ENTREGUE`.

O frontend serve como painel de observabilidade e interface de demonstracao do fluxo, exposto em `/logistica/` via Nginx.

---

## Stack Tecnologica

### Backend

| Componente | Tecnologia / Versao |
|---|---|
| Linguagem | Python 3.11 (imagem Docker `python:3.11-slim`) |
| Framework web | FastAPI 0.115.6 |
| Servidor ASGI | Uvicorn 0.34.0 com uvloop 0.22.1 |
| ORM | SQLAlchemy 2.0.36 (modo assincrono) |
| Driver de banco | asyncpg 0.30.0 |
| Banco de dados | PostgreSQL (instancia centralizada da disciplina) |
| Mensageria | Apache Kafka via aiokafka 0.12.0 |
| Validacao de dados | Pydantic 2.10.3 |
| Configuracao | python-dotenv 1.0.1 |
| WebSockets | websockets 16.0 |

### Frontend

| Componente | Tecnologia / Versao |
|---|---|
| Framework UI | React 19.2.6 |
| Bundler | Vite 8.0.12 com plugin `@vitejs/plugin-react` 6.0.1 |
| Estilizacao | Tailwind CSS 3.4.19 com PostCSS e Autoprefixer |
| Servidor de producao | Nginx (imagem Docker `nginx:alpine`) |
| Build target | Artefato estatico gerado em `frontend/dist/` |

---

## Requisitos do Sistema

- Docker Engine 24 ou superior
- Docker Compose v2 (plugin integrado ao Docker CLI)
- Acesso de rede ao broker Kafka e ao PostgreSQL especificados no arquivo `.env`
- A rede Docker externa `portal-b2b-network` deve existir antes de subir os servicos

Para criar a rede caso ela ainda nao exista:

```bash
docker network create portal-b2b-network
```

---

## Variaveis de Ambiente

Copie o arquivo de exemplo e preencha os valores conforme o ambiente:

```bash
cp .env.example .env
```

| Variavel | Descricao | Exemplo |
|---|---|---|
| `SERVICE_NAME` | Identificador do servico nos logs e no Kafka | `logistica-service` |
| `PORT` | Porta interna do container backend | `5008` |
| `DATABASE_URL` | String de conexao PostgreSQL (formato `postgresql://user:senha@host:porta/banco`) | `postgresql://svc_portal_b2b:senha@host:5432/portal_b2b` |
| `DB_SCHEMA` | Schema do banco de dados utilizado | `portal_b2b` |
| `KAFKA_BOOTSTRAP_SERVERS` | Lista de brokers Kafka separados por virgula | `10.128.0.2:9092,10.128.0.3:9092` |
| `ROOT_PATH` | Prefixo de rota para o FastAPI (usado pelo gateway) | `/api/logistica` |
| `JWT_SECRET` | Segredo para validacao de tokens JWT emitidos pelo portal de autenticacao | — |
| `JWT_ISSUER` | Emissor esperado no claim `iss` do JWT | `portal-autenticacao` |
| `JWT_AUDIENCE` | Audiencia esperada no claim `aud` do JWT | `portal-b2b` |
| `JWT_EXPIRATION_MINUTES` | Duracao de validade do token em minutos | `240` |
| `JWT_CLOCK_SKEW_SECONDS` | Tolerancia de desvio de relogio para validacao do JWT | `60` |

> **Atencao:** O arquivo `.env` nunca deve ser commitado no repositorio. Ele ja esta listado no `.gitignore`.

---

## Gestao da Infraestrutura com Docker

### Construir as imagens e subir toda a infraestrutura

Execute o comando abaixo para construir as imagens do zero e iniciar todos os containers em modo detached:

```bash
docker compose up --build -d
```

Para verificar se os containers estao em execucao apos a inicializacao:

```bash
docker compose ps
```

### Derrubar a infraestrutura e limpar recursos residuais

Para parar e remover os containers, as redes proprias do Compose e os volumes anonimos criados:

```bash
docker compose down --volumes --remove-orphans
```

> A rede `portal-b2b-network` e declarada como `external: true` e nao e removida por este comando, o que e o comportamento esperado. Ela e compartilhada com outros microsservicos do portal.

Para remover tambem as imagens locais construidas pelo projeto (libera espaco em disco):

```bash
docker compose down --volumes --remove-orphans --rmi local
```

### Visualizar logs dos containers

Exibir os logs de todos os servicos em tempo real (modo streaming):

```bash
docker compose logs -f
```

Exibir os logs apenas do backend:

```bash
docker compose logs -f logistica-service
```

Exibir os logs apenas do frontend (Nginx):

```bash
docker compose logs -f logistica-front
```

Exibir as ultimas N linhas de um servico especifico:

```bash
docker compose logs --tail=100 logistica-service
```

---

## Estrutura do Repositorio

```
b2b_logistica/
├── app/                        # Codigo-fonte do backend (Python)
│   ├── __init__.py
│   ├── main.py                 # Entrypoint FastAPI com lifespan handler
│   ├── database.py             # Configuracao do SQLAlchemy async (asyncpg)
│   ├── models.py               # Modelos ORM (mapeamento, sem DDL)
│   ├── schemas.py              # Schemas Pydantic de entrada, saida e envelope Kafka
│   ├── routes.py               # Rotas REST da API
│   └── kafka_handler.py        # Producer e consumers Kafka (aiokafka)
├── frontend/                   # Codigo-fonte do frontend (React + Vite)
│   ├── src/
│   │   ├── main.jsx            # Entrypoint React
│   │   ├── App.jsx             # Componente raiz
│   │   ├── api.js              # Camada de acesso a API REST
│   │   ├── components/         # Componentes reutilizaveis
│   │   └── index.css           # Estilos globais com Tailwind
│   ├── nginx.conf              # Configuracao Nginx (proxy reverso + SPA fallback)
│   ├── Dockerfile              # Build multi-stage: Node 22 → nginx:alpine
│   ├── vite.config.js          # Configuracao do Vite (base path, proxy de dev)
│   ├── tailwind.config.js      # Configuracao do Tailwind CSS
│   └── package.json            # Dependencias Node
├── Dockerfile                  # Imagem do backend (python:3.11-slim + uvicorn)
├── docker-compose.yml          # Orquestracao dos servicos logistica-service e logistica-front
├── requirements.txt            # Dependencias Python
├── .env.example                # Modelo de variaveis de ambiente
└── .gitignore
```

---

## Topicos Kafka

| Topico | Direcao | Descricao |
|---|---|---|
| `solicitacao_frete_criada` | Publicado | Emitido ao criar uma nova solicitacao de frete |
| `cotacao_frete_enviada` | Consumido | Recebe cotacoes da equipe de Transportadoras (Equipe 9) |
| `cotacoes_frete_disponiveis` | Publicado | Envia as cotacoes geradas para o microsservico de Demandas |
| `frete_contratado` | Consumido | Recebe a decisao explícita de contratacao do microsservico de Demandas |
| `frete_selecionado` | Publicado | Confirma o frete selecionado apos a contratacao |
| `logistica_status_atualizado` | Publicado | Notifica transicoes de status do rastreio (`EM_TRANSITO`, `ENTREGUE`) |

Todas as mensagens seguem o envelope padrao do Portal B2B com os campos: `eventId`, `eventType`, `eventVersion`, `timestamp`, `source`, `correlationId` e `payload`.

---

## Endpoints da API

A documentacao interativa completa esta disponivel em:

- Swagger UI: `http://localhost:5008/docs`
- OpenAPI JSON: `http://localhost:5008/openapi.json`

Quando acessado via gateway, o prefixo `/api/logistica` e aplicado automaticamente conforme a variavel `ROOT_PATH`.

| Metodo | Rota | Descricao |
|---|---|---|
| `GET` | `/health` | Health check do servico |
| `POST` | `/solicitar-externo` | Simula recebimento de pedido de frete (mock de Vendas) |
| `POST` | `/demo-iniciar-cotacao` | Etapa 1 do fluxo demo: cria solicitacao e gera 3 cotacoes |
| `POST` | `/demo-contratar-frete` | Etapa 2 do fluxo demo: confirma cotacao e inicia rastreio |
| `GET` | `/solicitacoes` | Lista todas as solicitacoes de frete |
| `GET` | `/solicitacoes/{id}` | Detalha uma solicitacao com cotacoes e frete selecionado |
| `GET` | `/solicitacoes/{id}/cotacoes` | Lista as cotacoes de uma solicitacao |
| `GET` | `/fretes-selecionados` | Lista todos os fretes selecionados |

---

## Modelo de Dados

O microsservico realiza apenas operacoes DML (SELECT, INSERT, UPDATE, DELETE). O DDL das tabelas e de responsabilidade exclusiva da equipe de banco de dados.

As tabelas mapeadas no schema `portal_b2b` sao:

- `solicitacao_frete` — Registro de cada solicitacao de cotacao de frete
- `cotacao_frete` — Cotacoes recebidas de transportadoras para cada solicitacao
- `frete_selecionado` — Frete escolhido e contratado para cada pedido
- `empresa`, `perfil`, `empresa_perfil`, `pedido` — Tabelas de dominio compartilhadas

---

## Acesso ao Frontend

Em ambiente de desenvolvimento local (sem o gateway do Portal B2B), o frontend esta disponivel em:

```
http://localhost:8088/logistica/
```

O Nginx do container `logistica-front` faz proxy das requisicoes `/api/logistica/*` diretamente para o backend `logistica-service:5008` dentro da rede Docker, sem dependencia do gateway externo.
