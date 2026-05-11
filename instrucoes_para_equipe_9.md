# Guia de Integração — Equipe 9 (Transportadoras) ↔ Equipe 8 (Logística)

> **Versão:** 1.1  
> **Autor:** Equipe 8 — Logística (`logistica-service`)  
> **Data:** 2026-05-10  
> **Contato técnico:** Equipe 8 — Portal B2B

---

## 1. Visão Geral do Fluxo

A **Equipe 8 (Logística)** atua como **orquestradora** do fluxo de frete no Portal B2B. O ciclo completo funciona assim:

```
┌──────────┐         ┌──────────────────┐         ┌────────────────────┐
│  VENDAS  │ ──────▶ │    LOGÍSTICA     │ ──────▶ │  TRANSPORTADORAS   │
│ (Equipe) │  pedido │   (Equipe 8)     │  Kafka  │    (Equipe 9)      │
└──────────┘ criado  └──────────────────┘         └────────────────────┘
                            │                             │
                            │  solicitacao_frete_criada    │
                            │ ──────────────────────────▶  │
                            │                              │
                            │  cotacao_frete_enviada       │
                            │ ◀──────────────────────────  │
                            │                              │
                            │  frete_selecionado           │
                            │ ──────────────────────────▶  │
                            ▼                              ▼
```

### Resumo do fluxo

1. **Vendas** envia um pedido com tipo de carga, veículo, CEP de origem e CEP de destino.
2. **Logística (nós)** recebe o pedido, grava a solicitação no banco e publica o evento `solicitacao_frete_criada` no Kafka.
3. **Transportadoras (vocês)** consomem o evento, calculam valor e prazo, e publicam `cotacao_frete_enviada`.
4. **Logística (nós)** consome as cotações, seleciona a **menor valor** e publica `frete_selecionado`.

---

## 2. Tópicos Kafka

| Tópico                     | Produtor                       | Consumidor                     | Descrição                                    |
| -------------------------- | ------------------------------ | ------------------------------ | -------------------------------------------- |
| `solicitacao_frete_criada` | Logística (Equipe 8)           | **Transportadoras (Equipe 9)** | Nova solicitação de frete para cotação       |
| `cotacao_frete_enviada`    | **Transportadoras (Equipe 9)** | Logística (Equipe 8)           | Cotação de frete enviada pela transportadora |
| `frete_selecionado`        | Logística (Equipe 8)           | Transportadoras (Equipe 9)     | Notificação da cotação vencedora             |

**Kafka Bootstrap Servers:** `redpanda:9092` (rede interna Docker)

---

## 3. Envelope Obrigatório — Padrão Portal B2B

**Todos** os eventos publicados no Kafka **devem** seguir o envelope oficial definido no Guia de Integração (seção 17). Mensagens fora deste formato serão **ignoradas**.

### Estrutura do Envelope

```json
{
  "eventId": "<UUID v4 — identificador único do evento>",
  "eventType": "<nome do tópico>",
  "eventVersion": "1.0",
  "timestamp": "<ISO 8601 — ex: 2026-05-10T22:30:00.000Z>",
  "source": "transportadoras-service",
  "correlationId": "<UUID v4 — MESMO correlationId recebido na solicitação>",
  "payload": { ... }
}
```

### Campos do Envelope

| Campo           | Tipo                | Obrigatório | Descrição                                                                                                                                  |
| --------------- | ------------------- |:-----------:| ------------------------------------------------------------------------------------------------------------------------------------------ |
| `eventId`       | `string (UUID v4)`  | ✅           | Identificador único do evento. Gerar um novo UUID para cada mensagem publicada.                                                            |
| `eventType`     | `string`            | ✅           | Nome do tópico. Para cotações: `"cotacao_frete_enviada"`.                                                                                  |
| `eventVersion`  | `string`            | ✅           | Versão do contrato. Usar `"1.0"`.                                                                                                          |
| `timestamp`     | `string (ISO 8601)` | ✅           | Data/hora de criação do evento em UTC. Exemplo: `"2026-05-10T22:30:00.000Z"`.                                                              |
| `source`        | `string`            | ✅           | Nome do serviço que originou o evento. Usar `"transportadoras-service"`.                                                                   |
| `correlationId` | `string (UUID v4)`  | ✅           | **Deve ser o mesmo** `correlationId` recebido no evento `solicitacao_frete_criada`. Isso permite rastreamento ponta-a-ponta no Portal B2B. |
| `payload`       | `object`            | ✅           | Dados de negócio do evento (ver seção 4).                                                                                                  |

