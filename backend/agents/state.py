"""Shared state for the NyayaAI research workflow (JSON-serialisable)."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # inputs
    query: str
    contract_id: Optional[int]
    clause_text: Optional[str]          # a single clause to explain
    clauses: list[dict[str, Any]]       # contract clauses for an audit
    doc_type: str
    intent: str                         # legal_qa | clause_explain | contract_risk_audit
    # working data
    guard_flags: list[str]
    findings: list[dict[str, Any]]      # rule-engine findings (explain / audit)
    research_plan: list[dict[str, Any]]
    retrieved: list[dict[str, Any]]
    verified_evidence: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    retry_count: int
    # outputs
    evidence: list[dict[str, Any]]      # evidence objects {claim, evidence[], confidence, conflicts[]}
    answer: str
    confidence: str
    trace: list[dict[str, Any]]
    errors: list[str]


def new_state(
    query: str = "",
    contract_id: Optional[int] = None,
    clause_text: Optional[str] = None,
    clauses: Optional[list[dict[str, Any]]] = None,
    doc_type: str = "other",
    intent: Optional[str] = None,
) -> AgentState:
    state: AgentState = {
        "query": query, "contract_id": contract_id, "clause_text": clause_text,
        "clauses": clauses or [], "doc_type": doc_type, "retry_count": 0,
        "trace": [], "errors": [], "retrieved": [], "verified_evidence": [], "research_plan": [],
    }
    if intent:
        state["intent"] = intent
    return state
