"""
backend/main.py
───────────────
FastAPI application entry point for NyayaAI.

Responsibilities:
- Create the FastAPI app with metadata for OpenAPI docs.
- Configure CORS for the React dev server.
- Mount sub-routers (added incrementally in future tasks).
- Expose /health for liveness checks.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.contracts import router as contracts_router
from backend.api.statutes import router as statutes_router
from backend.config import get_settings
from backend.database.init_db import init_db

# ── Logging ────────────────────────────────────────────────────────────────────
settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown hooks) ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup tasks before yield, teardown tasks after."""
    logger.info("NyayaAI backend starting up …")
    logger.info("USE_LLM=%s | EMBED_MODEL=%s", settings.use_llm, settings.embed_model)
    await init_db()
    yield
    logger.info("NyayaAI backend shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NyayaAI — Indian Legal Reasoning & Contract Intelligence",
    description=(
        "Agentic RAG platform for Indian law. "
        "Ingests contracts, retrieves relevant statutes via hybrid BM25 + "
        "semantic search, applies a rule-based risk engine, and orchestrates "
        "analysis through a LangGraph workflow."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Liveness check",
    response_description="Service status and active configuration",
)
async def health() -> dict:
    """
    Returns 200 with basic service metadata.

    Safe to call without authentication — used by monitoring and the
    React frontend to confirm the backend is reachable.
    """
    return {
        "status": "ok",
        "service": "NyayaAI",
        "version": app.version,
        "use_llm": settings.use_llm,
        "embed_model": settings.embed_model,
    }


# ── Sub-routers ────────────────────────────────────────────────────────────────
app.include_router(contracts_router)
app.include_router(statutes_router)

