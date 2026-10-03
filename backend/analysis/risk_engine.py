"""Rule-based risk engine with retrieval-backed evidence.

Pure Python (no DB access) so it is easy to test. For every clause it:
  1. classifies the clause (multi-label),
  2. applies data-driven rules from risk_rules.json,
  3. attaches evidence: a VERBATIM quote from a statute section stored in the DB
     (found by the hybrid retriever, or looked up from the rule's mapped section),
  4. adds "missing clause" findings at contract level.

Wording is deliberately cautious ("potential issue", "requires review").
If a mapped statute section is not in the loaded corpus the finding says
"Source verification required." and carries no evidence.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from backend.analysis.clause_classifier import classify_clause
from backend.retrieval.tokenizer import tokenize

RULES_PATH = Path(__file__).with_name("risk_rules.json")
DISCLAIMER = (
    "This platform provides legal information and document analysis for research and "
    "educational purposes. It is not a substitute for advice from a qualified legal professional."
)
LEVEL_ORDER = {"high": 3, "medium": 2, "low": 1, "info": 0}
SOURCE_VERIFICATION_REQUIRED = "source_verification_required"


# ── data classes ───────────────────────────────────────────────────────────────
@dataclass
class ClauseInput:
    clause_number: int
    text: str
    heading: Optional[str] = None
    clause_label: Optional[str] = None
    clause_id: Optional[int] = None
    clause_types: Optional[list[str]] = None


@dataclass
class FindingDraft:
    rule_id: str
    risk_level: str                 # high | medium | low | info
    category: str
    title: str
    reason: str
    recommendation: str
    clause_number: Optional[int] = None      # None for contract-level (missing clause)
    clause_id: Optional[int] = None
    clause_label: Optional[str] = None
    clause_heading: Optional[str] = None
    matched_text: Optional[str] = None
    scope: Optional[str] = None
    # verified | source_verification_required | no_statutory_source_expected
    evidence_status: str = "no_statutory_source_expected"
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── rules loading ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def load_rules(path: str | None = None) -> dict[str, Any]:
    return json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))


def _rx(pattern: str) -> re.Pattern:
    return _compile(pattern)


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


# ── helpers ────────────────────────────────────────────────────────────────────
def detect_restraint_scope(text: str, rules: dict[str, Any] | None = None) -> str:
    """'post_employment' | 'during_only' | 'unclear' for a restraint clause."""
    spec = (rules or load_rules())["restraint_scope"]
    if any(_rx(p).search(text) for p in spec["post"]):
        return "post_employment"
    if any(_rx(p).search(text) for p in spec["during"]):
        return "during_only"
    return "unclear"


_NUM_WORDS = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|eighteen|twenty[\s\-]?four|thirty[\s\-]?six"
_DURATION_RE = re.compile(rf"\b({_NUM_WORDS})\s*(?:\(\s*(\d+)\s*\)\s*)?(years?|months?)\b", re.IGNORECASE)


def extract_duration(text: str) -> Optional[str]:
    """First duration mentioned, e.g. 'three (3) years' -> '3 years'."""
    m = _DURATION_RE.search(text)
    if not m:
        return None
    number = m.group(2) or m.group(1)
    return f"{number} {m.group(3).lower()}"


def _snippet(text: str, pattern: Optional[re.Pattern] = None, limit: int = 220) -> str:
    """Sentence of the clause around the trigger (or the start of the clause)."""
    flat = " ".join(text.split())
    if pattern is not None:
        m = pattern.search(flat)
        if m:
            start = max(flat.rfind(".", 0, m.start()) + 1, 0)
            end = flat.find(".", m.end())
            end = len(flat) if end == -1 else end + 1
            return flat[start:end].strip()[:limit]
    return flat[:limit]


def _doc_type_ok(rule: dict[str, Any], doc_type: str) -> bool:
    allowed = rule.get("doc_types")
    return not allowed or doc_type in allowed


def _section_matches(act_title: str, number: str, expected: dict[str, str]) -> bool:
    return expected["act_keyword"] in act_title.lower() and number.lower() == expected["number"].lower()


def _best_quote(text: str, query: str, max_chars: int = 450) -> str:
    """Verbatim passage from `text` best matching `query` (a true substring of text)."""
    spans = [(m.start(), m.end()) for m in re.finditer(r".+?(?:[.;:](?=\s|$)|$)", text, re.DOTALL) if m.group().strip()]
    if not spans:
        return text.strip()[:max_chars]
    q_tokens = set(tokenize(query))
    best_i, best_score = 0, -1.0
    for i, (s, e) in enumerate(spans):
        toks = set(tokenize(text[s:e]))
        score = len(q_tokens & toks) / (len(toks) ** 0.5 or 1)
        if score > best_score:
            best_i, best_score = i, score
    start, end = spans[best_i]
    j = best_i
    while end - start < 120 and j + 1 < len(spans):  # extend very short sentences
        j += 1
        end = spans[j][1]
    return text[start:min(end, start + max_chars)].strip()


class _EvidenceFinder:
    def __init__(self, retriever: Any) -> None:
        self.retriever = retriever
        self.records = list(getattr(retriever, "records", []) or []) if retriever is not None else []
        self.by_id = {r.section_id: r for r in self.records}

    def find(self, rule: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        expected = rule.get("expected_section")
        if not expected:
            return [], "no_statutory_source_expected"
        if self.retriever is None or not self.records:
            return [], SOURCE_VERIFICATION_REQUIRED

        chosen_rec, rank, score, how = None, None, None, "rule_mapped"
        for i, res in enumerate(self.retriever.search(rule["retrieval_query"], k=8), 1):
            if _section_matches(res.act, res.section_number, expected):
                chosen_rec, rank, score, how = self.by_id.get(res.section_id), i, res.score, "retrieved"
                break
        if chosen_rec is None:  # fall back to the section named by the rule
            for rec in self.records:
                if _section_matches(rec.act_title, rec.section_number, expected):
                    chosen_rec = rec
                    break
        if chosen_rec is None:
            return [], SOURCE_VERIFICATION_REQUIRED

        quote = _best_quote(chosen_rec.text, rule["retrieval_query"])
        if not quote or quote not in chosen_rec.text:  # verbatim check
            return [], SOURCE_VERIFICATION_REQUIRED
        return [{
            "section_id": chosen_rec.section_id,
            "source_id": chosen_rec.source_id,
            "citation": chosen_rec.citation,
            "act": chosen_rec.act_title,
            "section_number": chosen_rec.section_number,
            "heading": chosen_rec.heading,
            "status": chosen_rec.status,
            "quote": quote,
            "support": "supports",
            "retrieval_source": how,   # retrieved | rule_mapped
            "rank": rank,
            "score": score,
            "verification": "verified",
        }], "verified"


# ── main entry points ──────────────────────────────────────────────────────────
def analyze_clauses(
    clauses: list[ClauseInput],
    retriever: Any = None,
    doc_type: str = "other",
    rules: dict[str, Any] | None = None,
) -> list[FindingDraft]:
    """Run all rules over the clauses and return findings sorted by severity."""
    rules = rules or load_rules()
    finder = _EvidenceFinder(retriever)
    findings: list[FindingDraft] = []
    present_labels: set[str] = set()
    evidence_cache: dict[str, tuple[list[dict[str, Any]], str]] = {}

    for c in clauses:
        types = c.clause_types or classify_clause(c.heading, c.text)
        c.clause_types = types
        present_labels.update(types)
        scope_cache: Optional[str] = None

        for rule in rules["rules"]:
            if not set(rule["applies_to"]) & set(types) or not _doc_type_ok(rule, doc_type):
                continue
            if rule.get("scope"):
                scope_cache = scope_cache or detect_restraint_scope(c.text, rules)
                if scope_cache != rule["scope"]:
                    continue
            trigger = None
            if rule.get("match_any"):
                trigger = next((_rx(p) for p in rule["match_any"] if _rx(p).search(c.text)), None)
                if trigger is None:
                    continue
            if rule.get("match_none") and any(_rx(p).search(c.text) for p in rule["match_none"]):
                continue

            if rule["id"] not in evidence_cache:
                evidence_cache[rule["id"]] = finder.find(rule)
            evidence, ev_status = evidence_cache[rule["id"]]
            duration = extract_duration(c.text) if rule.get("scope") else None
            reason = rule["reason"].replace("{duration}", f" (stated period: {duration})" if duration else "")
            findings.append(FindingDraft(
                rule_id=rule["id"], risk_level=rule["risk_level"], category=rule["category"],
                title=rule["title"], reason=reason, recommendation=rule["recommendation"],
                clause_number=c.clause_number, clause_id=c.clause_id, clause_label=c.clause_label,
                clause_heading=c.heading, matched_text=_snippet(c.text, trigger or _first_trigger(c.text, types)),
                scope=scope_cache if rule.get("scope") else None,
                evidence_status=ev_status, evidence=[dict(e) for e in evidence],
            ))

    for m in rules.get("missing_clause_rules", []):
        if not _doc_type_ok(m, doc_type) or present_labels & set(m["any_of"]):
            continue
        findings.append(FindingDraft(
            rule_id=m["id"], risk_level="info", category="missing_clause", title=m["title"],
            reason=m["reason"], recommendation="Review the document to confirm whether this topic is intentionally omitted.",
            evidence_status="no_statutory_source_expected",
        ))

    findings.sort(key=lambda f: (-LEVEL_ORDER[f.risk_level], f.clause_number if f.clause_number is not None else 10**6))
    return findings


_TRIGGER_WORDS = re.compile(r"compet|restrain|solicit|penalt|liquidated|forfeit|indemn|arbitrat|terminat|confidential", re.I)


def _first_trigger(text: str, types: list[str]) -> Optional[re.Pattern]:
    return _TRIGGER_WORDS


def summarize(findings: list[FindingDraft]) -> dict[str, Any]:
    counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        counts[f.risk_level] += 1
    return {
        "counts": counts,
        "total_findings": len(findings),
        "missing_clauses": sum(1 for f in findings if f.category == "missing_clause"),
        "verified": sum(1 for f in findings if f.evidence_status == "verified"),
        "source_verification_required": sum(1 for f in findings if f.evidence_status == SOURCE_VERIFICATION_REQUIRED),
        "review_required": sum(1 for f in findings if f.risk_level in ("high", "medium")),
        "disclaimer": DISCLAIMER,
    }
