# Guia de Integração — Equipe 7 (Vendas) ↔ Equipe 8 (Logística)

> **Versão:** 2.0  
> **Autor:** Equipe 8 — Logística (`logistica-service`)  
> **Data:** 2026-05-11  
> **Contato técnico:** Equipe 8 — Portal B2B

---

## 1. Visão Geral

A **Equipe 8 (Logística)** é responsável por receber os pedidos de venda e orquestrar todo o ciclo de frete, incluindo a simulação de cotações de transportadoras (responsabilidade previamente da Equipe 9, agora absorvida pela Equipe 8).

O fluxo de integração com a Equipe de Vendas é:

```
  Vendas (Equipe 7)              Logística (Equipe 8)
       │                              │
       │  pedido_criado (Kafka)        │
       │─────────────────────────────▶│
       │                              │ [Grava solicitação]
       │                              │ [Seleciona veículo por peso]
       │                              │ [Gera 3 cotações automáticas]
       │                              │ [Seleciona menor valor]
       │                              │ [Simula rastreio]
       │                              │
       │  frete_selecionado (Kafka)    │
       │◀─────────────────────────────│
       │                              │
       │  logistica_status_atualizado  │
       │◀─────────────────────────────│
       │                              │
```

### O que nós fazemos automaticamente

1. **Triagem de veículo:** Seleção automática do tipo de veículo com base no peso da carga.
2. **Cotações:** Geração automática de 3 cotações de transportadoras simuladas.
3. **Seleção:** Escolha da cotação com menor valor.
4. **Rastreio:** Simulação de `EM_TRANSITO` (10s) → `ENTREGUE` (20s).

> **A Equipe de Vendas só precisa postar no tópico `pedido_criado`.** Todo o restante é automatizado.

---

## 2. Tópico Kafka: `pedido_criado` (vocês publicam)

Este é o **único evento** que a Equipe de Vendas deve publicar para iniciar o fluxo de frete.

### Envelope Obrigatório

```json
{
  "eventId": "<UUID v4>",
  "eventType": "pedido_criado",
  "eventVersion": "1.0",
  "timestamp": "2026-05-11T10:00:00.000Z",
  "source": "vendas-service",
  "correlationId": "<UUID v4>",
  "payload": {
    "pedido_id": "550e8400-e29b-41d4-a716-446655440000",
    "tipo_transporte": "RODOVIARIO",
    "peso_carga": 2500.00,
    "cep_origem": "74000000",
    "cep_destino": "01001000"
  }
}
```

### Campos do Payload

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `pedido_id` | `string (UUID v4)` | ✅ | Identificador único do pedido de vendas. |
| `tipo_transporte` | `string` | ✅ | Modalidade de transporte: `RODOVIARIO`, `AEREO` ou `MARITIMO`. |
| `peso_carga` | `number (Decimal)` | ✅ | Peso total da carga em **kg**. Usado para triagem automática do veículo. |
| `cep_origem` | `string (8 dígitos)` | ✅ | CEP do local de coleta da carga. |
| `cep_destino` | `string (8 dígitos)` | ✅ | CEP do local de entrega da carga. |

### Campos Opcionais (melhoram a triagem)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo_carga_natureza` | `string` | Natureza da carga: `PERECIVEL`, `CARGA_LATERAL` ou `SECA_GERAL`. Relevante para cargas > 4.000 kg. Se omitido, assume `SECA_GERAL`. |
| `tipo_carga` | `string` | Classificação da carga: `GRANEL`, `FRACIONADA`, `CONTAINER`. |

---

## 3. Triagem Automática de Veículo

Baseado no `peso_carga`, nosso sistema seleciona automaticamente o veículo ideal:

| Porte | Faixa de Peso | Veículo | Descrição |
|-------|:------------:|---------|-----------|
| **Pequeno** | Até 1.500 kg | `FURGAO` | Entregas urbanas, e-commerce |
| **Médio** | 1.501 – 4.000 kg | `CAMINHAO_3_4` | Distribuição regional |
| **Grande** | > 4.000 kg + `SECA_GERAL` | `CAMINHAO_BAU_NORMAL` | Carga seca geral |
| **Grande** | > 4.000 kg + `PERECIVEL` | `CAMINHAO_BAU_FRIGORIFICO` | Cargas refrigeradas |
| **Grande** | > 4.000 kg + `CARGA_LATERAL` | `CAMINHAO_SIDER` | Descarga lateral rápida |

> **Vocês não precisam enviar `tipo_veiculo`.** Nós determinamos isso automaticamente pelo peso. Isso garante a eficiência operacional da entrega.

---

## 4. Faixas de Custo Estimadas

