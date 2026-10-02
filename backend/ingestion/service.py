"""
backend/ingestion/service.py
────────────────────────────
High-level ingestion service:
1. Accepts uploaded file (bytes or path)
2. Parses text and pages via DocumentParser
3. Segments text into structured clauses via ClauseSplitter
4. Persists Document, Contract, and Clause entities in SQLite
5. Returns the persisted ORM objects
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import Clause, Contract, Document
from backend.ingestion.clause_splitter import split_into_clauses
from backend.ingestion.document_parser import ParsedDocument, parse_document

logger = logging.getLogger(__name__)


def _infer_doc_type(title: str, full_text: str) -> str:
    """Heuristic doc_type detection from title & contract text."""
    lower = f"{title} {full_text[:500]}".lower()
    if "employment" in lower or "offer letter" in lower:
        return "employment"
    if "service" in lower or "master service" in lower or "msa" in lower:
        return "service"
    if "non-disclosure" in lower or "nda" in lower or "confidentiality" in lower:
        return "nda"
    if "lease" in lower or "rent" in lower or "tenancy" in lower:
        return "lease"
    if "loan" in lower or "credit agreement" in lower:
        return "loan"
    return "other"


async def ingest_contract(
    session: AsyncSession,
    content: Union[bytes, Path, str],
    filename: str,
    title: Optional[str] = None,
    jurisdiction: str = "india",
    user_id: Optional[int] = None,
) -> tuple[Document, Contract, list[Clause]]:
    """
    Ingest a contract file into the database.

    Args:
        session: Active SQLAlchemy AsyncSession
        content: Raw bytes or local file path
        filename: Original file name (e.g. "employment_agreement.pdf")
        title: Human-readable contract title (defaults to cleaned filename)
        jurisdiction: ISO / country identifier (defaults to "india")
        user_id: Optional user owner

    Returns:
        tuple of (Document, Contract, list[Clause])
    """
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    # Read raw bytes if content is bytes, else read from file
    if isinstance(content, bytes):
        raw_bytes = content
    else:
        path = Path(content)
        filename = filename or path.name
        raw_bytes = path.read_bytes()

    # Save to disk with unique prefix to avoid filename collisions
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(filename).name}"
    saved_path = settings.uploads_dir / safe_name
    saved_path.write_bytes(raw_bytes)

    # 1. Parse document
    parsed: ParsedDocument = parse_document(raw_bytes, filename=filename)
    logger.info(
        "Parsed %s (%s, %d bytes, %d pages)",
        filename,
        parsed.file_type,
        len(raw_bytes),
        len(parsed.pages),
    )

    # 2. Persist Document record
    doc_record = Document(
        filename=filename,
        file_type=parsed.file_type,
        file_path=str(saved_path),
        file_hash=parsed.file_hash,
        user_id=user_id,
    )
    session.add(doc_record)
    await session.flush()

    # 3. Create Contract record
    contract_title = title or Path(filename).stem.replace("_", " ").title()
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

    # 4. Split into clauses
    extracted = split_into_clauses(parsed)
    logger.info("Extracted %d clauses from '%s'", len(extracted), contract_title)

    clause_records: list[Clause] = []
    for ec in extracted:
        cl = Clause(
            contract_id=contract_record.id,
            clause_number=ec.clause_number,
            heading=ec.heading,
            text=ec.text,
            clause_type=ec.clause_type,
            page=ec.page,
        )
        session.add(cl)
        clause_records.append(cl)

    await session.commit()

    # Refresh to ensure all attributes and IDs are loaded
    await session.refresh(doc_record)
    await session.refresh(contract_record)
    for cl in clause_records:
        await session.refresh(cl)

    return doc_record, contract_record, clause_records
