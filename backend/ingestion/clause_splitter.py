"""
backend/ingestion/clause_splitter.py
────────────────────────────────────
Splits a raw contract into individual clauses with:
- clause_number (1-indexed integer)
- heading (extracted or inferred)
- text (verbatim clause content)
- clause_type (heuristic classification for risk engine and UI tagging)
- page (page number from document pages if available)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from backend.ingestion.document_parser import ParsedDocument


@dataclass
class ExtractedClause:
    clause_number: int
    heading: Optional[str]
    text: str
    clause_type: str
    page: Optional[int] = 1
    clause_label: Optional[str] = None


# ── Heuristic Clause Type Classifier ──────────────────────────────────────────

CLAUSE_TYPE_PATTERNS: dict[str, list[re.Pattern]] = {
    "non_compete": [
        re.compile(r"\bnon[\s\-_]?compete\b", re.I),
        re.compile(r"\bnon[\s\-_]?competition\b", re.I),
        re.compile(r"\brestraint\s+of\s+trade\b", re.I),
        re.compile(r"\bcovenant\s+not\s+to\s+compete\b", re.I),
        re.compile(r"\bcompetitive\s+activity\b", re.I),
    ],
    "non_solicitation": [
        re.compile(r"\bnon[\s\-_]?solicit(ation)?\b", re.I),
        re.compile(r"\bsolicit\s+(any\s+)?(employee|client|customer)\b", re.I),
    ],
    "indemnity": [
        re.compile(r"\bindemnif(y|ied|ication|ies)\b", re.I),
        re.compile(r"\bhold\s+harmless\b", re.I),
        re.compile(r"\bdefend\s+and\s+indemnify\b", re.I),
    ],
    "liability": [
        re.compile(r"\blimitation\s+of\s+liability\b", re.I),
        re.compile(r"\bindirect(\s+or\s+consequential)?\s+damages\b", re.I),
        re.compile(r"\baggregate\s+liability\b", re.I),
        re.compile(r"\bliability\s+cap\b", re.I),
        re.compile(r"\buncapped\b", re.I),
    ],
    "confidentiality": [
        re.compile(r"\bconfidential(ity)?\b", re.I),
        re.compile(r"\bnon[\s\-_]?disclosure\b", re.I),
        re.compile(r"\bproprietary\s+information\b", re.I),
        re.compile(r"\btrade\s+secrets?\b", re.I),
    ],
    "termination": [
        re.compile(r"\bterminat(ion|e|ed)\b", re.I),
        re.compile(r"\bterm\s+of\s+employment\b", re.I),
        re.compile(r"\bterm\s+and\s+termination\b", re.I),
        re.compile(r"\bnotice\s+period\b", re.I),
    ],
    "arbitration": [
        re.compile(r"\barbitrat(ion|or|al)\b", re.I),
        re.compile(r"\barbitration\s+and\s+conciliation\b", re.I),
        re.compile(r"\bdispute\s+resolution\b", re.I),
    ],
    "jurisdiction": [
        re.compile(r"\bgoverning\s+law\b", re.I),
        re.compile(r"\bjurisdiction\b", re.I),
        re.compile(r"\bcourts\s+of\b", re.I),
    ],
    "ip": [
        re.compile(r"\bintellectual\s+property\b", re.I),
        re.compile(r"\bwork\s+(made\s+)?for\s+hire\b", re.I),
        re.compile(r"\binvention(s)?\b", re.I),
        re.compile(r"\bassignment\s+of\s+(ip|rights|patents)\b", re.I),
    ],
    "payment": [
        re.compile(r"\bpayment\s+terms\b", re.I),
        re.compile(r"\bremuneration\b", re.I),
        re.compile(r"\bconsideration\b", re.I),
        re.compile(r"\bsalary\b", re.I),
        re.compile(r"\bfees\s+and\s+expenses\b", re.I),
        re.compile(r"\binvoic(e|ing)\b", re.I),
    ],
}


def classify_clause_type(heading: Optional[str], text: str) -> str:
    """Classify the clause based on heading and text keywords."""
    combined = f"{heading or ''}\n{text}"
    for clause_type, patterns in CLAUSE_TYPE_PATTERNS.items():
        if any(p.search(combined) for p in patterns):
            return clause_type
    return "general"


# ── Clause Boundary Regex ─────────────────────────────────────────────────────

# Matches split points before:
# "Clause 1.", "Clause 1:", "Section 2.", "Article III", "1. DEFINITIONS", etc.
# Note: uses strictly non-capturing groups so re.split doesn't inject match tokens.
CLAUSE_SPLIT_REGEX = re.compile(
    r"\n+(?="
    r"(?:Clause|CLAUSE|Section|SECTION|Article|ARTICLE)\s+(?:[0-9IVXLCDM]+|[A-Z])[\.:\s\-]"
    r"|(?:[0-9]{1,2}(?:\.[0-9]{1,2})*|\([0-9a-z]\))\s*[\.\:\-]\s+[A-Z]"
    r")",
    re.MULTILINE,
)

HEADER_EXTRACTOR = re.compile(
    r"^(?:(?:Clause|CLAUSE|Section|SECTION|Article|ARTICLE)\s+(?:[0-9IVXLCDM]+|[A-Z])[\.:\s\-]*"
    r"|(?:[0-9]{1,2}(?:\.[0-9]{1,2})*|\([0-9a-z]\))\s*[\.\:\-]\s*)"
    r"([^\n\:\.]+)(?:[\n\:\.]|$)",
    re.MULTILINE,
)

LABEL_EXTRACTOR = re.compile(
    r"^((?:Clause|CLAUSE|Section|SECTION|Article|ARTICLE)\s+(?:[0-9IVXLCDM]+|[A-Z])"
    r"|[0-9]{1,2}(?:\.[0-9]{1,2})*|\([0-9a-z]\))(?=[\.\:\s\-]|$)"
)

def _clean_text(text: str) -> str:
    """Normalize linebreaks and spaces."""
    return re.sub(r"\r\n|\r", "\n", text).strip()


def _estimate_page_for_clause(clause_text: str, doc: ParsedDocument) -> int:
    """Find which page this clause predominantly appears on."""
    if not doc.pages or len(doc.pages) == 1:
        return 1
    snippet = clause_text[:80].strip()
    if not snippet:
        return 1
    for page in doc.pages:
        if snippet in page.text:
            return page.page_number
    return 1


def split_into_clauses(doc: ParsedDocument) -> list[ExtractedClause]:
    """
    Splits ParsedDocument full text into a list of ExtractedClause objects.
    Uses structural headers where present; falls back to paragraph chunks
    if no structured clause markers are found.
    """
    raw_text = _clean_text(doc.full_text)
    if not raw_text:
        return []

    chunks = CLAUSE_SPLIT_REGEX.split(raw_text)
    clean_chunks = [c.strip() for c in chunks if c and c.strip()]

    if len(clean_chunks) < 2:
        # Fallback: Split on double newlines
        clean_chunks = [
            p.strip() for p in re.split(r"\n\s*\n+", raw_text) if len(p.strip()) > 30
        ]

    if not clean_chunks:
        clean_chunks = [raw_text]

    clauses: list[ExtractedClause] = []

    for idx, chunk in enumerate(clean_chunks, start=1):
        lines = chunk.split("\n", 1)
        first_line = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        heading: Optional[str] = None
        m = HEADER_EXTRACTOR.match(first_line)

        if m:
            heading = m.group(1).strip()
            # If body is non-empty, use body as the clause body, otherwise keep the full chunk
            clause_body = body if body else chunk
        elif idx == 1 and ("agreement" in first_line.lower() or "whereas" in chunk.lower()):
            heading = "Preamble & Recitals"
            clause_body = chunk
        elif len(first_line) <= 80 and (
            first_line.isupper()
            or any(k in first_line.lower() for k in CLAUSE_TYPE_PATTERNS.keys())
        ):
            heading = first_line
            clause_body = body if body else chunk
        else:
            clause_body = chunk

        # Classification looks at both heading and full chunk
        clause_type = classify_clause_type(heading, chunk)
        page = _estimate_page_for_clause(clause_body, doc)

        lm = LABEL_EXTRACTOR.match(first_line)
        clause_label = lm.group(1) if lm else None

        clauses.append(
            ExtractedClause(
                clause_number=idx,
                heading=heading,
                text=clause_body,
                clause_type=clause_type,
                page=page,
                clause_label=clause_label,
            )
        )

    return clauses
