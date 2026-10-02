"""Load statute sections from the DB and build/update the dense embedding index.

- Embeddings come from a lazily loaded, singleton sentence-transformers model.
- Long sections are split into overlapping word chunks; a section's dense score
  is the best chunk score.
- The index is cached on disk (data/index/embeddings.npy + index_meta.json).
- Updates are incremental: only new or changed sections are re-embedded.
- BM25 is rebuilt in memory from the DB each start-up (milliseconds for a
  statute corpus), so it needs no disk cache.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_DIR = PROJECT_ROOT / "data" / "index"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ── Data record ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SectionRecord:
    """A statute section prepared for retrieval."""
    section_id: int
    source_id: int
    act_title: str
    short_name: str | None
    section_number: str
    heading: str | None
    text: str
    status: str | None = None

    @property
    def citation(self) -> str:
        """Display form, e.g. 'ICA1872 s.27'."""
        return f"{self.short_name or self.act_title} s.{self.section_number}"

    @property
    def header(self) -> str:
        return f"{self.act_title} section {self.section_number}. {self.heading or ''}".strip()

    @property
    def search_text(self) -> str:
        """Text used for BM25 (header carries act name + section number)."""
        return f"{self.header}. {self.text}"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.search_text.encode("utf-8")).hexdigest()

    def chunks(self, max_words: int = 180, overlap: int = 30) -> list[str]:
        """Chunks for embedding; each chunk is prefixed with the section header."""
        return [f"{self.header}: {c}" for c in chunk_text(self.text, max_words, overlap)] or [self.header]


def chunk_text(text: str, max_words: int = 180, overlap: int = 30) -> list[str]:
    """Split text into overlapping word windows (MiniLM truncates at ~256 tokens)."""
    words = text.split()
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]
    step = max(1, max_words - overlap)
    out: list[str] = []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + max_words]))
        if start + max_words >= len(words):
            break
    return out


# ── DB loading ─────────────────────────────────────────────────────────────────

def default_db_url() -> str:
    try:
        from backend.config import get_settings
        return get_settings().db_url
    except Exception:  # config shape may differ; fall back to env/default
        return os.getenv("DB_URL", "sqlite+aiosqlite:///./data/nyaya.db")


def _to_sync_url(url: str) -> str:
    return (
        url.replace("sqlite+aiosqlite", "sqlite")
        .replace("postgresql+asyncpg", "postgresql+psycopg2")
    )


def load_sections_from_db(db_url: str | None = None) -> list[SectionRecord]:
    """Read all non-placeholder sections (sync engine; the app itself uses async)."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from backend.database.models import LegalSource, Section

    engine = create_engine(_to_sync_url(db_url or default_db_url()))
    records: list[SectionRecord] = []
    try:
        with Session(engine) as session:
            rows = session.execute(
                select(Section, LegalSource)
                .join(LegalSource, Section.source_id == LegalSource.id)
                .order_by(LegalSource.id, Section.id)
            ).all()
            for sec, src in rows:
                if "PLACEHOLDER" in (sec.text or ""):
                    continue
                records.append(
                    SectionRecord(
                        section_id=sec.id,
                        source_id=src.id,
                        act_title=src.title,
                        short_name=src.short_name,
                        section_number=str(sec.section_number),
                        heading=sec.heading,
                        text=sec.text,
                        status=src.status,
                    )
                )
    finally:
        engine.dispose()
    return records


# ── Embedder ───────────────────────────────────────────────────────────────────

