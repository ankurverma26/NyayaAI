"""Persist risk analysis for a stored contract (async DB layer).

Re-running analysis replaces the contract's previous findings, so it is safe to
call repeatedly (for example after new laws are loaded).
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.analysis.clause_classifier import classify_clause
from backend.analysis.risk_engine import ClauseInput, FindingDraft, analyze_clauses, summarize
from backend.database.models import (
    Clause,
    ClauseSectionLink,
    Contract,
    Evidence,
    RiskFinding,
    Section,
)


_LOCKS: dict[int, asyncio.Lock] = {}


async def analyze_contract(session: AsyncSession, contract_id: int, retriever: Any = None) -> dict[str, Any]:
    """Run the risk engine on a stored contract and save findings + evidence.

    Calls for the same contract are serialised, so two simultaneous requests
    (e.g. a double click) cannot write duplicate findings."""
    lock = _LOCKS.setdefault(contract_id, asyncio.Lock())
    async with lock:
        return await _analyze_contract_unlocked(session, contract_id, retriever)


async def _analyze_contract_unlocked(session: AsyncSession, contract_id: int, retriever: Any = None) -> dict[str, Any]:
    contract = (await session.execute(
        select(Contract).where(Contract.id == contract_id).options(selectinload(Contract.clauses))
    )).scalar_one_or_none()
    if contract is None:
        raise LookupError(f"Contract {contract_id} not found")

    if retriever is None:
        from backend.retrieval.factory import get_retriever
        retriever = await asyncio.to_thread(get_retriever)

    clauses = sorted(contract.clauses, key=lambda c: c.clause_number)
    inputs = []
    for c in clauses:
        types = c.clause_types or classify_clause(c.heading, c.text)
        inputs.append(ClauseInput(
            clause_number=c.clause_number, text=c.text, heading=c.heading,
            clause_label=c.clause_label, clause_id=c.id, clause_types=types,
        ))

    findings: list[FindingDraft] = await asyncio.to_thread(analyze_clauses, inputs, retriever, contract.doc_type or "other")

    # remove previous results for this contract
    old_ids = (await session.execute(select(RiskFinding.id).where(RiskFinding.contract_id == contract_id))).scalars().all()
    if old_ids:
        await session.execute(delete(Evidence).where(Evidence.finding_id.in_(old_ids)))
        await session.execute(delete(RiskFinding).where(RiskFinding.id.in_(old_ids)))
    clause_ids = [c.id for c in clauses]
    if clause_ids:
        await session.execute(delete(ClauseSectionLink).where(ClauseSectionLink.clause_id.in_(clause_ids)))

    linked: set[tuple[int, int]] = set()
    for f in findings:
        primary = f.evidence[0] if f.evidence else None
        row = RiskFinding(
            contract_id=contract_id, clause_id=f.clause_id, rule_id=f.rule_id, title=f.title,
            risk_level=f.risk_level, category=f.category, reason=f.reason,
            section_id=primary["section_id"] if primary else None, status="open",
            review_recommendation=f.recommendation, evidence_status=f.evidence_status,
            matched_text=f.matched_text,
        )
        session.add(row)
        await session.flush()
        for ev in f.evidence:
            session.add(Evidence(
                finding_id=row.id, source_id=ev["source_id"], section_id=ev["section_id"],
                quote=ev["quote"], support=ev["support"], verification_status=ev["verification"],
            ))
            if f.clause_id and (f.clause_id, ev["section_id"]) not in linked:
                linked.add((f.clause_id, ev["section_id"]))
                session.add(ClauseSectionLink(
                    clause_id=f.clause_id, section_id=ev["section_id"],
                    link_type="governs", confidence=ev.get("score"),
                ))
    await session.commit()

    out = summarize(findings)
    out.update({"contract_id": contract_id, "doc_type": contract.doc_type, "clauses_analyzed": len(clauses)})
    return out


async def list_issues(session: AsyncSession, contract_id: int) -> Optional[list[dict[str, Any]]]:
    """Findings with evidence, most severe first. None if the contract does not exist."""
    exists = (await session.execute(select(Contract.id).where(Contract.id == contract_id))).scalar_one_or_none()
    if exists is None:
        return None
    rows = (await session.execute(
        select(RiskFinding)
        .where(RiskFinding.contract_id == contract_id)
        .options(
            selectinload(RiskFinding.clause),
            selectinload(RiskFinding.evidence).selectinload(Evidence.section).selectinload(Section.source),
        )
    )).scalars().all()

    order = {"high": 3, "medium": 2, "low": 1, "info": 0}
    rows = sorted(rows, key=lambda r: (-order.get(r.risk_level, 0), r.clause.clause_number if r.clause else 10**6))
    issues: list[dict[str, Any]] = []
    for r in rows:
        issues.append({
            "id": r.id, "rule_id": r.rule_id, "title": r.title, "risk_level": r.risk_level,
            "category": r.category, "reason": r.reason, "recommendation": r.review_recommendation,
            "status": r.status, "evidence_status": r.evidence_status, "matched_text": r.matched_text,
            "clause_id": r.clause_id,
            "clause_number": r.clause.clause_number if r.clause else None,
            "clause_label": r.clause.clause_label if r.clause else None,
            "clause_heading": r.clause.heading if r.clause else None,
            "evidence": [{
                "section_id": e.section_id,
                "citation": e.section.citation_str if e.section else None,
                "act": e.section.source.title if e.section and e.section.source else None,
                "section_number": e.section.section_number if e.section else None,
                "heading": e.section.heading if e.section else None,
                "law_status": e.section.source.status if e.section and e.section.source else None,
                "quote": e.quote, "support": e.support, "verification": e.verification_status,
            } for e in r.evidence],
        })
    return issues
