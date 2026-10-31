"""
backend/api/sync.py
───────────────────
Live verification of stored statutes against the official source (India Code).

  POST /api/legal/sync/check    check Acts now; optionally raise Legal Change alerts
  GET  /api/legal/sync/status   last check result for every Act

The stored statute text is never overwritten automatically. A check only reports whether
the official text still contains what we stored, and raises alerts for human review.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.legal import _impacted_clauses
from backend.api.schemas import DISCLAIMER
from backend.database.session import get_session
from backend.legal_sync.persist import latest_status, run_checks

router = APIRouter(prefix="/api/legal/sync", tags=["Live source check"])


class CheckRequest(BaseModel):
    source_ids: Optional[list[int]] = None
    force: bool = False            # ignore the 6-hour download cache
    create_alerts: bool = True     # raise Legal Change alerts for changed / omitted sections


class CheckResponse(BaseModel):
    results: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    disclaimer: str = DISCLAIMER


@router.post("/check", response_model=CheckResponse, summary="Check stored statutes against the official source now")
async def check(payload: Optional[CheckRequest] = None, session: AsyncSession = Depends(get_session)) -> CheckResponse:
    payload = payload or CheckRequest()
    outcome = await run_checks(session, payload.source_ids, payload.force, payload.create_alerts)
    alerts: list[dict[str, Any]] = []
    for change in outcome["new_changes"]:
        impacted = await _impacted_clauses(session, change)
        change.processed = True
        alerts.append({"change_id": change.id, "title": change.title, "impacted_clauses": impacted})
    await session.commit()
    return CheckResponse(results=outcome["results"], alerts=alerts)


@router.get("/status", response_model=list[dict[str, Any]], summary="Last live-check result for every Act")
async def status(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    return await latest_status(session)