class Embedder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Lazy-loaded sentence-transformers wrapper (CPU, normalized vectors)."""

    def __init__(self, model_name: str | None = None) -> None:
        self.name = model_name or os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL)
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy import

            logger.info("Loading embedding model %s", self.name)
            self._model = SentenceTransformer(self.name, device="cpu")
        return self._model

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        vecs = self._load().encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vecs.astype(np.float32)


_default_embedder: SentenceTransformerEmbedder | None = None


def get_default_embedder() -> SentenceTransformerEmbedder:
    """Process-wide singleton so the model is loaded at most once."""
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = SentenceTransformerEmbedder()
    return _default_embedder


# ── Dense index ────────────────────────────────────────────────────────────────

class DenseIndex:
    """Chunk-level embedding matrix with per-section change tracking."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.row_section_ids: list[int] = []
        self.hashes: dict[int, str] = {}

    def update(self, records: list[SectionRecord], embedder: Embedder) -> dict[str, int]:
        """Embed only new/changed sections; reuse cached rows for the rest."""
        old_rows: dict[int, list[int]] = {}
        for idx, sid in enumerate(self.row_section_ids):
            old_rows.setdefault(sid, []).append(idx)

        texts: list[str] = []
        owners: list[int] = []
        changed = 0
        for r in records:
            if self.hashes.get(r.section_id) == r.content_hash and r.section_id in old_rows:
                continue
            changed += 1
            for chunk in r.chunks():
                texts.append(chunk)
                owners.append(r.section_id)

        fresh: dict[int, list[np.ndarray]] = {}
        if texts:
            vecs = embedder.encode(texts)
            for sid, vec in zip(owners, vecs):
                fresh.setdefault(sid, []).append(vec)

        parts: list[np.ndarray] = []
        ids: list[int] = []
        hashes: dict[int, str] = {}
        for r in records:
            if r.section_id in fresh:
                arr = np.vstack(fresh[r.section_id])
            else:
                arr = self.matrix[old_rows[r.section_id]]
            parts.append(arr)
            ids.extend([r.section_id] * arr.shape[0])
            hashes[r.section_id] = r.content_hash

        removed = len(set(old_rows) - {r.section_id for r in records})
        self.matrix = np.vstack(parts).astype(np.float32) if parts else np.zeros((0, 0), np.float32)
        self.row_section_ids = ids
        self.hashes = hashes
        return {
            "embedded_sections": changed,
            "reused_sections": len(records) - changed,
            "removed_sections": removed,
        }

    def section_scores(self, query_vec: np.ndarray) -> dict[int, float]:
        """Cosine similarity per section (best chunk). Vectors are L2-normalized."""
        if self.matrix.shape[0] == 0:
            return {}
        sims = self.matrix @ query_vec
        best: dict[int, float] = {}
        for sid, s in zip(self.row_section_ids, sims.tolist()):
            if s > best.get(sid, -1e9):
                best[sid] = s
        return best

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "embeddings.npy", self.matrix)
        meta = {
            "model": self.model_name,
            "row_section_ids": self.row_section_ids,
            "hashes": {str(k): v for k, v in self.hashes.items()},
        }
        (index_dir / "index_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, index_dir: Path, model_name: str) -> "DenseIndex":
        """Load cached index; return an empty one if missing or built with another model."""
        idx = cls(model_name)
        npy, meta_path = index_dir / "embeddings.npy", index_dir / "index_meta.json"
        if not (npy.exists() and meta_path.exists()):
            return idx
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("model") != model_name:
                logger.info("Embedding model changed; ignoring cached index")
                return idx
            matrix = np.load(npy)
            ids = [int(i) for i in meta["row_section_ids"]]
            if matrix.shape[0] != len(ids):
                return idx
            idx.matrix, idx.row_section_ids = matrix, ids
            idx.hashes = {int(k): v for k, v in meta["hashes"].items()}
        except Exception as exc:  # corrupt cache -> rebuild
            logger.warning("Could not load index cache (%s); rebuilding", exc)
            return cls(model_name)
        return idx


def build_or_update_index(
    records: list[SectionRecord],
    embedder: Embedder,
    index_dir: Path | None = None,
    rebuild: bool = False,
) -> tuple[DenseIndex, dict[str, int]]:
    """Load the cached index (unless rebuild), embed what changed, save, return."""
    index_dir = index_dir or DEFAULT_INDEX_DIR
    index = DenseIndex(embedder.name) if rebuild else DenseIndex.load(index_dir, embedder.name)
    stats = index.update(records, embedder)
    index.save(index_dir)
    logger.info("Dense index updated: %s", stats)
    return index, stats
