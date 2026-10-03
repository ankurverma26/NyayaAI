"""Risk analysis endpoints: run the analysis and read the issues."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analysis.risk_engine import DISCLAIMER
from backend.analysis.service import analyze_contract, list_issues
from backend.database.session import get_session

router = APIRouter(prefix="/api/contracts", tags=["Analysis"])


class AnalysisSummary(BaseModel):
    contract_id: int
    doc_type: Optional[str] = None
    clauses_analyzed: int
    counts: dict[str, int]
    total_findings: int
    missing_clauses: int
    verified: int
    source_verification_required: int
    review_required: int
    disclaimer: str = DISCLAIMER


class IssuesResponse(BaseModel):
    contract_id: int
    issues: list[dict[str, Any]]
    disclaimer: str = DISCLAIMER


@router.post("/{contract_id}/analyze", response_model=AnalysisSummary, summary="Run risk analysis on a contract")
async def analyze(contract_id: int, session: AsyncSession = Depends(get_session)) -> AnalysisSummary:
    try:
        result = await analyze_contract(session, contract_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")
    return AnalysisSummary(**result)


@router.get("/{contract_id}/issues", response_model=IssuesResponse, summary="List findings with evidence")
async def issues(contract_id: int, session: AsyncSession = Depends(get_session)) -> IssuesResponse:
    items = await list_issues(session, contract_id)
    if items is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract {contract_id} not found")
    return IssuesResponse(contract_id=contract_id, issues=items)
