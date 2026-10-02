"""
backend/api/statutes.py
───────────────────────
API endpoints for viewing loaded statutes and provisions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.schemas import (
    LegalSourceDetailSchema,
    LegalSourceSummarySchema,
    SectionSchema,
)
from backend.database.models import LegalSource, Section
from backend.database.session import get_session

router = APIRouter(prefix="/api/statutes", tags=["Statutes"])


@router.get(
    "",
    response_model=list[LegalSourceSummarySchema],
    summary="List all loaded statutes / legal sources",
)
async def list_statutes(
    session: AsyncSession = Depends(get_session),
) -> list[LegalSourceSummarySchema]:
    """Return all statutes with section counts."""
    stmt = (
        select(
            LegalSource,
            func.count(Section.id).label("sections_count"),
        )
        .outerjoin(Section, Section.source_id == LegalSource.id)
        .group_by(LegalSource.id)
        .order_by(LegalSource.title.asc())
    )
    rows = (await session.execute(stmt)).all()

    results: list[LegalSourceSummarySchema] = []
    for source, count in rows:
        summary = LegalSourceSummarySchema.model_validate(source)
        summary.sections_count = count
        results.append(summary)

    return results


@router.get(
    "/{source_id}",
    response_model=LegalSourceDetailSchema,
    summary="Get statute by ID with all sections",
)
async def get_statute(
    source_id: int,
    session: AsyncSession = Depends(get_session),
) -> LegalSourceDetailSchema:
    """Return statute details with all associated sections."""
    stmt = (
        select(LegalSource)
        .where(LegalSource.id == source_id)
        .options(selectinload(LegalSource.sections))
    )
    source = (await session.execute(stmt)).scalar_one_or_none()

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Statute with id={source_id} not found",
        )

    detail = LegalSourceDetailSchema.model_validate(source)
    detail.sections = [SectionSchema.model_validate(s) for s in source.sections]
    detail.sections_count = len(source.sections)
    return detail
