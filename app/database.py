"""
database.py — Configuração do SQLAlchemy Async para o logistica-service.

Conecta ao PostgreSQL centralizado usando o usuário svc_portal_b2b (DML only).
NÃO realiza DDL (CREATE/ALTER/DROP). As tabelas são geridas exclusivamente pela equipe de BD.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Leitura da DATABASE_URL do .env
# Padrão oficial: postgresql://svc_portal_b2b:senha@136.114.235.212:5432/portal_b2b
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://svc_portal_b2b:senha_portal_b2b@136.114.235.212:5432/portal_b2b",
)

# Garante que o driver é asyncpg (substitui 'postgresql://' por 'postgresql+asyncpg://')
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

DB_SCHEMA = os.getenv("DB_SCHEMA", "portal_b2b")

# ---------------------------------------------------------------------------
# Engine — search_path aponta para o schema portal_b2b
# ---------------------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # detecta conexões mortas antes de usar
    connect_args={"server_settings": {"search_path": DB_SCHEMA}},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Base declarativa — APENAS para mapeamento, NUNCA para DDL
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    Base declarativa para os modelos.

    REGRA INEGOCIÁVEL: NÃO usar Base.metadata.create_all() nem drop_all().
    O microsserviço só faz DML (SELECT, INSERT, UPDATE, DELETE).
    """
    pass


# ---------------------------------------------------------------------------
# Dependency FastAPI para injeção de sessão
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency do FastAPI para injeção de sessão assíncrona."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
