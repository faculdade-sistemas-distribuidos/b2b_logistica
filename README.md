# Logística Service — Portal B2B (Equipe 8)

> Microsserviço de Logística do Portal B2B — CMP1896 Sistemas Distribuídos (PUC-GO)

## Visão Geral

O `logistica-service` é o orquestrador do fluxo de frete no Portal B2B. Recebe solicitações de frete
originadas pela equipe de Vendas, publica no Kafka para cotação pelas Transportadoras (Equipe 9),
seleciona automaticamente a cotação de menor valor e simula o ciclo completo de entrega.

---

## Infraestrutura

| Recurso | Endereço |
|---------|----------|
| **Porta do serviço** | `5008` |
| **Load Balancer** | `34.8.17.245` |
| **PostgreSQL (Cloud SQL)** | `136.114.235.212:5432` |
| **Kafka (Redpanda)** | `redpanda:9092` (rede Docker interna) |
| **Kafka UI** | `http://34.29.84.207:8080` |

---

## Endpoints REST

### Health Check
```
GET /health
```
Retorna o status do serviço. O API Gateway mapeia para `/api/logistica/health`.

**Resposta:**
```json
{"status": "ok", "service": "logistica-service"}
```

### Solicitar Frete (Simulação de Vendas)
```
POST /solicitar-externo
```
Simula o recebimento de um pedido da equipe de Vendas. Grava a solicitação no banco e
publica `solicitacao_frete_criada` no Kafka.

### Demo — Fluxo Completo
```
POST /demo-fluxo-completo
```
Endpoint de demonstração para apresentação em aula. Executa o fluxo completo automaticamente:

| Tempo | Status | Ação |
|-------|--------|------|
| 0s | `AGUARDANDO` | Solicitação criada + evento Kafka |
| ~2s | — | 3 cotações simuladas publicadas |
| ~5s | `SELECIONADO` | Consumer seleciona menor valor |
| ~15s | `EM_TRANSITO` | Simulação de despacho |
| ~35s | `ENTREGUE` | Simulação de entrega finalizada |

### Listar Solicitações
```
GET /solicitacoes
GET /solicitacoes/{id}
```

### Listar Cotações de uma Solicitação
```
GET /solicitacoes/{id}/cotacoes
```

### Listar Fretes Selecionados
```
GET /fretes-selecionados
```

### Swagger/OpenAPI
```
http://localhost:5008/docs
```

---

## Tópicos Kafka

### Publica (Producer)

| Tópico | Quando |
|--------|--------|
| `solicitacao_frete_criada` | Ao receber solicitação de frete (POST /solicitar-externo ou /demo-fluxo-completo) |
| `frete_selecionado` | Ao selecionar a cotação de menor valor |
| `logistica_status_atualizado` | A cada transição de status (EM_TRANSITO, ENTREGUE) |

### Consome (Consumer)

| Tópico | Ação |
|--------|------|
| `cotacao_frete_enviada` | Recebe cotações das Transportadoras (Equipe 9), grava no banco e seleciona a melhor |

### Envelope Kafka Obrigatório

Todos os eventos seguem o envelope oficial do Portal B2B (seção 17 do Guia de Integração):

```json
{
  "eventId": "<UUID v4>",
  "eventType": "<nome_do_topico>",
  "eventVersion": "1.0",
  "timestamp": "<ISO 8601>",
  "source": "logistica-service",
  "correlationId": "<UUID v4>",
  "payload": { ... }
}
```

---

## Estrutura do Projeto

```
logistica-b2b/
├── app/
│   ├── __init__.py
│   ├── main.py            # Entrypoint FastAPI + lifespan (Kafka lifecycle)
│   ├── database.py        # SQLAlchemy async engine (Cloud SQL)
│   ├── models.py          # Mapeamento das tabelas portal_b2b.*
│   ├── schemas.py         # Pydantic schemas + envelope Kafka
│   ├── routes.py          # Rotas REST + endpoint de demo
│   └── kafka_handler.py   # Producer, Consumer e simulação de rastreio
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                   # Variáveis de ambiente (não versionado)
├── .env.example           # Template de variáveis
├── instrucoes_para_equipe_9.md  # Guia de integração para Transportadoras
└── README.md              # Este arquivo
```

---

## Configuração e Execução

### 1. Criar o `.env`

```bash
cp .env.example .env
```

O `.env` já contém os valores oficiais:

```env
SERVICE_NAME=logistica-service
PORT=5008
DATABASE_URL=postgresql://svc_portal_b2b:senha_portal_b2b@136.114.235.212:5432/portal_b2b
DB_SCHEMA=portal_b2b
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
```

### 2. Build e Execução

```bash
# Criar a rede (se não existir)
docker network create portal-b2b-network

# Build e subir
docker compose up -d --build
```

### 3. Verificar

```bash
# Health check
curl http://localhost:5008/health

# Logs em tempo real
docker logs -f logistica-service
```

### 4. Testar Fluxo Completo (Demo)

```bash
curl -X POST http://localhost:5008/demo-fluxo-completo \
  -H "Content-Type: application/json" \
  -d '{
    "pedido_id": "550e8400-e29b-41d4-a716-446655440000",
    "tipo_transporte": "RODOVIARIO",
    "cep_origem": "74000000",
    "cep_destino": "01001000",
    "tipo_veiculo": "CAMINHAO_TRUNK"
  }'
```

Após ~35 segundos, acompanhe a evolução:
```bash
# Ver solicitação com cotações
curl http://localhost:5008/solicitacoes/{id_retornado}

# Ver frete selecionado (vencedor)
curl http://localhost:5008/fretes-selecionados
```

---

## Banco de Dados

- **Schema:** `portal_b2b`
- **Tabelas utilizadas** (criadas pela equipe de BD — DDL script 04):
  - `portal_b2b.solicitacao_frete` — Solicitações de frete
  - `portal_b2b.cotacao_frete` — Cotações recebidas das transportadoras
  - `portal_b2b.frete_selecionado` — Frete selecionado (menor valor)
- **Regra:** O serviço **não executa DDL** (CREATE TABLE, ALTER TABLE). Apenas DML (SELECT, INSERT, UPDATE).

---

## Ciclo de Vida dos Status

```
AGUARDANDO ──▶ SELECIONADO ──(10s)──▶ EM_TRANSITO ──(20s)──▶ ENTREGUE
```

| Status | Descrição |
|--------|-----------|
| `AGUARDANDO` | Solicitação criada, aguardando cotações |
| `SELECIONADO` | Cotação vencedora escolhida (menor valor) |
| `EM_TRANSITO` | Carga em transporte (simulado: 10s após seleção) |
| `ENTREGUE` | Entrega concluída (simulado: 20s após trânsito) |

---

## Dependências

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
aiokafka==0.12.0
pydantic==2.10.3
python-dotenv==1.0.1
```

---

## Equipe

**Equipe 8 — Logística** | CMP1896 — Sistemas Distribuídos | PUC-GO
