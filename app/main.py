"""
main.py — Entrypoint do logistica-service.

Inicializa o FastAPI com:
  - Lifespan handler para gerenciar Kafka producer/consumer
  - Router com todas as rotas
  - Swagger/OpenAPI em /docs
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.kafka_handler import (
    consume_loop,
    start_consumer,
    start_producer,
    stop_consumer,
    stop_producer,
)
from app.routes import router

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("logistica-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida do serviço.

    Startup: inicia Kafka producer e consumer.
    Shutdown: encerra Kafka producer e consumer.
    """
    logger.info("=== logistica-service iniciando ===")

    # Iniciar Kafka producer
    await start_producer()

    # Iniciar Kafka consumer e rodar loop em background
    await start_consumer()
    consumer_task = asyncio.create_task(consume_loop())

    logger.info("=== logistica-service pronto na porta 5008 ===")

    yield

    # Shutdown
    logger.info("=== logistica-service encerrando ===")
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await stop_consumer()
    await stop_producer()
    logger.info("=== logistica-service encerrado ===")


app = FastAPI(
    title="Logística Service — Portal B2B",
    description=(
        "Microsserviço de Logística (Equipe 8) do Portal B2B.\n\n"
        "Responsável por:\n"
        "- Receber solicitações de frete (simulação de pedido de vendas)\n"
        "- Publicar evento solicitacao_frete_criada no Kafka\n"
        "- Consumir cotacoes de transportadoras (cotacao_frete_enviada)\n"
        "- Selecionar a melhor cotação (menor valor)\n"
        "- Publicar evento frete_selecionado no Kafka"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5008,
        reload=False,
    )
