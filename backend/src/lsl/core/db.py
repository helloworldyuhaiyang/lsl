from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session as OrmSession, sessionmaker

from lsl.core.config import Settings

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool
    from sqlalchemy.engine import Engine


class Base(DeclarativeBase):
    pass


@dataclass(slots=True)
class DatabaseResources:
    pool: ConnectionPool | None = None
    engine: Engine | None = None
    session_factory: sessionmaker[OrmSession] | None = None


def to_sqlalchemy_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+"):
        return database_url
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


def create_database_resources(settings: Settings) -> DatabaseResources:
    if not settings.DATABASE_URL:
        return DatabaseResources()

    try:
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise RuntimeError(
            "psycopg_pool is required. Run: uv pip install psycopg-pool"
        ) from exc

    connect_pool = ConnectionPool(
        conninfo=settings.DATABASE_URL,
        min_size=settings.DB_POOL_MIN_SIZE,
        max_size=settings.DB_POOL_MAX_SIZE,
        timeout=settings.DB_POOL_TIMEOUT,
        open=False,
    )
    connect_pool.open(wait=True)

    engine = create_engine(
        to_sqlalchemy_database_url(settings.DATABASE_URL),
        pool_pre_ping=True,
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return DatabaseResources(
        pool=connect_pool,
        engine=engine,
        session_factory=session_factory,
    )


def close_database_resources(resources: DatabaseResources) -> None:
    if resources.pool is not None:
        resources.pool.close()
    if resources.engine is not None:
        resources.engine.dispose()
