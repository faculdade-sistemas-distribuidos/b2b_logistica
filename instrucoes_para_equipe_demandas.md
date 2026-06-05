# Guia de Integracao — Demandas com Logistica (Equipe 8)

> **Versao:** 5.0 (Fluxo Descentralizado — Pos-Auditoria de Pre-Deployment)
> **Autor:** Equipe 8 — Logistica (`logistica-service`)
> **Ultima revisao:** Alinhado com a auditoria SRE de pre-deployment e com o Guia Oficial de Integracao da infraestrutura.

---

## 1. Visao Geral: Fluxo de Frete Manual

A escolha de frete nao e automatica. A Equipe 8 (Logistica) e responsavel por gerar as cotacoes e orquestrar a entrega fisica, mas a Equipe de Demandas e a responsavel oficial por decidir qual cotacao de frete sera contratada para cada pedido.

O fluxo funciona da seguinte forma:

1. A Logistica recebe o evento de pedido e gera cotacoes reais com as transportadoras.
2. A solicitacao de frete entra no status `COTADO` e a Logistica pausa o fluxo.
3. A Equipe de Demandas consome a API REST da Logistica para visualizar as cotacoes disponiveis.
4. A Equipe de Demandas seleciona a cotacao desejada enviando um `POST` para a Logistica.
5. A Logistica retoma o fluxo, atualiza o status para `SELECIONADO`, publica o evento `frete_selecionado` no Kafka e inicia a simulacao de rastreio ate o status `ENTREGUE`.

---

## 2. Autenticacao (JWT Obrigatorio)

A API e protegida via JWT (JSON Web Token). Para consumir qualquer rota REST da Logistica, a aplicacao de Demandas deve possuir um token assinado pela chave secreta do Portal B2B.

**Metodo preferencial — Query String (para redirecionamentos do portal pai):**

```
http://34.8.17.245/api/logistica/solicitacoes?jwt=SEU_TOKEN_AQUI
```

**Metodo alternativo — Header HTTP (para integracoes server-to-server):**

```
Authorization: Bearer SEU_TOKEN_AQUI
```

Em ambiente Docker local de desenvolvimento, o frontend (`logistica-front`) injeta automaticamente um token mock quando o hostname detectado e `localhost` ou `127.0.0.1`. Esse mecanismo e restrito ao ambiente local e nunca e ativado em producao. Em producao, a aplicacao de Demandas deve obter o token do usuario autenticado e inclui-lo explicitamente nas requisicoes.

---

## 3. Consumo da API REST

As rotas abaixo sao as principais que a Equipe de Demandas precisa integrar para operar o fluxo de fretes.

Todas as rotas listadas sao internas ao microsservico. O gateway da infraestrutura aplica o prefixo `/api/logistica` antes de encaminhar ao container. As rotas nao devem ser chamadas com o prefixo no codigo interno, apenas pelo gateway externo.

### A. Visualizar as Cotacoes Disponiveis

Quando for necessario exibir as opcoes de frete ao usuario, consulte a API para listar os valores capturados das transportadoras.

**Rota:** `GET /solicitacoes/{solicitacao_id}/cotacoes`

**Exemplo de chamada via gateway de producao:**
```
GET http://34.8.17.245/api/logistica/solicitacoes/{solicitacao_id}/cotacoes
```

**Resposta de Sucesso (HTTP 200):**
```json
[
  {
    "id": "c0746b1c-7708-410a-8d19-90b9b3e1f579",
    "solicitacao_id": "2e5f5fec-d840-4d87-9e75-b43ea56d31b8",
    "transportadora_id": "b32bd9f2-6122-4c84-b721-b284aec606e1",
    "valor": 2204.90,
    "prazo": 7,
    "data_cotacao": "2025-06-05T14:00:00Z"
  },
  {
    "id": "a9317b2b-4221-420a-8c11-10c9b3e1f981",
    "solicitacao_id": "2e5f5fec-d840-4d87-9e75-b43ea56d31b8",
    "transportadora_id": "c13cd9f2-7122-5c84-a721-c284aec606e2",
    "valor": 2626.44,
    "prazo": 4,
    "data_cotacao": "2025-06-05T14:00:01Z"
  }
]
```

A interface de Demandas deve exibir valor, prazo e transportadora para subsidiar a tomada de decisao.

### B. Contratar o Frete Escolhido

Apos a selecao ser feita pelo operador, a aplicacao de Demandas deve notificar a Logistica.

**Rota:** `POST /demo-contratar-frete`

**Exemplo de chamada via gateway de producao:**
```
POST http://34.8.17.245/api/logistica/demo-contratar-frete
```

**Payload (application/json):**
```json
{
  "solicitacao_id": "2e5f5fec-d840-4d87-9e75-b43ea56d31b8",
  "cotacao_id": "c0746b1c-7708-410a-8d19-90b9b3e1f579"
}
```

