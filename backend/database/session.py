"""
backend/database/session.py
───────────────────────────
Async SQLAlchemy engine, session factory, and FastAPI dependency.

Usage in a route:
    async def my_route(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Contract))
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings

_settings = get_settings()

# ── Engine (singleton) ────────────────────────────────────────────────────────
# `check_same_thread=False` is required for SQLite with async;
# `echo=False` in production — flip to True for SQL debug output.
engine: AsyncEngine = create_async_engine(
    _settings.db_url,
    connect_args={"check_same_thread": False}
    if "sqlite" in _settings.db_url
    else {},
    echo=False,
)

# ── Session factory ────────────────────────────────────────────────────────────
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # objects remain accessible after commit
    autoflush=False,
    autocommit=False,
)


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async session per request, rolling back on error and
    always closing the session on exit.

    Example::

        @router.get("/contracts")
        async def list_contracts(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias for dependency injection convenience
get_session = get_db