As cotações geradas pelo nosso sistema são calibradas por tipo de veículo:

| Veículo | Faixa de Valor (R$) | Prazo (dias úteis) |
|---------|:-------------------:|:------------------:|
| `FURGAO` | 350 – 900 | 1 – 4 |
| `CAMINHAO_3_4` | 800 – 1.800 | 2 – 7 |
| `CAMINHAO_BAU_NORMAL` | 1.500 – 3.500 | 3 – 10 |
| `CAMINHAO_BAU_FRIGORIFICO` | 2.200 – 4.500 | 2 – 6 |
| `CAMINHAO_SIDER` | 1.800 – 3.800 | 3 – 10 |

---

## 5. Eventos que Vocês Podem Consumir (Opcionais)

Após processar o pedido, publicamos os seguintes eventos que vocês podem consumir para acompanhar o status:

### `frete_selecionado`

Publicado quando a melhor cotação é selecionada:

```json
{
  "eventType": "frete_selecionado",
  "source": "logistica-service",
  "correlationId": "<mesmo do pedido_criado>",
  "payload": {
    "pedido_id": "550e8400-e29b-41d4-a716-446655440000",
    "solicitacao_id": "<UUID>",
    "cotacao_id": "<UUID>",
    "transportadora_id": "<UUID>",
    "valor": "850.50",
    "prazo": 3
  }
}
```

### `logistica_status_atualizado`

Publicado a cada transição de status:

```json
{
  "eventType": "logistica_status_atualizado",
  "source": "logistica-service",
  "payload": {
    "solicitacao_id": "<UUID>",
    "pedido_id": "<UUID>",
    "status_anterior": "SELECIONADO",
    "status_atual": "EM_TRANSITO"
  }
}
```

### Ciclo de Status

```
AGUARDANDO ──▶ SELECIONADO ──(10s)──▶ EM_TRANSITO ──(20s)──▶ ENTREGUE
```

---

## 6. Exemplos Práticos

### Exemplo 1 — Carga leve (e-commerce)

```json
{
  "pedido_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_transporte": "RODOVIARIO",
  "peso_carga": 800,
  "cep_origem": "74000000",
  "cep_destino": "01001000"
}
```

**→ Veículo:** `FURGAO` | **Frete estimado:** R$ 350–900 | **Prazo:** 1–4 dias

### Exemplo 2 — Carga média

```json
{
  "pedido_id": "660e9500-f39c-52e5-b827-557766551111",
  "tipo_transporte": "RODOVIARIO",
  "peso_carga": 3200,
  "cep_origem": "30130000",
  "cep_destino": "20040020"
}
```

**→ Veículo:** `CAMINHAO_3_4` | **Frete estimado:** R$ 800–1.800 | **Prazo:** 2–7 dias

### Exemplo 3 — Carga pesada perecível

```json
{
  "pedido_id": "770ea600-a40d-63f6-c938-668877662222",
  "tipo_transporte": "RODOVIARIO",
  "peso_carga": 12000,
  "tipo_carga_natureza": "PERECIVEL",
  "cep_origem": "13015100",
  "cep_destino": "01001000"
}
```

**→ Veículo:** `CAMINHAO_BAU_FRIGORIFICO` | **Frete estimado:** R$ 2.200–4.500 | **Prazo:** 2–6 dias

---

## 7. Configuração de Infraestrutura

| Recurso | Endereço |
|---------|----------|
| **Kafka (Redpanda)** | `redpanda:9092` (rede Docker interna) |
| **Kafka UI** | `http://34.29.84.207:8080` |
| **Database (Cloud SQL)** | `136.114.235.212:5432` |
| **Logística API (Gateway)** | `http://34.8.17.245/api/logistica/` |
| **Logística Dashboard** | `http://34.8.17.245:3000/` |
| **Swagger/OpenAPI** | `http://34.8.17.245/api/logistica/docs` |

---

## 8. Checklist de Integração para a Equipe de Vendas

- [ ] Publicar no tópico Kafka `pedido_criado` com o envelope oficial
- [ ] Incluir os campos obrigatórios: `pedido_id`, `tipo_transporte`, `peso_carga`, `cep_origem`, `cep_destino`
- [ ] (Opcional) Incluir `tipo_carga_natureza` para cargas > 4.000 kg
- [ ] (Opcional) Consumir `frete_selecionado` para saber o valor/prazo selecionado
- [ ] (Opcional) Consumir `logistica_status_atualizado` para rastrear entregas

---

> **Dúvidas?** Entrem em contato com a Equipe 8 (Logística). Estamos disponíveis para apoiar na integração e testes conjuntos via Kafka UI.

---
