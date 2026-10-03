"""
backend/api/contracts.py
────────────────────────
API endpoints for contracts and risk analysis:

  POST /documents/upload            – multipart upload → ingest → return contract_id
  POST /contracts/text              – raw text ingestion
  GET  /contracts                   – recent list with clause counts
  GET  /contracts/{id}              – contract detail with clauses
  GET  /contracts/{id}/clauses      – ordered clause list
  POST /contracts/{id}/analyze      – run risk engine + store findings
  GET  /contracts/{id}/issues       – findings with evidence, most severe first
  GET  /contracts/{id}/evidence     – raw evidence rows for all findings

All logic lives in services; routes only orchestrate HTTP glue.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.schemas import (
    AnalysisSummary,
    ClauseSchema,
    ContractDetailSchema,
    ContractSummarySchema,
    EvidenceListResponse,
    IngestionResponse,
    IngestTextRequest,
    IssuesResponse,
)
from backend.database.models import Clause, Contract, Evidence, RiskFinding, Section
from backend.database.session import get_session
from backend.ingestion.service import ingest_contract
from backend.analysis.service import analyze_contract, list_issues
from backend.analysis.risk_engine import DISCLAIMER

# ── Document upload router (separate prefix) ───────────────────────────────────
documents_router = APIRouter(prefix="/api/documents", tags=["Documents"])

# ── Contracts router ───────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/contracts", tags=["Contracts"])


# ── Allowed upload types ───────────────────────────────────────────────────────
_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",   # browsers sometimes send this for .docx
}
_ALLOWED_EXT = {".pdf", ".docx", ".txt"}
_MAX_BYTES = 10 * 1024 * 1024   # 10 MB


def _validate_upload(file: UploadFile, raw_bytes: bytes) -> None:
    """Raise 400 for empty, oversized, or wrong-type uploads."""
    if not raw_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(raw_bytes) > _MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File exceeds 10 MB limit")
    from pathlib import Path
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXT)}",
        )


# ── POST /documents/upload ─────────────────────────────────────────────────────


@documents_router.post(
    "/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a contract file (PDF, DOCX, TXT) and ingest it",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF, DOCX, or plain-text contract"),
    title: Optional[str] = Form(None, description="Optional custom title"),
    jurisdiction: str = Form("india", description="Governing legal jurisdiction"),
    session: AsyncSession = Depends(get_session),
) -> IngestionResponse:
    """
    Multipart upload endpoint.  Parses, chunks, classifies, and stores the
    contract in one call.  Returns the new ``contract_id`` along with counts.
    """
    raw_bytes = await file.read()
    _validate_upload(file, raw_bytes)

    doc, contract, clauses = await ingest_contract(
        session=session,
        content=raw_bytes,
        filename=file.filename or "uploaded_contract.txt",
        title=title,
        jurisdiction=jurisdiction,
    )
    return IngestionResponse(
        document_id=doc.id,
        contract_id=contract.id,
        title=contract.title,
        doc_type=contract.doc_type,
        filename=doc.filename,
        file_type=doc.file_type,
        clauses_count=len(clauses),
        message=f"Successfully ingested {len(clauses)} clauses from '{doc.filename}'",
    )


# ── POST /contracts/upload  (legacy alias kept for backward compat) ─────────────


@router.post(
    "/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a contract file (PDF, DOCX, TXT)",
    include_in_schema=False,   # hide duplicate in docs; prefer /documents/upload
)
async def upload_contract_alias(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    jurisdiction: str = Form("india"),
    session: AsyncSession = Depends(get_session),
) -> IngestionResponse:
    raw_bytes = await file.read()
    _validate_upload(file, raw_bytes)
    doc, contract, clauses = await ingest_contract(
        session=session,
        content=raw_bytes,
        filename=file.filename or "uploaded_contract.txt",
        title=title,
        jurisdiction=jurisdiction,
    )
    return IngestionResponse(
        document_id=doc.id, contract_id=contract.id, title=contract.title,
        doc_type=contract.doc_type, filename=doc.filename, file_type=doc.file_type,
        clauses_count=len(clauses),
        message=f"Successfully ingested {len(clauses)} clauses from '{doc.filename}'",
    )


# ── POST /contracts/text ───────────────────────────────────────────────────────


@router.post(
    "/text",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest contract text directly from a string payload",
)
async def ingest_raw_text(
    payload: IngestTextRequest,
    session: AsyncSession = Depends(get_session),
) -> IngestionResponse:
    """Paste contract text from the UI without saving a local file."""
    if not payload.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Contract text cannot be empty")

    doc, contract, clauses = await ingest_contract(
        session=session,
        content=payload.text.encode("utf-8"),
        filename=payload.filename or "pasted_contract.txt",
        title=payload.title,
        jurisdiction=payload.jurisdiction or "india",
    )
    return IngestionResponse(
        document_id=doc.id, contract_id=contract.id, title=contract.title,
        doc_type=contract.doc_type, filename=doc.filename, file_type=doc.file_type,
        clauses_count=len(clauses),
        message=f"Successfully ingested {len(clauses)} clauses",
    )


# ── GET /contracts ─────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[ContractSummarySchema],
    summary="List recently ingested contracts",
)
async def list_contracts(
    limit: int = Query(default=50, ge=1, le=200, description="Max contracts to return"),
    session: AsyncSession = Depends(get_session),
) -> list[ContractSummarySchema]:
    """Return contracts ordered newest-first with their clause counts."""
    stmt = (
        select(Contract, func.count(Clause.id).label("clauses_count"))
        .outerjoin(Clause, Clause.contract_id == Contract.id)
        .group_by(Contract.id)
        .order_by(Contract.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    results: list[ContractSummarySchema] = []
    for contract, count in rows:
        s = ContractSummarySchema.model_validate(contract)
        s.clauses_count = count
        results.append(s)
    return results


# ── GET /contracts/{contract_id} ───────────────────────────────────────────────


@router.get(
    "/{contract_id}",
    response_model=ContractDetailSchema,
    summary="Get a contract with all its clauses",
)
async def get_contract(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> ContractDetailSchema:
    """Return full contract detail including clauses ordered by clause_number."""
    stmt = (
        select(Contract)
        .where(Contract.id == contract_id)
        .options(selectinload(Contract.clauses))
    )
    contract = (await session.execute(stmt)).scalar_one_or_none()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")

    sorted_clauses = sorted(contract.clauses, key=lambda c: c.clause_number)
    detail = ContractDetailSchema.model_validate(contract)
    detail.clauses = [ClauseSchema.model_validate(c) for c in sorted_clauses]
    detail.clauses_count = len(sorted_clauses)
    return detail


# ── GET /contracts/{contract_id}/clauses ───────────────────────────────────────


@router.get(
    "/{contract_id}/clauses",
    response_model=list[ClauseSchema],
    summary="Get ordered clauses for a contract",
)
async def get_contract_clauses(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[ClauseSchema]:
    """Return clauses sorted by clause_number."""
    # Verify contract exists first
    contract_exists = (
        await session.execute(select(Contract.id).where(Contract.id == contract_id))
    ).scalar_one_or_none()
    if not contract_exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")

    stmt = (
        select(Clause)
        .where(Clause.contract_id == contract_id)
        .order_by(Clause.clause_number.asc())
    )
    clauses = (await session.execute(stmt)).scalars().all()
    return [ClauseSchema.model_validate(c) for c in clauses]


# ── POST /contracts/{contract_id}/analyze ─────────────────────────────────────


@router.post(
    "/{contract_id}/analyze",
    response_model=AnalysisSummary,
    summary="Run risk engine + agent workflow on a contract",
)
async def analyze(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> AnalysisSummary:
    """
    Runs the rule-based risk engine on every clause, stores RiskFinding and
    Evidence rows (replacing any previous run), and returns summary counts.
    Re-running is idempotent — previous findings are deleted before new ones
    are written.
    """
    try:
        result = await analyze_contract(session, contract_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return AnalysisSummary(**result)


# ── GET /contracts/{contract_id}/issues ────────────────────────────────────────


@router.get(
    "/{contract_id}/issues",
    response_model=IssuesResponse,
    summary="List risk findings with evidence (most severe first)",
)
async def issues(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> IssuesResponse:
    """Returns all risk findings with their statutory evidence. Includes disclaimer."""
    items = await list_issues(session, contract_id)
    if items is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")
    return IssuesResponse(contract_id=contract_id, issues=items)


# ── GET /contracts/{contract_id}/evidence ──────────────────────────────────────


@router.get(
    "/{contract_id}/evidence",
    response_model=EvidenceListResponse,
    summary="Get all evidence rows attached to this contract’s findings",
)
async def get_contract_evidence(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> EvidenceListResponse:
    """
    Returns the raw Evidence rows (joined to their Section and LegalSource)
    for every RiskFinding on this contract.  Useful for building citation
    panels in the frontend.
    """
    # Confirm contract exists
    exists = (
        await session.execute(select(Contract.id).where(Contract.id == contract_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")

    stmt = (
        select(Evidence)
        .join(RiskFinding, Evidence.finding_id == RiskFinding.id)
        .where(RiskFinding.contract_id == contract_id)
        .options(
            selectinload(Evidence.finding),
            selectinload(Evidence.section).selectinload(Section.source),
        )
    )
    rows = (await session.execute(stmt)).scalars().all()

    finding_ids: set[int] = set()
    evidence_list = []
    for ev in rows:
        finding_ids.add(ev.finding_id)
        evidence_list.append({
            "id": ev.id,
            "finding_id": ev.finding_id,
            "finding_title": ev.finding.title if ev.finding else None,
            "risk_level": ev.finding.risk_level if ev.finding else None,
            "section_id": ev.section_id,
            "citation": ev.section.citation_str if ev.section else None,
            "act": ev.section.source.title if ev.section and ev.section.source else None,
            "section_number": ev.section.section_number if ev.section else None,
            "heading": ev.section.heading if ev.section else None,
            "law_status": ev.section.source.status if ev.section and ev.section.source else None,
            "quote": ev.quote,
            "support": ev.support,
            "verification": ev.verification_status,
        })

    return EvidenceListResponse(
        contract_id=contract_id,
        findings_count=len(finding_ids),
        evidence=evidence_list,
    )
