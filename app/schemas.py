"""
schemas.py — Schemas Pydantic para validação de entrada/saída e envelope Kafka.

Segue o envelope obrigatório definido no Guia de Integração (seção 17):
  eventId, eventType, eventVersion, timestamp, source, correlationId, payload
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# Schemas de Entrada
# ============================================================

class SolicitacaoFreteCreate(BaseModel):
    """Dados para criar uma solicitação de frete (simulação de pedido de vendas)."""

    pedido_id: uuid.UUID = Field(
        ..., description="UUID do pedido (vindo da equipe de Vendas/Pedidos)"
    )
    tipo_transporte: str = Field(
        ...,
        max_length=50,
        description="Tipo de transporte (ex: RODOVIARIO, AEREO, MARITIMO)",
    )
    # Campos extras para o payload Kafka (não persistidos na tabela DDL atual)
    tipo_veiculo: Optional[str] = Field(
        None, max_length=100, description="Tipo de veículo solicitado"
    )
    tipo_carga: Optional[str] = Field(
        None, max_length=100, description="Tipo de carga"
    )
    cep_origem: Optional[str] = Field(
        None, max_length=8, description="CEP de origem"
    )
    cep_destino: Optional[str] = Field(
        None, max_length=8, description="CEP de destino"
    )


# ============================================================
# Schemas de Resposta
# ============================================================

class CotacaoFreteResponse(BaseModel):
    """Resposta com dados de uma cotação de frete."""

    id: uuid.UUID
    solicitacao_id: uuid.UUID
    transportadora_id: uuid.UUID
    valor: Decimal
    prazo: int
    data_cotacao: datetime

    model_config = {"from_attributes": True}


class FreteSelecionadoResponse(BaseModel):
    """Resposta com dados do frete selecionado."""

    id: uuid.UUID
    pedido_id: uuid.UUID
    cotacao_id: uuid.UUID
    data_selecao: datetime
    cotacao: Optional[CotacaoFreteResponse] = None

    model_config = {"from_attributes": True}


class SolicitacaoFreteResponse(BaseModel):
    """Resposta com dados de uma solicitação de frete."""

    id: uuid.UUID
    pedido_id: uuid.UUID
    tipo_transporte: str
    status: str
    data_criacao: datetime
    cotacoes: list[CotacaoFreteResponse] = []
    frete_selecionado: Optional[FreteSelecionadoResponse] = None

    model_config = {"from_attributes": True}


class SolicitacaoFreteResumo(BaseModel):
    """Resposta resumida (sem nested) para listagens."""

    id: uuid.UUID
    pedido_id: uuid.UUID
    tipo_transporte: str
    status: str
    data_criacao: datetime

    model_config = {"from_attributes": True}


# ============================================================
# Envelope Kafka Oficial
# ============================================================

class KafkaEnvelope(BaseModel):
    """
    Envelope obrigatório para todos os eventos Kafka do Portal B2B.

    Referência: Guia de Integração, seção 17.
    """

    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    eventType: str
    eventVersion: str = "1.0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: str = "logistica-service"
    correlationId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any] = {}


# ============================================================
# Health Check
# ============================================================

class HealthResponse(BaseModel):
    """Resposta do endpoint /health."""

    status: str = "ok"
    service: str = "logistica-service"