> **IMPORTANTE:** O `correlationId` é essencial para rastreabilidade. Repassem o mesmo valor recebido na solicitação original.

---

## 4. Contrato: Evento `solicitacao_frete_criada` (vocês consomem)

Este é o evento que **vocês devem consumir** do tópico `solicitacao_frete_criada`.

### Payload que vocês receberão

```json
{
  "eventId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "eventType": "solicitacao_frete_criada",
  "eventVersion": "1.0",
  "timestamp": "2026-05-10T22:30:00.000Z",
  "source": "logistica-service",
  "correlationId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "payload": {
    "solicitacao_id": "c56a4180-65aa-42ec-a945-5fd21dec0538",
    "pedido_id": "550e8400-e29b-41d4-a716-446655440000",
    "tipo_transporte": "RODOVIARIO",
    "tipo_veiculo": "CAMINHAO_TRUNK",
    "tipo_carga": "GRANEL",
    "cep_origem": "74000000",
    "cep_destino": "01001000"
  }
}
```

### Campos do Payload (solicitação)

| Campo             | Tipo                 | Sempre presente | Descrição                                                                 |
| ----------------- | -------------------- |:---------------:| ------------------------------------------------------------------------- |
| `solicitacao_id`  | `string (UUID)`      | ✅               | ID da solicitação de frete. **Usar este valor na resposta.**              |
| `pedido_id`       | `string (UUID)`      | ✅               | ID do pedido de vendas que originou a solicitação.                        |
| `tipo_transporte` | `string`             | ✅               | Tipo de transporte. Valores possíveis: `RODOVIARIO`, `AEREO`, `MARITIMO`. |
| `tipo_veiculo`    | `string`             | ❌               | Tipo de veículo solicitado. Ex: `CAMINHAO_TRUNK`, `VAN`, `CARRETA`.       |
| `tipo_carga`      | `string`             | ❌               | Tipo de carga. Ex: `GRANEL`, `FRACIONADA`, `CONTAINER`.                   |
| `cep_origem`      | `string (8 dígitos)` | ❌               | CEP de origem da carga.                                                   |
| `cep_destino`     | `string (8 dígitos)` | ❌               | CEP de destino da carga.                                                  |

> **Dica:** Os campos `tipo_veiculo`, `tipo_carga`, `cep_origem` e `cep_destino` podem ser `null` ou ausentes. Tratem como opcionais na lógica de vocês.

---

## 5. Contrato: Evento `cotacao_frete_enviada` (vocês publicam)

Este é o evento que **vocês devem publicar** no tópico `cotacao_frete_enviada` após calcular o valor e prazo do frete.

### Exemplo completo com envelope

```json
{
  "eventId": "9f86d081-884c-4d65-a502-c8e9f7320b18",
  "eventType": "cotacao_frete_enviada",
  "eventVersion": "1.0",
  "timestamp": "2026-05-10T22:35:00.000Z",
  "source": "transportadoras-service",
  "correlationId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "payload": {
    "solicitacao_id": "c56a4180-65aa-42ec-a945-5fd21dec0538",
    "transportadora_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
    "valor": 1250.75,
    "prazo": 5
  }
}
```

### Campos obrigatórios do Payload (cotação)

| Campo               | Tipo               | Obrigatório | Descrição                                                                                                                        |
| ------------------- | ------------------ |:-----------:| -------------------------------------------------------------------------------------------------------------------------------- |
| `solicitacao_id`    | `string (UUID)`    | ✅           | O **mesmo** `solicitacao_id` recebido no evento `solicitacao_frete_criada`. Identifica a qual solicitação esta cotação pertence. |
| `transportadora_id` | `string (UUID)`    | ✅           | UUID que identifica a transportadora que está enviando a cotação.                                                                |
| `valor`             | `number (Decimal)` | ✅           | Valor do frete em reais (R$). Precisão de até 4 casas decimais. Exemplo: `1250.7500`.                                            |
| `prazo`             | `integer`          | ✅           | Prazo de entrega em **dias úteis**. Exemplo: `5`.                                                                                |

