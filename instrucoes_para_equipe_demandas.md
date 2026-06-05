# Guia de Integração — Demandas ↔ Logística (Equipe 8)

> **Versão:** 4.0 (Fluxo Descentralizado)  
> **Autor:** Equipe 8 — Logística (`logistica-service`)  

---

## 1. Visão Geral: Fluxo de Frete Manual

A escolha de frete **não é mais automática**. A Equipe 8 (Logística) é responsável por gerar as cotações e orquestrar a entrega física, mas a **Equipe de Demandas** agora é a responsável oficial por tomar a decisão de qual cotação de frete será contratada para cada pedido.

O novo fluxo funciona da seguinte maneira:

1. A Logística recebe o evento de pedido e gera cotações reais com as transportadoras.
2. A solicitação de frete entra no status **`COTADO`** e a Logística **pausa o fluxo**.
3. A Equipe de **Demandas deve consumir a API REST da Logística** para visualizar as cotações disponíveis.
4. A Equipe de **Demandas seleciona manualmente a cotação desejada** enviando um comando `POST` para a Logística.
5. A Logística retoma o fluxo, atualiza o status para `SELECIONADO`, publica o contrato no Kafka e inicia a operação logística de rastreio até a entrega.

---

## 2. Autenticação (JWT Obrigatório)

Nossa API agora é protegida via JWT (JSON Web Token). Para consumir qualquer rota REST (incluindo listar cotações e aprovar fretes), a aplicação de Demandas deve possuir um token assinado pela chave secreta do Portal B2B.

**Como enviar o token?**

O método preferencial de injeção estabelecido no portal é via **Query String**, facilitando redirecionamentos:

`http://<IP_GATEWAY>/api/logistica/solicitacoes?jwt=SEU_TOKEN_AQUI`

Você também pode utilizar o tradicional header HTTP de Autorização, caso esteja fazendo integrações server-to-server seguras:
`Authorization: Bearer SEU_TOKEN_AQUI`

*(Para o ambiente de Sandbox local do frontend, a interface injeta um token mestre automaticamente. Contudo, em Produção, a sua aplicação de Demandas deve resgatar o token do usuário logado e enviá-lo nas requisições de API).*

---

## 3. Consumo da API REST (Integração)

Abaixo estão as duas rotas principais que a Equipe de Demandas precisa integrar em sua aplicação para operar o fluxo de fretes.

### A. Visualizar as Cotações Disponíveis

Quando vocês precisarem montar a tela para o usuário escolher o frete, consultem a nossa API para listar os valores que captamos.

**Rota:** `GET /solicitacoes/{solicitacao_id}/cotacoes`  
*(Lembre-se de anexar o token de autenticação)*

**Resposta de Sucesso (200 OK):**
```json
[
  {
    "id": "c0746b1c-7708-410a-8d19-90b9b3e1f579",
    "transportadora_id": "b32bd9f2-6122-4c84-b721-b284aec606e1",
    "valor": 2204.90,
    "prazo": 7
  },
  {
    "id": "a9317b2b-4221-420a-8c11-10c9b3e1f981",
    "transportadora_id": "c13cd9f2-7122-5c84-a721-c284aec606e2",
    "valor": 2626.44,
    "prazo": 4
  }
]
```
*A interface de Demandas deve exibir esses valores, prazos e a transportadora para a tomada de decisão.*

### B. Contratar o Frete Escolhido

Após a seleção ser feita, a sua aplicação deve engatilhar a contração avisando a Logística.

**Rota:** `POST /demo-contratar-frete`  
*(Lembre-se de anexar o token de autenticação)*

**Payload (JSON):**
```json
{
  "solicitacao_id": "2e5f5fec-d840-4d87-9e75-b43ea56d31b8",
  "cotacao_id": "c0746b1c-7708-410a-8d19-90b9b3e1f579"
}
```

Após o sucesso dessa chamada, a Logística assumirá o controle publicando o evento `frete_contratado` no Kafka e fará a carga avançar pelos status de transporte até ser `ENTREGUE`.

---

## 4. Tópicos do Kafka (O que vocês podem escutar)

Apesar da interação de escolha ser via REST, a Equipe de Demandas pode escutar os tópicos do Kafka para atualizar o status da entrega no seu sistema de forma passiva (Event-Driven).

Os tópicos produzidos ativamente pela Logística são:

- **`cotacao_frete_enviada`**: Emitido assim que geramos uma cotação nova (Indicativo para atualizar a tela).
- **`frete_contratado`**: Emitido logo após vocês aprovarem a cotação via API REST. Serve como um recibo global.
- **`logistica_status_atualizado`**: Avisa sobre o progresso físico da entrega (`EM_TRANSITO` e por fim `ENTREGUE`).

---

## 5. Endereços Úteis

Se você quiser testar as requisições manualmente usando o Swagger oficial da Logística:

| Recurso | URL |
|---------|----------|
| **Logística API (Gateway Produção)** | `http://<IP_DO_GATEWAY>/api/logistica/docs` |
| **Logística API (Sandbox Local)** | `http://localhost:5008/docs` |

> Dúvidas na formatação dos Payloads JSON, mapeamento de UUIDs ou integração JWT? A Equipe 8 está à disposição!
