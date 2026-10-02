"""
backend/api/contracts.py
────────────────────────
API endpoints for:
- Uploading contract files (PDF, DOCX, TXT)
- Submitting raw contract text
- Listing contracts and viewing contract clauses
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.schemas import (
    ClauseSchema,
    ContractDetailSchema,
    ContractSummarySchema,
    IngestionResponse,
    IngestTextRequest,
)
from backend.database.models import Clause, Contract
from backend.database.session import get_session
from backend.ingestion.service import ingest_contract

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])


@router.post(
    "/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a contract file (PDF, DOCX, TXT)",
)
async def upload_contract(
    file: UploadFile = File(..., description="PDF, DOCX, or plain text contract"),
    title: Optional[str] = Form(None, description="Optional custom title"),
    jurisdiction: str = Form("india", description="Governing legal jurisdiction"),
    session: AsyncSession = Depends(get_session),
) -> IngestionResponse:
    """
    Uploads a contract, parses it page-by-page, splits it into structured clauses,
    and saves Document, Contract, and Clause entities to the database.
    """
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )

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


@router.post(
    "/text",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest contract text directly from string payload",
)
async def ingest_raw_text(
    payload: IngestTextRequest,
    session: AsyncSession = Depends(get_session),
) -> IngestionResponse:
    """
    Allows pasting contract text directly from the UI without saving a local file first.
    """
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Contract text cannot be empty"
        )

    doc, contract, clauses = await ingest_contract(
        session=session,
        content=payload.text.encode("utf-8"),
        filename=payload.filename or "pasted_contract.txt",
        title=payload.title,
        jurisdiction=payload.jurisdiction or "india",
    )

    return IngestionResponse(
        document_id=doc.id,
        contract_id=contract.id,
        title=contract.title,
        doc_type=contract.doc_type,
        filename=doc.filename,
        file_type=doc.file_type,
        clauses_count=len(clauses),
        message=f"Successfully ingested {len(clauses)} clauses",
    )


@router.get(
    "",
    response_model=list[ContractSummarySchema],
    summary="List all ingested contracts",
)
async def list_contracts(
    session: AsyncSession = Depends(get_session),
) -> list[ContractSummarySchema]:
    """Return all contracts with their clause counts, ordered by creation date."""
    stmt = (
        select(
            Contract,
            func.count(Clause.id).label("clauses_count"),
        )
        .outerjoin(Clause, Clause.contract_id == Contract.id)
        .group_by(Contract.id)
        .order_by(Contract.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    results: list[ContractSummarySchema] = []
    for contract, count in rows:
        summary = ContractSummarySchema.model_validate(contract)
        summary.clauses_count = count
        results.append(summary)

    return results


@router.get(
    "/{contract_id}",
    response_model=ContractDetailSchema,
    summary="Get contract by ID with all clauses",
)
async def get_contract(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> ContractDetailSchema:
    """Return full contract details including all clauses ordered by clause_number."""
    stmt = (
        select(Contract)
        .where(Contract.id == contract_id)
        .options(selectinload(Contract.clauses))
    )
    contract = (await session.execute(stmt)).scalar_one_or_none()

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id={contract_id} not found",
        )

    # Sort clauses by clause_number
    sorted_clauses = sorted(contract.clauses, key=lambda c: c.clause_number)
    detail = ContractDetailSchema.model_validate(contract)
    detail.clauses = [ClauseSchema.model_validate(c) for c in sorted_clauses]
    detail.clauses_count = len(sorted_clauses)
    return detail


@router.get(
    "/{contract_id}/clauses",
    response_model=list[ClauseSchema],
    summary="Get all clauses for a contract",
)
async def get_contract_clauses(
    contract_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[ClauseSchema]:
    """Return ordered clauses for a specific contract."""
    stmt = (
        select(Clause)
        .where(Clause.contract_id == contract_id)
        .order_by(Clause.clause_number.asc())
    )
    clauses = (await session.execute(stmt)).scalars().all()
    if not clauses:
        # Check if contract exists
        contract_exists = (
            await session.execute(select(Contract.id).where(Contract.id == contract_id))
        ).scalar_one_or_none()
        if not contract_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract with id={contract_id} not found",
            )
    return [ClauseSchema.model_validate(c) for c in clauses]