**Resposta de Sucesso (HTTP 200):**

Retorna o objeto `SolicitacaoFrete` atualizado com o status `SELECIONADO`. Apos essa chamada, a Logistica publica o evento `frete_selecionado` no Kafka e inicia automaticamente a simulacao de rastreio (`SELECIONADO` -> `EM_TRANSITO` -> `ENTREGUE`).

**Codigos de erro relevantes:**

| Codigo | Significado |
|---|---|
| `400` | `solicitacao_id` ou `cotacao_id` ausentes ou invalidos |
| `404` | Solicitacao ou cotacao nao encontrada |
| `409` | Solicitacao ja processada ou pedido ja possui frete contratado |

---

## 4. Topicos Kafka

A Equipe de Demandas pode escutar os topicos publicados pela Logistica para atualizar o status da entrega de forma passiva (event-driven), sem necessidade de polling REST.

**Topicos publicados pela Logistica (voces consomem):**

| Topico | Quando e emitido |
|---|---|
| `solicitacao_frete_criada` | Ao criar uma nova solicitacao de cotacao |
| `cotacoes_frete_disponiveis` | Apos gerar as 3 cotacoes das transportadoras para uma solicitacao |
| `frete_selecionado` | Apos a contratacao confirmada — contem `pedido_id`, `cotacao_id`, `transportadora_id`, `valor` e `prazo` |
| `logistica_status_atualizado` | A cada transicao de status de rastreio (`EM_TRANSITO` e `ENTREGUE`) |

**Topico publicado pelo Demandas (voces publicam, a Logistica consome):**

| Topico | Quando publicar |
|---|---|
| `frete_contratado` | Alternativa assincrona ao `POST /demo-contratar-frete`. Payload obrigatorio: `solicitacao_id` e `cotacao_id`. |

Todos os eventos seguem o envelope padrao do Portal B2B:

```json
{
  "eventId": "uuid",
  "eventType": "nome_do_topico",
  "eventVersion": "1.0",
  "timestamp": "ISO8601",
  "source": "nome-do-servico",
  "correlationId": "uuid",
  "payload": {}
}
```

**Configuracao obrigatoria do Kafka para integracao:**

```env
KAFKA_BOOTSTRAP_SERVERS=10.128.0.2:9092,10.128.0.3:9092,10.128.0.4:9092
```

O cluster Redpanda opera com 3 brokers nos IPs internos da VPC do GCP listados acima. O endereco `redpanda:9092` e valido apenas para desenvolvimento local isolado com Docker. Nao deve ser usado em integracao ou producao.

---

## 5. Enderecos e Portas Oficiais

### Ambiente de Integracao e Producao (Load Balancer GCP)

| Recurso | URL |
|---|---|
| Frontend Logistica | `http://34.8.17.245/logistica/` |
| API Logistica — Health | `http://34.8.17.245/api/logistica/health` |
| API Logistica — Swagger | `http://34.8.17.245/api/logistica/docs` |
| Kafka UI (diagnostico) | `http://34.29.84.207:8080` |

### Ambiente de Desenvolvimento Local (Docker)

Para testar localmente sem depender do ambiente de integracao, suba os containers do projeto com:

```bash
docker compose up --build -d
```

| Recurso | URL local |
|---|---|
| Frontend Logistica | `http://localhost:8088/logistica/` |
| API Logistica — Health | `http://localhost:5008/health` |
| API Logistica — Swagger | `http://localhost:5008/docs` |

As portas `5008` (backend) e `8088` (frontend) sao as portas oficiais definidas pela equipe de infraestrutura e nao podem ser alteradas.

### Configuracao do `.env` local para desenvolvimento

```env
SERVICE_NAME=logistica-service
PORT=5008

DATABASE_URL=postgresql://svc_portal_b2b:senha_portal_b2b@136.114.235.212:5432/portal_b2b
DB_SCHEMA=portal_b2b
KAFKA_BOOTSTRAP_SERVERS=10.128.0.2:9092,10.128.0.3:9092,10.128.0.4:9092

ROOT_PATH=/api/logistica
```

O banco oficial e o Cloud SQL PostgreSQL em `136.114.235.212:5432`. O host `localhost` ou `postgres` nao deve ser usado para o banco em nenhum cenario de integracao.

---

## 6. Requisitos do Ambiente Docker

A rede Docker externa `portal-b2b-network` deve existir antes de subir os containers:

```bash
docker network create portal-b2b-network
```

O arquivo `.env` nunca deve ser commitado no repositorio. Ele esta listado no `.gitignore`. Utilize sempre o `.env.example` como base.

Duvidas sobre o fluxo de integracao, mapeamento de UUIDs ou formato dos payloads devem ser alinhadas diretamente com a Equipe 8.
