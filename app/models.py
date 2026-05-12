"""
models.py — Modelos SQLAlchemy mapeando as tabelas existentes no schema portal_b2b.

Tabelas criadas pela equipe de banco (DDL script 04-criacao_tabelas_principais.sql):
  - portal_b2b.solicitacao_frete
  - portal_b2b.cotacao_frete
  - portal_b2b.frete_selecionado

IMPORTANTE:
  - Estes modelos NÃO criam tabelas. Apenas mapeiam a estrutura existente.
  - Todos os IDs são UUID com server_default gen_random_uuid().
  - Todos os modelos apontam para schema "portal_b2b".
"""

import uuid
from datetime import datetime

# pyrefly: ignore [missing-import]
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    text,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import relationship

from app.database import Base

SCHEMA = "portal_b2b"


class Empresa(Base):
    """Mapeamento da tabela portal_b2b.empresa."""

    __tablename__ = "empresa"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class Perfil(Base):
    """Mapeamento da tabela portal_b2b.perfil."""

    __tablename__ = "perfil"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True)
    nome = Column(String(50), nullable=False, unique=True)


class EmpresaPerfil(Base):
    """Mapeamento da tabela portal_b2b.empresa_perfil."""

    __tablename__ = "empresa_perfil"
    __table_args__ = {"schema": SCHEMA}

    empresa_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.empresa.id"), primary_key=True)
    perfil_id = Column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.perfil.id"), primary_key=True)


class Pedido(Base):
    """Mapeamento da tabela portal_b2b.pedido."""

    __tablename__ = "pedido"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class SolicitacaoFrete(Base):
    """Mapeamento da tabela portal_b2b.solicitacao_frete."""

    __tablename__ = "solicitacao_frete"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    pedido_id = Column(UUID(as_uuid=True), nullable=False)
    tipo_transporte = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, server_default=text("'AGUARDANDO'"))
    data_criacao = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Relacionamento: uma solicitação tem N cotações
    cotacoes = relationship(
        "CotacaoFrete",
        back_populates="solicitacao",
        lazy="selectin",
    )


class CotacaoFrete(Base):
    """Mapeamento da tabela portal_b2b.cotacao_frete."""

    __tablename__ = "cotacao_frete"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    solicitacao_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.solicitacao_frete.id"),
        nullable=False,
    )
    transportadora_id = Column(UUID(as_uuid=True), nullable=False)
    valor = Column(Numeric(18, 4), nullable=False)
    prazo = Column(Integer, nullable=False)
    data_cotacao = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Relacionamento reverso para solicitação
    solicitacao = relationship(
        "SolicitacaoFrete",
        back_populates="cotacoes",
    )


class FreteSelecionado(Base):
    """Mapeamento da tabela portal_b2b.frete_selecionado."""

    __tablename__ = "frete_selecionado"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    pedido_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    cotacao_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.cotacao_frete.id"),
        nullable=False,
    )
    data_selecao = Column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Relacionamento: frete selecionado → cotação escolhida
    cotacao = relationship("CotacaoFrete", lazy="selectin")
