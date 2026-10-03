"""Hybrid retriever: BM25 + dense embeddings + citation/section-number boost."""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import asdict, dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi

from backend.retrieval.index_builder import DenseIndex, Embedder, SectionRecord
from backend.retrieval.query_expansion import ExpandedQuery, expand_query
from backend.retrieval.tokenizer import tokenize

MODES = ("hybrid", "bm25", "dense")


@dataclass(frozen=True)
class SearchResult:
    section_id: int
    citation: str            # e.g. "ICA1872 s.27"
    act: str
    section_number: str
    heading: str | None
    text: str
    status: str | None
    score: float             # final fused score
    bm25_score: float        # min-max normalized, 0..1
    dense_score: float       # min-max normalized, 0..1
    bm25_raw: float
    dense_raw: float         # raw cosine similarity (useful as a relevance floor)
    boosted: bool            # exact section-number / act-name boost applied
    contributed_by: list[str] = field(default_factory=list)  # bm25 | dense | citation_match

    def to_dict(self) -> dict:
        return asdict(self)


def _minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-12:
        return np.zeros_like(x, dtype=np.float64)
    return (x - lo) / (hi - lo)


class HybridRetriever:
    def __init__(
        self,
        records: list[SectionRecord],
        dense_index: DenseIndex | None = None,
        embedder: Embedder | None = None,
        alpha: float = 0.5,
        exact_boost: float = 1.0,
        act_boost: float = 0.15,
        cache_size: int = 256,
    ) -> None:
        self.records = list(records)
        self.dense_index = dense_index
        self.embedder = embedder
        self.alpha = alpha
        self.exact_boost = exact_boost
        self.act_boost = act_boost
        self._bm25 = BM25Okapi([tokenize(r.search_text) for r in self.records]) if self.records else None
        self._cache: OrderedDict[tuple, list[SearchResult]] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()  # cache is shared by agent worker threads

    @property
    def dense_available(self) -> bool:
        return bool(
            self.dense_index is not None
            and self.embedder is not None
            and self.dense_index.matrix.shape[0] > 0
        )

    # ── component scorers ──────────────────────────────────────────────────────
    def _bm25_raw(self, q: ExpandedQuery) -> np.ndarray:
        tokens = tokenize(q.original) + tokenize(" ".join(q.extra_terms))
        if not tokens or self._bm25 is None:
            return np.zeros(len(self.records))
        return np.asarray(self._bm25.get_scores(tokens), dtype=np.float64)

    def _dense_raw(self, q: ExpandedQuery) -> np.ndarray | None:
        if not self.dense_available:
            return None
        qvec = self.embedder.encode([q.dense_text])[0]  # type: ignore[union-attr]
        scores = self.dense_index.section_scores(qvec)  # type: ignore[union-attr]
        if not scores:
            return None
        floor = min(scores.values())
        return np.array([scores.get(r.section_id, floor) for r in self.records], dtype=np.float64)

    def _boost_mask(self, q: ExpandedQuery) -> tuple[np.ndarray, np.ndarray]:
        """(exact_mask, act_mask) over self.records."""
        n = len(self.records)
        exact = np.zeros(n, dtype=bool)
        act = np.zeros(n, dtype=bool)
        for i, r in enumerate(self.records):
            act_match = any(h in r.act_title.lower() for h in q.act_hints) if q.act_hints else True
            if q.section_refs and r.section_number.lower() in q.section_refs and act_match:
                exact[i] = True
            elif q.act_hints and not q.section_refs and act_match:
                act[i] = True
        return exact, act

    # ── public API ─────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 5, mode: str = "hybrid", alpha: float | None = None) -> list[SearchResult]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if not self.records or not query.strip():
            return []
        a = self.alpha if alpha is None else alpha
        key = (query, k, mode, a)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]

        q = expand_query(query)
        bm25_raw = self._bm25_raw(q)
        dense_raw = self._dense_raw(q)
        bm25_n = _minmax(bm25_raw)
        dense_n = _minmax(dense_raw) if dense_raw is not None else np.zeros(len(self.records))

        exact = act = np.zeros(len(self.records), dtype=bool)
        if mode == "bm25":
            fused = bm25_n
        elif mode == "dense":
            fused = dense_n if dense_raw is not None else np.zeros(len(self.records))
        else:
            if dense_raw is None:  # graceful fallback when embeddings are unavailable
                fused = bm25_n
            else:
                fused = a * dense_n + (1.0 - a) * bm25_n
            exact, act = self._boost_mask(q)
            fused = fused + self.exact_boost * exact + self.act_boost * act

        top_bm25 = set(np.argsort(-bm25_raw)[:k].tolist()) if bm25_raw.any() else set()
        top_dense = set(np.argsort(-dense_raw)[:k].tolist()) if dense_raw is not None else set()

        order = sorted(range(len(self.records)), key=lambda i: (-fused[i], self.records[i].section_id))
        results: list[SearchResult] = []
        for i in order:
            if fused[i] <= 0:
                continue
            r = self.records[i]
            who: list[str] = []
            if i in top_bm25:
                who.append("bm25")
            if i in top_dense:
                who.append("dense")
            if exact[i]:
                who.append("citation_match")
            results.append(
                SearchResult(
                    section_id=r.section_id,
                    citation=r.citation,
                    act=r.act_title,
                    section_number=r.section_number,
                    heading=r.heading,
                    text=r.text,
                    status=r.status,
                    score=float(fused[i]),
                    bm25_score=float(bm25_n[i]),
                    dense_score=float(dense_n[i]),
                    bm25_raw=float(bm25_raw[i]),
                    dense_raw=float(dense_raw[i]) if dense_raw is not None else 0.0,
                    boosted=bool(exact[i] or act[i]),
                    contributed_by=who,
                )
            )
            if len(results) >= k:
                break

        with self._lock:
            self._cache[key] = results
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return results
