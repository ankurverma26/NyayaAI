"""Build (and cache) the process-wide retriever from the database."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.retrieval.index_builder import (
    build_or_update_index,
    get_default_embedder,
    load_sections_from_db,
)

logger = logging.getLogger(__name__)
_retriever: HybridRetriever | None = None
_lock = threading.Lock()  # concurrent requests must not build the retriever twice


def build_retriever(
    db_url: str | None = None,
    index_dir: Path | None = None,
    use_dense: bool = True,
    rebuild: bool = False,
    alpha: float = 0.5,
    embedder=None,
) -> HybridRetriever:
    records = load_sections_from_db(db_url)
    if not records:
        logger.warning("No sections found in DB. Run scripts/load_laws.py first.")
    dense_index = None
    if use_dense and records:
        try:
            embedder = embedder or get_default_embedder()
            dense_index, stats = build_or_update_index(records, embedder, index_dir, rebuild)
            logger.info("Index stats: %s", stats)
        except ImportError:
            logger.warning("sentence-transformers not installed; using BM25 only")
            dense_index, embedder = None, None
    return HybridRetriever(records, dense_index=dense_index, embedder=embedder, alpha=alpha)


def get_retriever() -> HybridRetriever:
    """Singleton used by the agent/API. Set USE_DENSE=false to force BM25-only."""
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                _retriever = build_retriever(use_dense=os.getenv("USE_DENSE", "true").lower() != "false")
    return _retriever


def reset_retriever() -> None:
    """Call after loading new laws so the next search rebuilds the index."""
    global _retriever
    with _lock:
        _retriever = None
