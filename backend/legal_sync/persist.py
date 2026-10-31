"""Run live checks for the Acts stored in the database and save the results (async DB layer)."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import LegalChange, LegalSource, SourceCheck
from backend.legal_sync.fetch import fetch_text
from backend.legal_sync.service import check_source

ALERT_STATUSES = {"changed": "differs from the official text", "omitted_or_repealed": "appears omitted or repealed in the official text"}


async def _latest_check(session: AsyncSession, source_id: int, with_fingerprint: bool = False) -> Optional[SourceCheck]:
    stmt = select(SourceCheck).where(SourceCheck.source_id == source_id)
    if with_fingerprint:
        stmt = stmt.where(SourceCheck.fingerprint.is_not(None))
    return (await session.execute(stmt.order_by(SourceCheck.id.desc()).limit(1))).scalar_one_or_none()


async def run_checks(
    session: AsyncSession,
    source_ids: Optional[list[int]] = None,
    force: bool = False,
    create_alerts: bool = True,
    fetcher: Optional[Callable] = None,
) -> dict[str, Any]:
    """Check each Act against its official PDF, one request at a time. Stored text is never modified.

    Returns {"results": [...], "new_changes": [LegalChange, ...]}.
    """
    fetch = fetcher or fetch_text
    stmt = select(LegalSource).options(selectinload(LegalSource.sections)).order_by(LegalSource.id)
    if source_ids:
        stmt = stmt.where(LegalSource.id.in_(source_ids))
    sources = (await session.execute(stmt)).scalars().all()

    results: list[dict[str, Any]] = []
    new_changes: list[LegalChange] = []
    today = date.today().isoformat()

    for src in sources:
        pairs = [(s.section_number, s.text) for s in src.sections]
        res = await asyncio.to_thread(check_source, src.url, pairs, fetch, force)  # network + PDF parsing off the event loop
        prev = await _latest_check(session, src.id, with_fingerprint=True)
        changed_since_last = bool(prev and res.get("fingerprint") and prev.fingerprint != res["fingerprint"])
        session.add(SourceCheck(
            source_id=src.id, url=src.url, outcome=res["outcome"], http_status=res.get("http_status"),
            fingerprint=res.get("fingerprint"), counts=res.get("counts"),
            details={"sections": res.get("sections"), "error": res.get("error")},
            changed_since_last=changed_since_last,
        ))

        if create_alerts and res["outcome"] == "needs_review":
            by_number = {s.section_number: s for s in src.sections}
            for number, info in (res.get("sections") or {}).items():
                if info["status"] not in ALERT_STATUSES:
                    continue
                title = f"Source check: {src.short_name or src.title} s.{number} {ALERT_STATUSES[info['status']]}"
                exists = (await session.execute(
                    select(LegalChange.id).where(LegalChange.title == title, LegalChange.date == today)
                )).first()
                if exists:
                    continue
                change = LegalChange(
                    title=title,
                    description=f"Automatic live check on {today} (similarity {info['score']}). Compare with the official text before relying on this section.",
                    affected_section_id=by_number[number].id, source_id=src.id, date=today, processed=False,
                )
                session.add(change)
                new_changes.append(change)

        results.append({
            "source_id": src.id, "title": src.title, "short_name": src.short_name, "url": src.url,
            "outcome": res["outcome"], "counts": res.get("counts") or {}, "sections": res.get("sections") or {},
            "changed_since_last": changed_since_last, "error": res.get("error"), "from_cache": res.get("from_cache", False),
        })

    await session.flush()
    return {"results": results, "new_changes": new_changes}


async def latest_status(session: AsyncSession) -> list[dict[str, Any]]:
    """Most recent check for every stored Act (or 'never checked')."""
    sources = (await session.execute(select(LegalSource).order_by(LegalSource.id))).scalars().all()
    out: list[dict[str, Any]] = []
    for src in sources:
        last = await _latest_check(session, src.id)
        flagged = []
        if last and last.details:
            flagged = [{"section_number": n, **info} for n, info in (last.details.get("sections") or {}).items()
                       if info.get("status") != "verified"]
        out.append({
            "source_id": src.id, "title": src.title, "short_name": src.short_name, "url": src.url, "law_status": src.status,
            "last_checked": last.checked_at.isoformat() if last and last.checked_at else None,
            "outcome": last.outcome if last else "never_checked",
            "counts": (last.counts or {}) if last else {},
            "changed_since_last": bool(last.changed_since_last) if last else False,
            "error": (last.details or {}).get("error") if last else None,
            "flagged": flagged,
        })
    return out