> **ATENÇÃO:** Todos os 4 campos do payload são **obrigatórios**. Mensagens com campos ausentes ou `null` serão **descartadas** pelo nosso consumer.

### Validações aplicadas pelo logistica-service

```python
# Nosso consumer valida assim:
if not all([solicitacao_id, transportadora_id, valor, prazo]):
    logger.warning("Payload incompleto — cotação ignorada")
    return
```

---

## 6. Evento `frete_selecionado` (informativo)

Após recebermos **uma ou mais cotações** para a mesma solicitação, nossa lógica automaticamente:

1. **Compara todas as cotações** recebidas para aquela `solicitacao_id`.
2. **Seleciona a cotação com menor valor** (`ORDER BY valor ASC LIMIT 1`).
3. **Atualiza o status** da solicitação para `SELECIONADO`.
4. **Publica o evento** `frete_selecionado` no Kafka.

### Payload do evento `frete_selecionado`

```json
{
  "eventId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "eventType": "frete_selecionado",
  "eventVersion": "1.0",
  "timestamp": "2026-05-10T22:40:00.000Z",
  "source": "logistica-service",
  "correlationId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "payload": {
    "pedido_id": "550e8400-e29b-41d4-a716-446655440000",
    "solicitacao_id": "c56a4180-65aa-42ec-a945-5fd21dec0538",
    "cotacao_id": "9f86d081-884c-4d65-a502-c8e9f7320b18",
    "transportadora_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
    "valor": "1250.7500",
    "prazo": 5
  }
}
```

> **Nota:** A cada nova cotação recebida, reavaliamos **todas** as cotações da solicitação. Se uma cotação mais barata chegar depois, o frete selecionado é **atualizado** automaticamente.

---

## 7. Configurações Recomendadas para o Consumer

```python
# Exemplo com aiokafka (Python)
consumer = AIOKafkaConsumer(
    "solicitacao_frete_criada",
    bootstrap_servers="redpanda:9092",
    group_id="transportadoras-service-group",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="earliest",
    enable_auto_commit=True,
)
```

```java
// Exemplo com Spring Kafka (Java)
@KafkaListener(
    topics = "solicitacao_frete_criada",
    groupId = "transportadoras-service-group"
)
public void consumirSolicitacao(String message) {
    JsonNode envelope = objectMapper.readTree(message);
    JsonNode payload = envelope.get("payload");
    String solicitacaoId = payload.get("solicitacao_id").asText();
    // ... processar e gerar cotação
}
```

---

## 8. Diagrama de Sequência

```
 Vendas          Logística (Equipe 8)         Transportadoras (Equipe 9)
   │                     │                              │
   │  pedido_criado      │                              │
   │────────────────────▶│                              │
   │                     │                              │
   │                     │ [Grava solicitação no DB]     │
   │                     │                              │
   │                     │  solicitacao_frete_criada     │
   │                     │─────────────────────────────▶│
   │                     │                              │
   │                     │                  [Calcula cotação]
   │                     │                              │
   │                     │  cotacao_frete_enviada        │
   │                     │◀─────────────────────────────│
   │                     │                              │
   │                     │ [Grava cotação no DB]         │
   │                     │ [Seleciona menor valor]       │
   │                     │                              │
   │                     │  frete_selecionado            │
   │                     │─────────────────────────────▶│
   │                     │                              │
```

---

## 9. Checklist de Integração

- [ ] Configurar consumer para o tópico `solicitacao_frete_criada`
- [ ] Deserializar o envelope JSON e extrair o `payload`
- [ ] Armazenar o `correlationId` para repassar na resposta
- [ ] Implementar lógica de cálculo de frete (valor + prazo)
- [ ] Publicar no tópico `cotacao_frete_enviada` com envelope oficial
- [ ] Garantir que `source` está como `"transportadoras-service"`
- [ ] Validar que os 4 campos do payload estão presentes e não-nulos
- [ ] (Opcional) Consumir `frete_selecionado` para saber se a cotação foi aceita

---

## 10. Informações de Infraestrutura

