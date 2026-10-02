"""Tests for hybrid retrieval.

Unit tests use a synthetic FIXTURE corpus and a fake embedder, so they run
without the embedding model. Integration tests at the bottom use your real
corpus + model and are skipped automatically if those are not available.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.retrieval.index_builder import (
    DenseIndex,
    SectionRecord,
    build_or_update_index,
    chunk_text,
)
from backend.retrieval.query_expansion import detect_act_hints, expand_query, extract_section_refs
from backend.retrieval.tokenizer import tokenize


# ── fixtures ───────────────────────────────────────────────────────────────────
def _rec(i, act, short, num, heading, text):
    return SectionRecord(i, 1, act, short, num, heading, text, "in_force")


FIXTURE = [
    _rec(1, "Fixture Contract Act", "FIX1", "27", "Fixture restraint heading",
         "FIXTURE TEXT alpha restraint of trade profession business void"),
    _rec(2, "Fixture Contract Act", "FIX1", "74", "Fixture penalty heading",
         "FIXTURE TEXT beta stipulated penalty compensation breach"),
    _rec(3, "Fixture Companies Act", "FIX2", "27", "Fixture shares heading",
         "FIXTURE TEXT gamma share capital company memorandum"),
    _rec(4, "Fixture Arbitration Act", "FIX3", "7", "Fixture arbitration heading",
         "FIXTURE TEXT delta arbitration agreement writing parties"),
]


class FakeEmbedder:
    """Deterministic bag-of-words hashing embedder (counts encode calls)."""
    name = "fake-embedder"

    def __init__(self):
        self.encoded = 0

    def encode(self, texts):
        self.encoded += len(texts)
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in tokenize(t):
                out[i, hash(tok) % 64] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


def _retriever(tmp_path, records=FIXTURE):
    emb = FakeEmbedder()
    idx, _ = build_or_update_index(records, emb, tmp_path)
    return HybridRetriever(records, idx, emb), emb


# ── tokenizer / query expansion ────────────────────────────────────────────────
def test_tokenizer_keeps_section_numbers():
    toks = tokenize("Section 27 and s.43A")
    assert "27" in toks and "43a" in toks and "section" in toks


def test_stemming_matches_variants():
    assert tokenize("damages") == tokenize("damage")
    assert tokenize("competing") == tokenize("compete")


@pytest.mark.parametrize("q,expected", [
    ("section 27", ["27"]),
    ("what is s.43A about", ["43a"]),
    ("sec. 73", ["73"]),
    ("sections 73 and 74", ["73", "74"]),
    ("years 3 of service", []),
])
def test_extract_section_refs(q, expected):
    assert extract_section_refs(q) == expected


def test_act_hints_and_expansion():
    assert detect_act_hints("section 27 of the Indian Contract Act") == ["contract"]
    eq = expand_query("is a non-compete valid")
    assert "restraint of trade" in eq.extra_terms


# ── retrieval ──────────────────────────────────────────────────────────────────
def test_bm25_mode_finds_text_match(tmp_path):
    r, _ = _retriever(tmp_path)
    res = r.search("arbitration agreement in writing", k=3, mode="bm25")
    assert res[0].section_number == "7"


def test_section_number_boost_ranks_first(tmp_path):
    r, _ = _retriever(tmp_path)
    res = r.search("section 74", k=3)
    assert res[0].citation == "FIX1 s.74" and res[0].boosted
    assert "citation_match" in res[0].contributed_by


def test_act_hint_limits_boost_to_named_act(tmp_path):
    r, _ = _retriever(tmp_path)
    res = r.search("section 27 of the companies act", k=3)
    assert res[0].citation == "FIX2 s.27"


def test_dense_only_mode_runs(tmp_path):
    r, _ = _retriever(tmp_path)
    assert r.search("penalty compensation", k=2, mode="dense")[0].section_number == "74"


def test_falls_back_to_bm25_without_dense():
    r = HybridRetriever(FIXTURE)  # no dense index
    assert r.search("arbitration agreement", k=1)[0].section_number == "7"


def test_cache_returns_same_object(tmp_path):
    r, _ = _retriever(tmp_path)
    assert r.search("penalty", k=2) is r.search("penalty", k=2)


# ── incremental indexing ───────────────────────────────────────────────────────
def test_incremental_update_only_embeds_changes(tmp_path):
    emb = FakeEmbedder()
    _, s1 = build_or_update_index(FIXTURE, emb, tmp_path)
    assert s1["embedded_sections"] == 4
    before = emb.encoded
    _, s2 = build_or_update_index(FIXTURE, emb, tmp_path)  # nothing changed
    assert s2["embedded_sections"] == 0 and emb.encoded == before
    changed = FIXTURE[:3] + [_rec(4, "Fixture Arbitration Act", "FIX3", "7", "h", "FIXTURE TEXT new words")]
    idx, s3 = build_or_update_index(changed + [_rec(5, "Fixture Act", "FIX4", "1", "h", "FIXTURE TEXT extra")], emb, tmp_path)
    assert s3["embedded_sections"] == 2 and s3["reused_sections"] == 3
    assert set(idx.row_section_ids) == {1, 2, 3, 4, 5}


def test_index_roundtrip(tmp_path):
    emb = FakeEmbedder()
    idx, _ = build_or_update_index(FIXTURE, emb, tmp_path)
    loaded = DenseIndex.load(tmp_path, emb.name)
    assert loaded.row_section_ids == idx.row_section_ids
    assert np.allclose(loaded.matrix, idx.matrix)
    assert DenseIndex.load(tmp_path, "other-model").matrix.shape[0] == 0


def test_chunking_overlaps_long_text():
    words = " ".join(f"w{i}" for i in range(400))
    chunks = chunk_text(words, max_words=180, overlap=30)
    assert len(chunks) >= 3 and all(len(c.split()) <= 180 for c in chunks)


# ── integration (real corpus + real model; auto-skipped if unavailable) ────────
ROOT = Path(__file__).resolve().parent.parent
_HAVE_ST = importlib.util.find_spec("sentence_transformers") is not None
_HAVE_DB = (ROOT / "data" / "nyaya.db").exists()


@pytest.fixture(scope="module")
def real():
    from backend.retrieval.factory import build_retriever
    return build_retriever()


def _need(real_ret, act_kw, num):
    if not any(act_kw in r.act_title.lower() and r.section_number.lower() == num for r in real_ret.records):
        pytest.skip(f"{act_kw} s.{num} not loaded in DB")


@pytest.mark.skipif(not (_HAVE_ST and _HAVE_DB), reason="needs sentence-transformers and data/nyaya.db")
@pytest.mark.parametrize("query,act_kw,num", [
    ("restraint of trade after employment", "contract", "27"),
    ("section 74 liquidated damages", "contract", "74"),
    ("arbitration agreement in writing", "arbitration", "7"),
])
def test_real_corpus_expected_top_hit(real, query, act_kw, num):
    _need(real, act_kw, num)
    top = real.search(query, k=1)[0]
    assert act_kw in top.act.lower() and top.section_number.lower() == num
