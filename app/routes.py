"""
routes.py — Rotas REST do logistica-service.

Rotas internas simples (sem prefixo /api/logistica/), pois o Gateway cuida disso.
"""

import asyncio
import logging
import random
import uuid
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.kafka_handler import (
    TOPIC_COTACAO_ENVIADA,
    TOPIC_SOLICITACAO_CRIADA,
    publish_event,
)
from app.models import CotacaoFrete, FreteSelecionado, SolicitacaoFrete
from app.schemas import (
    CotacaoFreteResponse,
    FreteSelecionadoResponse,
    HealthResponse,
    SolicitacaoFreteCreate,
    SolicitacaoFreteResponse,
    SolicitacaoFreteResumo,
)

logger = logging.getLogger("logistica-service.routes")

router = APIRouter()


# ============================================================
# Health Check
# ============================================================

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check do serviço.

    Retorna status 'ok' conforme contrato obrigatório do Portal B2B.
    """
    return HealthResponse()


# ============================================================
# Simulação de Recebimento (Vendas)
# ============================================================

@router.post(
    "/solicitar-externo",
    response_model=SolicitacaoFreteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Solicitações"],
    summary="Simular recebimento de pedido de frete",
    description=(
        "Endpoint de simulação (mock) para testar o fluxo. "
        "Simula o recebimento de um pedido_criado da Equipe de Vendas. "
        "Grava a solicitação no banco e publica solicitacao_frete_criada no Kafka."
    ),
)
async def solicitar_frete_externo(
    dados: SolicitacaoFreteCreate,
    db: AsyncSession = Depends(get_db),
):
    """Cria uma solicitação de frete e publica evento no Kafka."""
    correlation_id = str(uuid.uuid4())

    # 1. Gravar solicitação no banco
    solicitacao = SolicitacaoFrete(
        pedido_id=dados.pedido_id,
        tipo_transporte=dados.tipo_transporte,
        status="AGUARDANDO",
    )
    db.add(solicitacao)
    await db.commit()
    await db.refresh(solicitacao)

    logger.info(
        "Solicitação de frete criada: id=%s pedido_id=%s",
        solicitacao.id,
        solicitacao.pedido_id,
    )

    # 2. Publicar evento solicitacao_frete_criada no Kafka
    payload = {
        "solicitacao_id": str(solicitacao.id),
        "pedido_id": str(solicitacao.pedido_id),
        "tipo_transporte": solicitacao.tipo_transporte,
    }

    # Incluir campos extras no payload Kafka (não persistidos no banco)
    if dados.tipo_veiculo:
        payload["tipo_veiculo"] = dados.tipo_veiculo
    if dados.tipo_carga:
        payload["tipo_carga"] = dados.tipo_carga
    if dados.cep_origem:
        payload["cep_origem"] = dados.cep_origem
    if dados.cep_destino:
        payload["cep_destino"] = dados.cep_destino

    await publish_event(
        topic=TOPIC_SOLICITACAO_CRIADA,
        payload=payload,
        correlation_id=correlation_id,
    )

    return solicitacao


# ============================================================
# Demo: Fluxo Completo com Cotações Simuladas
# ============================================================

# Transportadoras simuladas (IDs fixos para facilitar identificação na demo)
_TRANSPORTADORAS_DEMO = [
    {"id": "aaa11111-1111-1111-1111-111111111111", "nome": "TransLog Express"},
    {"id": "bbb22222-2222-2222-2222-222222222222", "nome": "Rodo Frete Brasil"},
    {"id": "ccc33333-3333-3333-3333-333333333333", "nome": "CargoVia Sul"},
]


# ============================================================
# Mapeamento automático de veículo por peso (regras BR)
# ============================================================

# Faixas de preço simulado por tipo de veículo (min, max em R$)
_FAIXAS_PRECO_VEICULO = {
    "FURGAO":                   (350.00,  900.00),
    "CAMINHAO_3_4":             (800.00,  1800.00),
    "CAMINHAO_BAU_NORMAL":      (1500.00, 3500.00),
    "CAMINHAO_BAU_FRIGORIFICO": (2200.00, 4500.00),
    "CAMINHAO_SIDER":           (1800.00, 3800.00),
}

# Faixas de prazo simulado por tipo de veículo (min, max em dias)
_FAIXAS_PRAZO_VEICULO = {
    "FURGAO":                   (1, 4),
    "CAMINHAO_3_4":             (2, 7),
    "CAMINHAO_BAU_NORMAL":      (3, 10),
    "CAMINHAO_BAU_FRIGORIFICO": (2, 6),
    "CAMINHAO_SIDER":           (3, 10),
}


def selecionar_veiculo_por_peso(
    peso_carga: Decimal | None,
    tipo_carga_natureza: str | None = None,
) -> str | None:
    """
    Seleciona automaticamente o tipo de veículo com base no peso da carga.

    Regras de negócio (logística brasileira):
      - Até 1.500 kg:           FURGAO (entregas urbanas / cargas leves)
      - 1.501 kg a 4.000 kg:   CAMINHAO_3_4 (distribuição regional)
      - Acima de 4.000 kg:
          - Perecível:          CAMINHAO_BAU_FRIGORIFICO
          - Carga lateral:      CAMINHAO_SIDER (lonado)
          - Seca geral:        CAMINHAO_BAU_NORMAL

    Args:
        peso_carga: Peso total da carga em kg. Se None, retorna None.
        tipo_carga_natureza: Natureza da carga (PERECIVEL, CARGA_LATERAL, SECA_GERAL).
                             Relevante apenas para cargas acima de 4.000 kg.

    Returns:
        Código do tipo de veículo ou None se peso_carga não informado.
    """
    if peso_carga is None:
        return None

    peso = Decimal(str(peso_carga))

    # Porte Pequeno
    if peso <= Decimal("1500"):
        return "FURGAO"

    # Porte Médio
    if peso <= Decimal("4000"):
        return "CAMINHAO_3_4"

    # Porte Grande — subdivisão por natureza da carga
    natureza = (tipo_carga_natureza or "SECA_GERAL").upper().strip()

    if natureza == "PERECIVEL":
        return "CAMINHAO_BAU_FRIGORIFICO"
    elif natureza == "CARGA_LATERAL":
        return "CAMINHAO_SIDER"
    else:
        return "CAMINHAO_BAU_NORMAL"


async def _simular_cotacoes_background(
    solicitacao_id: str,
    correlation_id: str,
    tipo_veiculo: str | None = None,
) -> None:
    """
    Background task que simula 3 cotações de transportadoras diferentes.

    Se tipo_veiculo for informado, gera valores coerentes com o porte do veículo.
    Caso contrário, gera valores aleatórios entre R$ 500 e R$ 2.000.
    Publica no tópico cotacao_frete_enviada com o envelope oficial,
    fazendo o consumer existente processar cada uma normalmente.
    """
    # Determinar faixas de preço e prazo
    if tipo_veiculo and tipo_veiculo in _FAIXAS_PRECO_VEICULO:
        preco_min, preco_max = _FAIXAS_PRECO_VEICULO[tipo_veiculo]
        prazo_min, prazo_max = _FAIXAS_PRAZO_VEICULO[tipo_veiculo]
        logger.info(
            "[DEMO] Cotações calibradas para veículo %s (R$%.0f–R$%.0f, %d–%d dias)",
            tipo_veiculo, preco_min, preco_max, prazo_min, prazo_max,
        )
    else:
        preco_min, preco_max = 500.00, 2000.00
        prazo_min, prazo_max = 2, 15

    # Gerar cotações com valores baseados no porte do veículo
    cotacoes_simuladas = []
    for transportadora in _TRANSPORTADORAS_DEMO:
        cotacoes_simuladas.append({
            "transportadora_id": transportadora["id"],
            "nome": transportadora["nome"],
            "valor": round(random.uniform(preco_min, preco_max), 2),
            "prazo": random.randint(prazo_min, prazo_max),
        })

    # Log resumo das cotações geradas
    menor = min(cotacoes_simuladas, key=lambda c: c["valor"])
    logger.info(
        "[DEMO] Cotações geradas — valores: %s | Menor: %s (R$ %.2f)",
        [f'R${c["valor"]:.2f}' for c in cotacoes_simuladas],
        menor["nome"],
        menor["valor"],
    )

    # Aguarda para garantir que a solicitação foi commitada no banco
    # e que o consumer está pronto para processar
    await asyncio.sleep(2)

    for i, cotacao in enumerate(cotacoes_simuladas, 1):
        logger.info(
            "[DEMO] Publicando cotação simulada %d/3: transportadora=%s valor=R$%.2f prazo=%d dias",
            i,
            cotacao["nome"],
            cotacao["valor"],
            cotacao["prazo"],
        )

        await publish_event(
            topic=TOPIC_COTACAO_ENVIADA,
            correlation_id=correlation_id,
            payload={
                "solicitacao_id": solicitacao_id,
                "transportadora_id": cotacao["transportadora_id"],
                "valor": cotacao["valor"],
                "prazo": cotacao["prazo"],
            },
        )

        # Intervalo entre cotações para simular chegada escalonada
        await asyncio.sleep(1)

    logger.info(
        "[DEMO] Todas as 3 cotações simuladas publicadas para solicitação %s. "
        "Aguardando consumer processar e selecionar a melhor.",
        solicitacao_id,
    )


@router.post(
    "/demo-fluxo-completo",
    response_model=SolicitacaoFreteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Demo"],
    summary="Demo: fluxo completo com rastreio simulado",
    description=(
        "Endpoint de demonstração para apresentação em aula.\n\n"
        "Executa o **fluxo completo** automaticamente, percorrendo todos os estados:\n\n"
        "| Tempo | Estado | Ação |\n"
        "|-------|--------|------|\n"
        "| 0s | `AGUARDANDO` | Solicitação criada + evento `solicitacao_frete_criada` |\n"
        "| ~2s | — | 3 cotações simuladas publicadas (valores aleatórios R$500–R$2000) |\n"
        "| ~5s | `SELECIONADO` | Consumer seleciona menor valor + evento `frete_selecionado` |\n"
        "| ~15s | `EM_TRANSITO` | Simulação de despacho da carga |\n"
        "| ~35s | `ENTREGUE` | Simulação de entrega finalizada |\n\n"
        "**Acompanhe em tempo real** via polling em `GET /solicitacoes/{id}`."
    ),
)
async def demo_fluxo_completo(
    dados: SolicitacaoFreteCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Cria solicitação de frete e dispara cotações simuladas automaticamente.

    O fluxo completo é executado em ~35 segundos:
      - Solicitação gravada e evento publicado imediatamente
      - 3 cotações simuladas com valores aleatórios (R$500-R$2000)
      - Consumer processa e seleciona a mais barata
      - Rastreio simulado: EM_TRANSITO (5s) → ENTREGUE (10s)
    """
    correlation_id = str(uuid.uuid4())

    # 0. Triagem automática de veículo por peso (regras BR)
    tipo_veiculo_final = dados.tipo_veiculo
    if dados.peso_carga is not None and not dados.tipo_veiculo:
        tipo_veiculo_final = selecionar_veiculo_por_peso(
            peso_carga=dados.peso_carga,
            tipo_carga_natureza=dados.tipo_carga_natureza,
        )
        logger.info(
            "[DEMO] Triagem automática: peso=%.1f kg → veículo=%s",
            dados.peso_carga,
            tipo_veiculo_final,
        )

    # 1. Gravar solicitação no banco (idêntico ao /solicitar-externo)
    solicitacao = SolicitacaoFrete(
        pedido_id=dados.pedido_id,
        tipo_transporte=dados.tipo_transporte,
        status="AGUARDANDO",
    )
    db.add(solicitacao)
    await db.commit()
    await db.refresh(solicitacao)

    logger.info(
        "[DEMO] Solicitação criada: id=%s pedido_id=%s",
        solicitacao.id,
        solicitacao.pedido_id,
    )

    # 2. Publicar evento solicitacao_frete_criada
    payload = {
        "solicitacao_id": str(solicitacao.id),
        "pedido_id": str(solicitacao.pedido_id),
        "tipo_transporte": solicitacao.tipo_transporte,
    }
    if tipo_veiculo_final:
        payload["tipo_veiculo"] = tipo_veiculo_final
    if dados.tipo_carga:
        payload["tipo_carga"] = dados.tipo_carga
    if dados.cep_origem:
        payload["cep_origem"] = dados.cep_origem
    if dados.cep_destino:
        payload["cep_destino"] = dados.cep_destino
    if dados.peso_carga is not None:
        payload["peso_carga"] = str(dados.peso_carga)
    if dados.tipo_carga_natureza:
        payload["tipo_carga_natureza"] = dados.tipo_carga_natureza

    await publish_event(
        topic=TOPIC_SOLICITACAO_CRIADA,
        payload=payload,
        correlation_id=correlation_id,
    )

    # 3. Disparar cotações simuladas em background
    #    Isso acontece APÓS a resposta HTTP ser enviada ao cliente
    background_tasks.add_task(
        _simular_cotacoes_background,
        solicitacao_id=str(solicitacao.id),
        correlation_id=correlation_id,
        tipo_veiculo=tipo_veiculo_final,
    )

    logger.info(
        "[DEMO] Resposta enviada. Cotações simuladas serão publicadas em ~2s. "
        "Veículo: %s",
        tipo_veiculo_final or "(não especificado)",
    )

    return solicitacao


