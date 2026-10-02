"""
backend/database/init_db.py
───────────────────────────
Database initialisation helper — creates all tables if they do not exist.

This is an Alembic-free bootstrap suitable for a mini-project.
Run once at startup (called from backend/main.py lifespan) or directly:

    python -m backend.database.init_db
"""
from __future__ import annotations

import asyncio
import logging

from backend.database.models import Base
from backend.database.session import engine

logger = logging.getLogger(__name__)


from sqlalchemy import text


async def _migrate_columns(conn) -> None:
    """Add new optional columns if upgrading an existing SQLite database."""
    try:
        res = await conn.execute(text("PRAGMA table_info(legal_sources)"))
        cols = {row[1] for row in res.fetchall()}
        if cols and "retrieved_on" not in cols:
            await conn.execute(text("ALTER TABLE legal_sources ADD COLUMN retrieved_on VARCHAR(20)"))

        res = await conn.execute(text("PRAGMA table_info(sections)"))
        cols = {row[1] for row in res.fetchall()}
        if cols and "notes" not in cols:
            await conn.execute(text("ALTER TABLE sections ADD COLUMN notes TEXT"))
    except Exception as exc:
        logger.debug("Column migration check passed: %s", exc)


async def init_db() -> None:
    """
    Create all tables declared on Base.metadata and apply column additions.

    Safe to call on every startup — SQLAlchemy uses CREATE TABLE IF NOT EXISTS
    semantics so existing tables and data are never touched.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_columns(conn)
    logger.info("Database tables created / verified.")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    asyncio.run(init_db())
