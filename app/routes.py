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

from app.database import AsyncSessionLocal, get_db
from app.kafka_handler import (
    TOPIC_COTACAO_ENVIADA,
    TOPIC_FRETE_CONTRATADO,
    TOPIC_SOLICITACAO_CRIADA,
    publish_event,
    _simular_rastreio,
)
from app.models import CotacaoFrete, Empresa, EmpresaPerfil, FreteSelecionado, Pedido, Perfil, SolicitacaoFrete
from app.schemas import (
    ContratarFreteRequest,
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

    if not dados.pedido_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pedido_id é obrigatório."
        )

    pedido_id = dados.pedido_id

    # 1. Gravar solicitação no banco
    solicitacao = SolicitacaoFrete(
        pedido_id=pedido_id,
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
    # 0. Buscar transportadoras reais no banco
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Empresa).join(EmpresaPerfil).join(Perfil)
            .where(Perfil.nome == 'TRANSPORTADORA').limit(3)
        )
        transportadoras_reais = result.scalars().all()
        
        t_ids = [str(t.id) for t in transportadoras_reais]
        
        # Fallback caso o banco não retorne nenhuma
        if not t_ids:
            t_ids = ["b32bd9f2-6122-4c84-b721-b284aec606e1"]

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
    for i, transportadora in enumerate(_TRANSPORTADORAS_DEMO):
        # Distribui os IDs disponíveis. Se houver menos que 3, repete usando o resto da divisão.
        t_id_atual = t_ids[i % len(t_ids)]
        
        cotacoes_simuladas.append({
            "transportadora_id": t_id_atual,
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
    "/demo-iniciar-cotacao",
    response_model=SolicitacaoFreteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Demo"],
    summary="Demo Etapa 1: Iniciar cotação de frete",
    description=(
        "Etapa 1 do novo fluxo descentralizado.\n\n"
        "Cria uma solicitação, gera 3 cotações de transportadoras reais "
        "e **para em status `COTADO`**.\n\n"
        "O operador deve escolher uma cotação e confirmar via `POST /demo-contratar-frete`."
    ),
)
async def demo_iniciar_cotacao(
    dados: SolicitacaoFreteCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Cria solicitação de frete, gera 3 cotações e aguarda seleção manual.
    """
    correlation_id = str(uuid.uuid4())

    if not dados.pedido_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="pedido_id é obrigatório."
        )

    pedido_id = dados.pedido_id

    # 0. Triagem automática de veículo por peso
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

    # 1. Gravar solicitação
    solicitacao = SolicitacaoFrete(
        pedido_id=pedido_id,
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
    if dados.cep_origem:
        payload["cep_origem"] = dados.cep_origem
    if dados.cep_destino:
        payload["cep_destino"] = dados.cep_destino
    if dados.peso_carga is not None:
        payload["peso_carga"] = str(dados.peso_carga)

    await publish_event(
        topic=TOPIC_SOLICITACAO_CRIADA,
        payload=payload,
        correlation_id=correlation_id,
    )

    # 3. Disparar geração das 3 cotações em background e marcar como COTADO
    background_tasks.add_task(
        _simular_cotacoes_e_parar,
        solicitacao_id=str(solicitacao.id),
        correlation_id=correlation_id,
        tipo_veiculo=tipo_veiculo_final,
    )

    return solicitacao


async def _simular_cotacoes_e_parar(
    solicitacao_id: str,
    correlation_id: str,
    tipo_veiculo: str | None = None,
) -> None:
    """
    Gera 3 cotações, grava no banco, atualiza status para COTADO e **para**.
    Não seleciona automaticamente — aguarda decisão explícita via /demo-contratar-frete.
    """
    await _simular_cotacoes_background(
        solicitacao_id=solicitacao_id,
        correlation_id=correlation_id,
        tipo_veiculo=tipo_veiculo,
    )
    # Após gerar as cotações, aguardar o consumer processar e atualizar status para COTADO
    await asyncio.sleep(4)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(SolicitacaoFrete).where(
                    SolicitacaoFrete.id == uuid.UUID(solicitacao_id)
                )
            )
            sol = result.scalar_one_or_none()
            if sol and sol.status == "AGUARDANDO":
                sol.status = "COTADO"
                logger.info(
                    "[DEMO] Status atualizado para COTADO: solicitacao=%s", solicitacao_id
                )


@router.post(
    "/demo-contratar-frete",
    response_model=SolicitacaoFreteResponse,
    tags=["Demo"],
    summary="Demo Etapa 2: Confirmar contratação de frete",
    description=(
        "Etapa 2 do novo fluxo descentralizado.\n\n"
        "Recebe a cotação escolhida pelo operador, grava o `frete_selecionado` "
        "no banco e inicia a simulação de rastreio (`SELECIONADO` → `EM_TRANSITO` → `ENTREGUE`)."
    ),
)
async def demo_contratar_frete(
    dados: ContratarFreteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Registra a cotação escolhida e inicia o rastreio simulado."""
    correlation_id = str(uuid.uuid4())

    # 1. Buscar solicitação
    result = await db.execute(
        select(SolicitacaoFrete).where(SolicitacaoFrete.id == dados.solicitacao_id)
    )
    solicitacao = result.scalar_one_or_none()
    if solicitacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solicitação {dados.solicitacao_id} não encontrada.",
        )

    if solicitacao.status not in ("AGUARDANDO", "COTADO"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Solicitação já processada (status atual: {solicitacao.status}).",
        )

    # 2. Verificar se a cotação pertence a esta solicitação
    result = await db.execute(
        select(CotacaoFrete).where(
            CotacaoFrete.id == dados.cotacao_id,
            CotacaoFrete.solicitacao_id == dados.solicitacao_id,
        )
    )
    cotacao = result.scalar_one_or_none()
    if cotacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cotação {dados.cotacao_id} não encontrada para esta solicitação.",
        )

    # 3. Verificar duplicidade
    result = await db.execute(
        select(FreteSelecionado).where(
            FreteSelecionado.pedido_id == solicitacao.pedido_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este pedido já possui um frete contratado.",
        )

    # 4. Gravar frete selecionado e atualizar status
    frete = FreteSelecionado(
        pedido_id=solicitacao.pedido_id,
        cotacao_id=cotacao.id,
    )
    db.add(frete)
    solicitacao.status = "SELECIONADO"
    await db.commit()
    await db.refresh(solicitacao)

    logger.info(
        "[DEMO] Frete contratado: pedido=%s cotacao=%s valor=%s",
        solicitacao.pedido_id, cotacao.id, cotacao.valor,
    )

    # 5. Publicar evento frete_contratado no Kafka (para integração real com Demandas)
    await publish_event(
        topic=TOPIC_FRETE_CONTRATADO,
        correlation_id=correlation_id,
        payload={
            "pedido_id": str(solicitacao.pedido_id),
            "solicitacao_id": str(solicitacao.id),
            "cotacao_id": str(cotacao.id),
            "transportadora_id": str(cotacao.transportadora_id),
            "valor": str(cotacao.valor),
            "prazo": cotacao.prazo,
        },
    )

    # 6. Disparar rastreio em background (não bloqueia a resposta HTTP)
    asyncio.create_task(
        _simular_rastreio(
            solicitacao_id=str(solicitacao.id),
            pedido_id=str(solicitacao.pedido_id),
            correlation_id=correlation_id,
        )
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