# ============================================================
# Listagem de Solicitações
# ============================================================

@router.get(
    "/solicitacoes",
    response_model=list[SolicitacaoFreteResumo],
    tags=["Solicitações"],
    summary="Listar todas as solicitações de frete",
)
async def listar_solicitacoes(db: AsyncSession = Depends(get_db)):
    """Retorna lista resumida de todas as solicitações de frete."""
    result = await db.execute(
        select(SolicitacaoFrete).order_by(SolicitacaoFrete.data_criacao.desc())
    )
    return result.scalars().all()


@router.get(
    "/solicitacoes/{solicitacao_id}",
    response_model=SolicitacaoFreteResponse,
    tags=["Solicitações"],
    summary="Detalhe de uma solicitação de frete",
)
async def detalhar_solicitacao(
    solicitacao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna o detalhe de uma solicitação com cotações e frete selecionado."""
    result = await db.execute(
        select(SolicitacaoFrete)
        .options(
            selectinload(SolicitacaoFrete.cotacoes),
        )
        .where(SolicitacaoFrete.id == solicitacao_id)
    )
    solicitacao = result.scalar_one_or_none()

    if solicitacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solicitação {solicitacao_id} não encontrada.",
        )

    # Buscar frete selecionado via query explícita (não há FK direta entre as tabelas)
    frete_result = await db.execute(
        select(FreteSelecionado)
        .options(selectinload(FreteSelecionado.cotacao))
        .where(FreteSelecionado.pedido_id == solicitacao.pedido_id)
    )
    frete_selecionado = frete_result.scalar_one_or_none()

    # Montar resposta manualmente incluindo o frete selecionado
    return SolicitacaoFreteResponse(
        id=solicitacao.id,
        pedido_id=solicitacao.pedido_id,
        tipo_transporte=solicitacao.tipo_transporte,
        status=solicitacao.status,
        data_criacao=solicitacao.data_criacao,
        cotacoes=solicitacao.cotacoes,
        frete_selecionado=frete_selecionado,
    )


# ============================================================
# Listagem de Fretes Selecionados
# ============================================================

@router.get(
    "/fretes-selecionados",
    response_model=list[FreteSelecionadoResponse],
    tags=["Fretes Selecionados"],
    summary="Listar todos os fretes selecionados",
)
async def listar_fretes_selecionados(db: AsyncSession = Depends(get_db)):
    """Retorna lista de todos os fretes selecionados (menor cotação)."""
    result = await db.execute(
        select(FreteSelecionado)
        .options(selectinload(FreteSelecionado.cotacao))
        .order_by(FreteSelecionado.data_selecao.desc())
    )
    return result.scalars().all()


# ============================================================
# Listagem de Cotações por Solicitação
# ============================================================

@router.get(
    "/solicitacoes/{solicitacao_id}/cotacoes",
    response_model=list[CotacaoFreteResponse],
    tags=["Cotações"],
    summary="Listar cotações de uma solicitação",
)
async def listar_cotacoes(
    solicitacao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna todas as cotações recebidas para uma solicitação de frete."""
    # Verificar se a solicitação existe
    result = await db.execute(
        select(SolicitacaoFrete).where(SolicitacaoFrete.id == solicitacao_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solicitação {solicitacao_id} não encontrada.",
        )

    result = await db.execute(
        select(CotacaoFrete)
        .where(CotacaoFrete.solicitacao_id == solicitacao_id)
        .order_by(CotacaoFrete.valor.asc())
    )
    return result.scalars().all()
