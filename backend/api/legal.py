"""
backend/api/legal.py
────────────────────
Legal research endpoints:

  POST /api/legal/search                     hybrid statute search
  POST /api/legal/ask                        run the LangGraph research agent
  GET  /api/legal/laws/{source_id}           a statute with its sections
  GET  /api/legal/changes                    list legal changes
  POST /api/legal/changes                    add a (mock) legal change -> impacted clauses
  GET  /api/legal/changes/{id}/impact        impacted clauses for a change
  GET  /api/analysis/{run_id}/trace          execution trace of an agent run
  GET  /api/analysis/findings/{id}/trace     auditable chain for one risk finding

Routes only handle HTTP; heavy work runs in worker threads (retrieval / agent).
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.agents.graph import run_agent
from backend.agents.guard import sanitize_user_text
from backend.agents.llm import get_llm_client
from backend.agents.persistence import persist_trace
from backend.analysis.risk_engine import load_rules
from backend.api.schemas import (
    AskRequest,
    AskResponse,
    CreateLegalChangeRequest,
    FindingTraceResponse,
    LegalChangeImpactResponse,
    LegalChangeSchema,
    LegalSourceDetailSchema,
    SearchRequest,
    SearchResponse,
    SearchResultSchema,
    SectionSchema,
    TraceResponse,
    TraceStep,
)
from backend.database.models import (
    AgentRun,
    Clause,
    ClauseSectionLink,
    Contract,
    Evidence,
    LegalChange,
    LegalSource,
    RiskFinding,
    Section,
)
from backend.database.session import get_session
from backend.retrieval import factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/legal", tags=["Legal research"])
trace_router = APIRouter(prefix="/api/analysis", tags=["Trace"])


def _natural_key(number: str) -> tuple[int, str]:
    m = re.match(r"\d+", number)
    return (int(m.group()) if m else 10**6, number)


# ── POST /api/legal/search ─────────────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse, summary="Hybrid search over the statute corpus")
async def search(payload: SearchRequest) -> SearchResponse:
    clean, _ = sanitize_user_text(payload.query, max_len=500)
    retriever = await asyncio.to_thread(factory.get_retriever)
    results = await asyncio.to_thread(retriever.search, clean, payload.k, payload.mode)
    return SearchResponse(
        query=payload.query,
        mode=payload.mode,
        results=[SearchResultSchema(**r.to_dict()) for r in results],
    )


# ── POST /api/legal/ask ────────────────────────────────────────────────────────
@router.post("/ask", response_model=AskResponse, summary="Ask a legal question (agentic RAG workflow)")
async def ask(payload: AskRequest, session: AsyncSession = Depends(get_session)) -> AskResponse:
    ctx: dict[str, Any] = {}
    if payload.contract_id is not None:
        contract = (await session.execute(
            select(Contract).where(Contract.id == payload.contract_id).options(selectinload(Contract.clauses))
        )).scalar_one_or_none()
        if contract is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Contract {payload.contract_id} not found")
        ctx["contract_id"] = contract.id
        ctx["doc_type"] = contract.doc_type or "other"
        ctx["clauses"] = [
            {"clause_number": c.clause_number, "clause_label": c.clause_label, "heading": c.heading, "text": c.text}
            for c in sorted(contract.clauses, key=lambda c: c.clause_number)
        ]
    if payload.clause_text:
        ctx["clause_text"] = payload.clause_text
    if payload.intent:
        ctx["intent"] = payload.intent

    retriever = await asyncio.to_thread(factory.get_retriever)
    state = await asyncio.to_thread(run_agent, retriever, payload.query, llm=get_llm_client(), engine="auto", **ctx)

    run_id: Optional[int] = None
    try:
        run_id = await persist_trace(session, state)
    except Exception:  # never fail the answer because the trace could not be saved
        logger.exception("Could not persist agent trace")
        await session.rollback()

    return AskResponse(
        query=payload.query,
        intent=state.get("intent"),
        answer=state.get("answer", ""),
        confidence=state.get("confidence", "none"),
        evidence=state.get("evidence", []),
        trace=state.get("trace", []),
        workflow_engine=state.get("workflow_engine", "unknown"),
        agent_run_id=run_id,
    )


# ── GET /api/legal/laws/{source_id} ────────────────────────────────────────────
@router.get("/laws/{source_id}", response_model=LegalSourceDetailSchema, summary="A statute with all its sections")
async def get_law(source_id: int, session: AsyncSession = Depends(get_session)) -> LegalSourceDetailSchema:
    src = (await session.execute(
        select(LegalSource).where(LegalSource.id == source_id).options(selectinload(LegalSource.sections))
    )).scalar_one_or_none()
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Legal source {source_id} not found")
    sections = sorted(src.sections, key=lambda s: _natural_key(s.section_number))
    label = src.short_name or src.title
    return LegalSourceDetailSchema(
        id=src.id, title=src.title, short_name=src.short_name, source_type=src.source_type,
        jurisdiction=src.jurisdiction, status=src.status, citation=src.citation,
        retrieved_on=src.retrieved_on, sections_count=len(sections),
        sections=[
            SectionSchema(id=s.id, source_id=s.source_id, section_number=s.section_number, heading=s.heading,
                          text=s.text, notes=s.notes, citation_str=f"{label} s.{s.section_number}")
            for s in sections
        ],
    )


# ── Legal changes (simple Legal Change Impact feature) ─────────────────────────
_CITE_RE = re.compile(r"^\s*([\w\-]+)\s+s\.?\s*([\w\-]+)\s*$", re.IGNORECASE)


async def _impacted_clauses(session: AsyncSession, change: LegalChange) -> list[dict[str, Any]]:
    if change.affected_section_id is None:
        return []
    rows = (await session.execute(
        select(ClauseSectionLink, Clause, Contract)
        .join(Clause, ClauseSectionLink.clause_id == Clause.id)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(ClauseSectionLink.section_id == change.affected_section_id)
        .order_by(Contract.id, Clause.clause_number)
    )).all()
    out: list[dict[str, Any]] = []
    for link, clause, contract in rows:
        label = clause.clause_label or clause.clause_number
        out.append({
            "contract_id": contract.id,
            "contract_title": contract.title,
            "clause_id": clause.id,
            "clause_number": clause.clause_number,
            "clause_label": clause.clause_label,
            "clause_heading": clause.heading,
            "link_type": link.link_type,
            "confidence": link.confidence,
            "alert": (f"Legal Change Alert: Clause {label} of '{contract.title}' may be affected by "
                      f"'{change.title}'. The clause should be reviewed in light of this development."),
        })
    return out


@router.get("/changes", response_model=list[LegalChangeSchema], summary="List legal changes (newest first)")
async def list_changes(session: AsyncSession = Depends(get_session)) -> list[LegalChangeSchema]:
    rows = (await session.execute(select(LegalChange).order_by(LegalChange.id.desc()))).scalars().all()
    return [LegalChangeSchema.model_validate(r) for r in rows]


@router.post("/changes", response_model=LegalChangeImpactResponse, status_code=status.HTTP_201_CREATED,
             summary="Add a legal change and find the clauses it may affect")
async def create_change(payload: CreateLegalChangeRequest,
                        session: AsyncSession = Depends(get_session)) -> LegalChangeImpactResponse:
    section: Optional[Section] = None
    if payload.affected_section_id is not None:
        section = (await session.execute(select(Section).where(Section.id == payload.affected_section_id))).scalar_one_or_none()
        if section is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="affected_section_id not found")
    elif payload.citation:
        m = _CITE_RE.match(payload.citation)
        if not m:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="citation must look like 'ICA1872 s.27'")
        section = (await session.execute(
            select(Section).join(LegalSource, Section.source_id == LegalSource.id)
            .where(func.lower(LegalSource.short_name) == m.group(1).lower(),
                   func.lower(Section.section_number) == m.group(2).lower())
        )).scalars().first()
        if section is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"No section found for '{payload.citation}'")

    change = LegalChange(
        title=payload.title, description=payload.description,
        affected_section_id=section.id if section else None,
        source_id=section.source_id if section else payload.source_id,
        date=payload.date or date.today().isoformat(), processed=False,
    )
    session.add(change)
    await session.flush()
    impacted = await _impacted_clauses(session, change)
    change.processed = True  # impact analysis for this change has been computed
    await session.commit()
    return LegalChangeImpactResponse(change_id=change.id, title=change.title,
                                     affected_section_id=change.affected_section_id, impacted_clauses=impacted)


@router.get("/changes/{change_id}/impact", response_model=LegalChangeImpactResponse, summary="Clauses affected by a change")
async def change_impact(change_id: int, session: AsyncSession = Depends(get_session)) -> LegalChangeImpactResponse:
    change = (await session.execute(select(LegalChange).where(LegalChange.id == change_id))).scalar_one_or_none()
    if change is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Legal change {change_id} not found")
    return LegalChangeImpactResponse(change_id=change.id, title=change.title,
                                     affected_section_id=change.affected_section_id,
                                     impacted_clauses=await _impacted_clauses(session, change))


# ── Trace endpoints ────────────────────────────────────────────────────────────
@trace_router.get("/{run_id}/trace", response_model=TraceResponse, summary="Execution trace of an agent run")
async def run_trace(run_id: int, session: AsyncSession = Depends(get_session)) -> TraceResponse:
    rows = (await session.execute(select(AgentRun).where(AgentRun.run_id == run_id).order_by(AgentRun.id))).scalars().all()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Agent run {run_id} not found")
    return TraceResponse(run_id=run_id, steps=[TraceStep.model_validate(r) for r in rows])


@trace_router.get("/findings/{finding_id}/trace", response_model=FindingTraceResponse,
                  summary="Why did the system reach this finding? (auditable evidence chain)")
async def finding_trace(finding_id: int, session: AsyncSession = Depends(get_session)) -> FindingTraceResponse:
    f = (await session.execute(
        select(RiskFinding).where(RiskFinding.id == finding_id).options(
            selectinload(RiskFinding.clause),
            selectinload(RiskFinding.evidence).selectinload(Evidence.section).selectinload(Section.source),
        )
    )).scalar_one_or_none()
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Finding {finding_id} not found")

    rule = next((r for r in load_rules()["rules"] if r["id"] == f.rule_id), None)
    steps: list[dict[str, Any]] = []

    if f.clause is not None:
        c = f.clause
        steps.append({"stage": "Contract clause", "title": f"Clause {c.clause_label or c.clause_number}: {c.heading or '(no heading)'}",
                      "detail": {"text": c.text[:700], "detected_types": c.clause_types or [c.clause_type], "page": c.page}})
    else:
        steps.append({"stage": "Contract clause", "title": "Contract-level check (no single clause)",
                      "detail": {"note": "This finding concerns something not found in the document."}})

    steps.append({"stage": "Detected legal issue", "title": f.title or f.rule_id,
                  "detail": {"rule_id": f.rule_id, "category": f.category, "matched_text": f.matched_text}})

    if rule and rule.get("expected_section"):
        exp = rule["expected_section"]
        steps.append({"stage": "Research query", "title": rule["retrieval_query"],
                      "detail": {"mapped_provision": f"{exp['act_keyword']} s.{exp['number']}", "method": "hybrid retrieval (BM25 + embeddings)"}})
    else:
        steps.append({"stage": "Research query", "title": "No statutory provision mapped to this finding",
                      "detail": {"note": "The finding is based on the clause wording alone."}})

    if f.evidence:
        for e in f.evidence:
            sec, src = e.section, (e.section.source if e.section else None)
            steps.append({"stage": "Applicable law", "title": src.title if src else "Unknown source",
                          "detail": {"citation": src.citation if src else None, "law_status": src.status if src else None,
                                     "retrieved_on": src.retrieved_on if src else None, "url": src.url if src else None}})
            steps.append({"stage": "Relevant section",
                          "title": f"{(src.short_name or src.title) if src else ''} s.{sec.section_number}" if sec else "Unknown section",
                          "detail": {"heading": sec.heading if sec else None}})
            steps.append({"stage": "Evidence", "title": "Verbatim quote from the stored statute text",
                          "detail": {"quote": e.quote, "support": e.support, "verification": e.verification_status}})
            note = ("Law status must be confirmed on India Code." if src and src.status == "verify_current_status"
                    else "Version history is not tracked in this release; the status shown is as loaded.")
            steps.append({"stage": "Temporal check", "title": f"Status: {src.status if src else 'unknown'}", "detail": {"note": note}})
    else:
        steps.append({"stage": "Evidence", "title": "Source verification required.",
                      "detail": {"evidence_status": f.evidence_status}})

    steps.append({"stage": "Finding", "title": f"{f.risk_level.upper()} — review priority (not a legal determination)",
                  "detail": {"reason": f.reason, "recommendation": f.review_recommendation}})
    return FindingTraceResponse(finding_id=f.id, contract_id=f.contract_id, steps=steps)
