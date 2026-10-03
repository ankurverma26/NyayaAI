"""
backend/ingestion/service.py
────────────────────────────
High-level ingestion service:
1. Accepts uploaded file (bytes or path)
2. Parses text and pages via DocumentParser
3. Segments text into structured clauses via ClauseSplitter
4. Assigns multi-label clause types (backend/analysis/clause_classifier.py)
5. Persists Document, Contract, and Clause entities
6. Returns the persisted ORM objects

Security: the raw upload is NOT written to disk (it is parsed from memory), so no
contract files are left behind in data/uploads/. Only a SHA-256 hash is kept.
"""
from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.analysis.clause_classifier import classify_clause
from backend.database.models import Clause, Contract, Document
from backend.ingestion.clause_splitter import split_into_clauses
from backend.ingestion.document_parser import ParsedDocument, parse_document

logger = logging.getLogger(__name__)

# Order matters: most specific first. Word boundaries avoid false hits such as
# "nda" inside "standard" or "rent" inside "parent"/"current".
_DOC_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("employment", re.compile(r"\b(employment|employee|offer\s+letter|appointment\s+letter)\b", re.I)),
    ("nda", re.compile(r"\b(non[\s\-]?disclosure|nda)\b", re.I)),
    ("lease", re.compile(r"\b(lease|rent|rental|tenancy|landlord|tenant)\b", re.I)),
    ("loan", re.compile(r"\b(loan|credit\s+agreement|borrower|lender)\b", re.I)),
    ("service", re.compile(r"\b(services?|consult\w*|vendor|msa|freelance\w*)\b", re.I)),
]


def _infer_doc_type(title: str, full_text: str) -> str:
    """Heuristic doc_type detection from title & start of the contract text."""
    sample = f"{title} {full_text[:600]}"
    for doc_type, pattern in _DOC_TYPE_PATTERNS:
        if pattern.search(sample):
            return doc_type
    return "other"


async def ingest_contract(
    session: AsyncSession,
    content: Union[bytes, Path, str],
    filename: str,
    title: Optional[str] = None,
    jurisdiction: str = "india",
    user_id: Optional[int] = None,
) -> tuple[Document, Contract, list[Clause]]:
    """Ingest a contract file into the database. Returns (Document, Contract, clauses)."""
    if isinstance(content, bytes):
        raw_bytes = content
    else:
        path = Path(content)
        filename = filename or path.name
        raw_bytes = path.read_bytes()

    safe_name = Path(filename).name  # strip any directory components

    # 1. Parse document (in memory)
    parsed: ParsedDocument = parse_document(raw_bytes, filename=safe_name)
    logger.info("Parsed upload (%s, %d bytes, %d pages)", parsed.file_type, len(raw_bytes), len(parsed.pages))

    # 2. Persist Document record (file itself is not stored)
    doc_record = Document(
        filename=safe_name,
        file_type=parsed.file_type,
        file_path=f"not_stored/{uuid.uuid4().hex[:8]}",
        file_hash=parsed.file_hash,
        user_id=user_id,
    )
    session.add(doc_record)
    await session.flush()

    # 3. Create Contract record
    contract_title = title or Path(safe_name).stem.replace("_", " ").title()
    doc_type = _infer_doc_type(contract_title, parsed.full_text)
    contract_record = Contract(
        title=contract_title,
        doc_type=doc_type,
        jurisdiction=jurisdiction,
        user_id=user_id,
        document_id=doc_record.id,
    )
    session.add(contract_record)
    await session.flush()

    # 4. Split into clauses and classify (multi-label)
    extracted = split_into_clauses(parsed)
    logger.info("Extracted %d clauses", len(extracted))

    clause_records: list[Clause] = []
    for ec in extracted:
        types = classify_clause(ec.heading, ec.text)
        cl = Clause(
            contract_id=contract_record.id,
            clause_number=ec.clause_number,
            clause_label=ec.clause_label,
            heading=ec.heading,
            text=ec.text,
            clause_type=types[0],
            clause_types=types,
            page=ec.page,
        )
        session.add(cl)
        clause_records.append(cl)

    await session.commit()

    await session.refresh(doc_record)
    await session.refresh(contract_record)
    for cl in clause_records:
        await session.refresh(cl)

    return doc_record, contract_record, clause_records