| Recurso                     | Endereço                              |
| --------------------------- | ------------------------------------- |
| Kafka (Redpanda)            | `redpanda:9092` (rede Docker interna) |
| Kafka UI                    | `http://34.29.84.207:8080`            |
| PostgreSQL (Cloud SQL)      | `136.114.235.212:5432`                |
| Logística Service (Health)  | `http://localhost:5008/health`        |
| Logística Service (Swagger) | `http://localhost:5008/docs`          |

---

## 11. Simulação Interna de Cotações (Fallback para Demo)

> **Aviso importante para a Equipe 9:**

Para garantir a **robustez da demonstração em aula**, o `logistica-service` possui um endpoint de demo (`POST /demo-fluxo-completo`) que **simula internamente** o envio de 3 cotações fictícias no tópico `cotacao_frete_enviada`.

### Por que isso existe?

Caso a Equipe 9 enfrente **problemas técnicos** durante a apresentação (container fora do ar, erro de conexão Kafka, etc.), o fluxo completo da Logística pode ser demonstrado de forma autônoma usando cotações simuladas.

### O que acontece quando vocês e a simulação coexistem?

- **Sem conflito.** As cotações de vocês e as cotações simuladas são processadas normalmente pelo consumer.
- O algoritmo de seleção compara **todas** as cotações (reais + simuladas) e seleciona a de **menor valor**, independente da origem.
- Em produção, o endpoint de demo **não será utilizado** — ele existe apenas para fins acadêmicos.

### Cotações simuladas geradas

| Transportadora (fictícia) | UUID Fixo                              | Valor                    | Prazo                 |
| ------------------------- | -------------------------------------- | ------------------------ | --------------------- |
| TransLog Express          | `aaa11111-1111-1111-1111-111111111111` | Aleatório (R$500–R$2000) | Aleatório (2–15 dias) |
| Rodo Frete Brasil         | `bbb22222-2222-2222-2222-222222222222` | Aleatório (R$500–R$2000) | Aleatório (2–15 dias) |
| CargoVia Sul              | `ccc33333-3333-3333-3333-333333333333` | Aleatório (R$500–R$2000) | Aleatório (2–15 dias) |

> **Nota:** Os UUIDs das transportadoras fictícias são **fixos e reconhecíveis** (padrão `aaa...`, `bbb...`, `ccc...`), facilitando a distinção entre cotações reais e simuladas nos logs e no banco.

---

## 12. Ciclo de Vida dos Status (Rastreio)

Após a seleção do frete vencedor, o `logistica-service` simula automaticamente o ciclo de transporte. O campo `status` da tabela `solicitacao_frete` percorre os seguintes estados:

```
AGUARDANDO ──(cotações chegam)──▶ SELECIONADO ──(10s)──▶ EM_TRANSITO ──(20s)──▶ ENTREGUE
```

| Estado        | Descrição                                 | Duração simulada          |
| ------------- | ----------------------------------------- |:-------------------------:|
| `AGUARDANDO`  | Solicitação criada, aguardando cotações   | —                         |
| `SELECIONADO` | Cotação vencedora escolhida (menor valor) | Imediato após cotações    |
| `EM_TRANSITO` | Carga despachada, em transporte           | 10 segundos após seleção  |
| `ENTREGUE`    | Entrega finalizada com sucesso            | 20 segundos após trânsito |

### Tópico de acompanhamento: `logistica_status_atualizado`

A cada transição de status, publicamos um evento no tópico `logistica_status_atualizado`:

```json
{
  "eventType": "logistica_status_atualizado",
  "source": "logistica-service",
  "correlationId": "<mesmo do fluxo>",
  "payload": {
    "solicitacao_id": "<UUID>",
    "pedido_id": "<UUID>",
    "status_anterior": "SELECIONADO",
    "status_atual": "EM_TRANSITO"
  }
}
```

> **Para o Frontend:** O status pode ser consultado via polling em `GET /solicitacoes/{id}` ou monitorando o tópico `logistica_status_atualizado` no Kafka.

---

> **Dúvidas?** Entrem em contato com a Equipe 8 (Logística). Estamos disponíveis para apoiar na integração e realizar testes conjuntos via Kafka UI.

---
