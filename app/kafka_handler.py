"""
kafka_handler.py — Produtor e Consumidor Kafka para o logistica-service.

Produtor:
  - Publica eventos no envelope oficial do Portal B2B.

Consumidor:
  - Escuta o tópico 'cotacao_frete_enviada' (Equipe 9 — Transportadoras).
  - Ao receber cotações, grava no banco e executa lógica de seleção (menor valor).
  - Publica 'frete_selecionado' após seleção.
  - Dispara simulação de rastreio (EM_TRANSITO → ENTREGUE) para demo.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import CotacaoFrete, FreteSelecionado, SolicitacaoFrete
from app.schemas import KafkaEnvelope

logger = logging.getLogger("logistica-service.kafka")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092")
SERVICE_NAME = os.getenv("SERVICE_NAME", "logistica-service")

# Tópicos oficiais
TOPIC_SOLICITACAO_CRIADA = "solicitacao_frete_criada"
TOPIC_COTACAO_ENVIADA = "cotacao_frete_enviada"
TOPIC_FRETE_SELECIONADO = "frete_selecionado"

# Instâncias globais gerenciadas pelo lifespan do FastAPI
producer: AIOKafkaProducer | None = None
consumer: AIOKafkaConsumer | None = None


# ============================================================
# Producer
# ============================================================

async def start_producer() -> None:
    """Inicia o producer Kafka."""
    global producer
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await producer.start()
        logger.info("Kafka producer iniciado em %s", KAFKA_BOOTSTRAP)
    except Exception as e:
        logger.error("Falha ao iniciar Kafka producer: %s", e)
        producer = None


async def stop_producer() -> None:
    """Para o producer Kafka."""
    global producer
    if producer:
        await producer.stop()
        producer = None
        logger.info("Kafka producer encerrado.")


async def publish_event(
    topic: str,
    payload: dict,
    correlation_id: str | None = None,
) -> None:
    """
    Publica um evento no formato envelope oficial do Portal B2B.

    Args:
        topic: Nome do tópico Kafka (= eventType).
        payload: Dados de negócio do evento.
        correlation_id: UUID de rastreamento entre serviços.
    """
    if producer is None:
        logger.warning(
            "Producer não inicializado. Evento %s não publicado.", topic
        )
        return

    envelope = KafkaEnvelope(
        eventType=topic,
        source=SERVICE_NAME,
        correlationId=correlation_id or str(uuid.uuid4()),
        payload=payload,
    )

    try:
        await producer.send_and_wait(
            topic=topic,
            key=envelope.correlationId,
            value=envelope.model_dump(),
        )
        logger.info(
            "Evento publicado: topic=%s eventId=%s correlationId=%s",
            topic,
            envelope.eventId,
            envelope.correlationId,
        )
    except Exception as e:
        logger.error("Falha ao publicar evento %s: %s", topic, e)


# ============================================================
# Consumer
# ============================================================

async def start_consumer() -> None:
    """Inicia o consumer Kafka para o tópico cotacao_frete_enviada."""
    global consumer
    try:
        consumer = AIOKafkaConsumer(
            TOPIC_COTACAO_ENVIADA,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=f"{SERVICE_NAME}-group",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await consumer.start()
        logger.info(
            "Kafka consumer iniciado. Tópico: %s", TOPIC_COTACAO_ENVIADA
        )
    except Exception as e:
        logger.error("Falha ao iniciar Kafka consumer: %s", e)
        consumer = None


async def stop_consumer() -> None:
    """Para o consumer Kafka."""
    global consumer
    if consumer:
        await consumer.stop()
        consumer = None
        logger.info("Kafka consumer encerrado.")


async def consume_loop() -> None:
    """
    Loop principal do consumer.

    Processa mensagens do tópico cotacao_frete_enviada:
      1. Extrai payload da cotação
      2. Grava cotacao_frete no banco
      3. Verifica se é a melhor cotação (menor valor) e seleciona
    """
    if consumer is None:
        logger.warning("Consumer não inicializado. Loop abortado.")
        return

    logger.info("Consumer loop iniciado. Aguardando cotações...")

    try:
        async for msg in consumer:
            try:
                await _process_cotacao_message(msg.value)
            except Exception as e:
                logger.error(
                    "Erro ao processar mensagem (offset=%s): %s",
                    msg.offset,
                    e,
                    exc_info=True,
                )
    except Exception as e:
        logger.error("Consumer loop encerrado com erro: %s", e)


async def _process_cotacao_message(message: dict) -> None:
    """
    Processa uma mensagem de cotação de frete.

    Espera o envelope oficial com payload contendo:
      - solicitacao_id (UUID)
      - transportadora_id (UUID)
      - valor (Decimal)
      - prazo (int)
    """
    payload = message.get("payload", {})
    correlation_id = message.get("correlationId", str(uuid.uuid4()))

    solicitacao_id = payload.get("solicitacao_id")
    transportadora_id = payload.get("transportadora_id")
    valor = payload.get("valor")
    prazo = payload.get("prazo")

    if not all([solicitacao_id, transportadora_id, valor, prazo]):
        logger.warning(
            "Mensagem cotacao_frete_enviada com payload incompleto: %s", payload
        )
        return

    logger.info(
        "Cotação recebida: solicitacao=%s transportadora=%s valor=%s prazo=%s",
        solicitacao_id,
        transportadora_id,
        valor,
        prazo,
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Verificar se a solicitação existe
            result = await session.execute(
                select(SolicitacaoFrete).where(
                    SolicitacaoFrete.id == uuid.UUID(str(solicitacao_id))
                )
            )
            solicitacao = result.scalar_one_or_none()

            if solicitacao is None:
                logger.warning(
                    "Solicitação %s não encontrada. Cotação ignorada.",
                    solicitacao_id,
                )
                return

            # 2. Gravar a cotação no banco
            cotacao = CotacaoFrete(
                solicitacao_id=uuid.UUID(str(solicitacao_id)),
                transportadora_id=uuid.UUID(str(transportadora_id)),
                valor=Decimal(str(valor)),
                prazo=int(prazo),
            )
            session.add(cotacao)
            await session.flush()

            logger.info("Cotação gravada: id=%s", cotacao.id)

            # 3. Selecionar a melhor cotação (menor valor)
            await _selecionar_melhor_cotacao(
                session, solicitacao, correlation_id
            )


async def _selecionar_melhor_cotacao(
    session: AsyncSession,
    solicitacao: SolicitacaoFrete,
    correlation_id: str,
) -> None:
    """
    Seleciona a cotação com menor valor para a solicitação.

    Atualiza o status da solicitação para 'SELECIONADO',
    grava frete_selecionado e publica evento no Kafka.
    """
    # Buscar todas as cotações da solicitação
    result = await session.execute(
        select(CotacaoFrete)
        .where(CotacaoFrete.solicitacao_id == solicitacao.id)
        .order_by(CotacaoFrete.valor.asc())
    )
    cotacoes = result.scalars().all()

    if not cotacoes:
        logger.info("Nenhuma cotação encontrada para solicitação %s.", solicitacao.id)
        return

    melhor_cotacao = cotacoes[0]  # Menor valor (ORDER BY valor ASC)

    # Verificar se já existe frete selecionado para este pedido
    result = await session.execute(
        select(FreteSelecionado).where(
            FreteSelecionado.pedido_id == solicitacao.pedido_id
        )
    )
    frete_existente = result.scalar_one_or_none()

    if frete_existente:
        # Atualizar se a nova cotação for melhor
        if melhor_cotacao.id != frete_existente.cotacao_id:
            frete_existente.cotacao_id = melhor_cotacao.id
            logger.info(
                "Frete selecionado atualizado: pedido=%s cotacao=%s valor=%s",
                solicitacao.pedido_id,
                melhor_cotacao.id,
                melhor_cotacao.valor,
            )
        else:
            logger.info(
                "Cotação selecionada mantida (já é a melhor): cotacao=%s",
                melhor_cotacao.id,
            )
            return
    else:
        # Criar novo frete selecionado
        frete = FreteSelecionado(
            pedido_id=solicitacao.pedido_id,
            cotacao_id=melhor_cotacao.id,
        )
        session.add(frete)
        logger.info(
            "Frete selecionado criado: pedido=%s cotacao=%s valor=%s",
            solicitacao.pedido_id,
            melhor_cotacao.id,
            melhor_cotacao.valor,
        )

    # Atualizar status da solicitação
    solicitacao.status = "SELECIONADO"

    await session.flush()

    # Publicar evento frete_selecionado
    await publish_event(
        topic=TOPIC_FRETE_SELECIONADO,
        correlation_id=correlation_id,
        payload={
            "pedido_id": str(solicitacao.pedido_id),
            "solicitacao_id": str(solicitacao.id),
            "cotacao_id": str(melhor_cotacao.id),
            "transportadora_id": str(melhor_cotacao.transportadora_id),
            "valor": str(melhor_cotacao.valor),
            "prazo": melhor_cotacao.prazo,
        },
    )

    # Disparar simulação de rastreio (EM_TRANSITO → ENTREGUE) em background
    asyncio.create_task(
        _simular_rastreio(
            solicitacao_id=str(solicitacao.id),
            pedido_id=str(solicitacao.pedido_id),
            correlation_id=correlation_id,
        )
    )


# ============================================================
# Simulação de Rastreio (Tracking) — Demo
# ============================================================

async def _simular_rastreio(
    solicitacao_id: str,
    pedido_id: str,
    correlation_id: str,
) -> None:
    """
    Simula a progressão do rastreio após a seleção do frete.

    Atualiza o campo status da tabela solicitacao_frete (sem DDL):
      - Após 10s: SELECIONADO → EM_TRANSITO
      - Após +20s: EM_TRANSITO → ENTREGUE

    Publica logs e eventos para cada transição de estado.
    """
    logger.info(
        "[RASTREIO] Iniciando simulação de rastreio para solicitação %s",
        solicitacao_id,
    )

    # --- Transição 1: SELECIONADO → EM_TRANSITO (10 segundos) ---
    await asyncio.sleep(10)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(SolicitacaoFrete).where(
                    SolicitacaoFrete.id == uuid.UUID(solicitacao_id)
                )
            )
            solicitacao = result.scalar_one_or_none()

            if solicitacao is None:
                logger.warning(
                    "[RASTREIO] Solicitação %s não encontrada. Rastreio abortado.",
                    solicitacao_id,
                )
                return

            solicitacao.status = "EM_TRANSITO"

    logger.info(
        "[RASTREIO] 🚚 Status atualizado: solicitação=%s → EM_TRANSITO",
        solicitacao_id,
    )

    # Publicar evento de transição para o Frontend acompanhar
    await publish_event(
        topic="logistica_status_atualizado",
        correlation_id=correlation_id,
        payload={
            "solicitacao_id": solicitacao_id,
            "pedido_id": pedido_id,
            "status_anterior": "SELECIONADO",
            "status_atual": "EM_TRANSITO",
        },
    )

    # --- Transição 2: EM_TRANSITO → ENTREGUE (20 segundos) ---
    await asyncio.sleep(20)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(SolicitacaoFrete).where(
                    SolicitacaoFrete.id == uuid.UUID(solicitacao_id)
                )
            )
            solicitacao = result.scalar_one_or_none()

            if solicitacao is None:
                logger.warning(
                    "[RASTREIO] Solicitação %s não encontrada. Rastreio abortado.",
                    solicitacao_id,
                )
                return

            solicitacao.status = "ENTREGUE"

    logger.info(
        "[RASTREIO] 📦 Status atualizado: solicitação=%s → ENTREGUE",
        solicitacao_id,
    )

    # Publicar evento de entrega finalizada
    await publish_event(
        topic="logistica_status_atualizado",
        correlation_id=correlation_id,
        payload={
            "solicitacao_id": solicitacao_id,
            "pedido_id": pedido_id,
            "status_anterior": "EM_TRANSITO",
            "status_atual": "ENTREGUE",
        },
    )

    logger.info(
        "[RASTREIO] ✅ Simulação de rastreio completa para solicitação %s. "
        "Fluxo finalizado: AGUARDANDO → SELECIONADO → EM_TRANSITO → ENTREGUE",
        solicitacao_id,
    )
