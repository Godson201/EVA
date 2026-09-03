from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def initialize_database(settings: Settings | None = None) -> AsyncEngine:
    global _engine, _session_factory
    config = settings or get_settings()
    if _engine is None:
        _engine = create_async_engine(config.database_url, echo=config.database_echo, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        initialize_database()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


async def close_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
