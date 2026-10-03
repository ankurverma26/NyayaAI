"""
backend/api/schemas.py
──────────────────────
Pydantic v2 schemas for NyayaAI API request and response bodies.

All field names follow snake_case per project conventions.
The disclaimer field appears on every analysis / legal response.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.analysis.risk_engine import DISCLAIMER  # single source of truth for the disclaimer text

# ── Shared ────────────────────────────────────────────────────────────────────


class OkResponse(BaseModel):
    """Simple acknowledgement."""
    ok: bool = True
    message: str = ""


# ── Clauses ───────────────────────────────────────────────────────────────────


class ClauseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    clause_number: int            # sequence number (the contract's own numbering is clause_label)
    heading: Optional[str] = None
    text: str
    clause_type: Optional[str] = None
    clause_types: Optional[list[str]] = None
    clause_label: Optional[str] = None
    page: Optional[int] = None


# ── Contracts ─────────────────────────────────────────────────────────────────


class ContractSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    doc_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    created_at: datetime
    document_id: Optional[int] = None
    clauses_count: Optional[int] = 0


class ContractDetailSchema(ContractSummarySchema):
    clauses: list[ClauseSchema] = []


# ── Ingestion ─────────────────────────────────────────────────────────────────


class IngestTextRequest(BaseModel):
    text: str
    title: Optional[str] = "Untitled Contract"
    filename: Optional[str] = "contract.txt"
    jurisdiction: Optional[str] = "india"


class IngestionResponse(BaseModel):
    document_id: int
    contract_id: int
    title: str
    doc_type: Optional[str] = None
    filename: str
    file_type: str
    clauses_count: int
    message: str


# ── Evidence ──────────────────────────────────────────────────────────────────


class EvidenceItemSchema(BaseModel):
    """A single evidence record with statutory citation."""
    id: int
    section_id: Optional[int] = None
    citation: Optional[str] = None
    act: Optional[str] = None
    section_number: Optional[str] = None
    heading: Optional[str] = None
    law_status: Optional[str] = None
    quote: str
    support: str                  # supports | contradicts | neutral
    verification: str             # verified | source_verification_required


class EvidenceListResponse(BaseModel):
    contract_id: int
    findings_count: int
    evidence: list[dict[str, Any]]
    disclaimer: str = DISCLAIMER


# ── Risk Findings ─────────────────────────────────────────────────────────────


class FindingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: Optional[str] = None
    title: Optional[str] = None
    risk_level: str
    category: Optional[str] = None
    reason: str
    recommendation: Optional[str] = None
    status: str
    evidence_status: Optional[str] = None
    matched_text: Optional[str] = None
    clause_id: Optional[int] = None
    clause_number: Optional[int] = None
    clause_heading: Optional[str] = None
    clause_label: Optional[str] = None
    evidence: list[dict[str, Any]] = []


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


class FindingTraceResponse(BaseModel):
    """Auditable chain: clause -> issue -> research query -> law -> section -> evidence -> finding."""
    finding_id: int
    contract_id: int
    steps: list[dict[str, Any]]
    disclaimer: str = DISCLAIMER


# ── Statutes ──────────────────────────────────────────────────────────────────


class SectionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    section_number: str
    heading: Optional[str] = None
    text: str
    notes: Optional[str] = None
    citation_str: Optional[str] = None


class LegalSourceSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    short_name: Optional[str] = None
    source_type: str
    jurisdiction: str
    status: str
    citation: Optional[str] = None
    retrieved_on: Optional[str] = None
    sections_count: Optional[int] = 0


class LegalSourceDetailSchema(LegalSourceSummarySchema):
    sections: list[SectionSchema] = []


# ── Legal search / ask ────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    k: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(hybrid|bm25|dense)$")


class SearchResultSchema(BaseModel):
    section_id: int
    citation: str
    act: str
    section_number: str
    heading: Optional[str] = None
    text: str
    status: Optional[str] = None
    score: float
    bm25_score: float
    dense_score: float
    boosted: bool
    contributed_by: list[str]


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: list[SearchResultSchema]
    disclaimer: str = DISCLAIMER


class AskRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    contract_id: Optional[int] = None
    clause_text: Optional[str] = Field(default=None, max_length=8000)
    intent: Optional[str] = Field(
        default=None,
        pattern="^(legal_qa|clause_explain|contract_risk_audit)$",
    )


class AskResponse(BaseModel):
    query: str
    intent: Optional[str] = None
    answer: str
    confidence: str
    evidence: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    workflow_engine: str
    agent_run_id: Optional[int] = None
    disclaimer: str = DISCLAIMER


# ── Agent run / trace ─────────────────────────────────────────────────────────


class TraceStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step: str
    status: str
    detail: Optional[dict[str, Any]] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    query: Optional[str] = None
    contract_id: Optional[int] = None


class TraceResponse(BaseModel):
    run_id: int
    steps: list[TraceStep]


# ── Legal changes ─────────────────────────────────────────────────────────────


class LegalChangeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    affected_section_id: Optional[int] = None
    source_id: Optional[int] = None
    date: Optional[str] = None
    processed: bool


class CreateLegalChangeRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=512)
    description: Optional[str] = None
    affected_section_id: Optional[int] = None
    citation: Optional[str] = Field(
        default=None,
        description="Alternative to affected_section_id, e.g. 'ICA1872 s.27'",
    )
    source_id: Optional[int] = None
    date: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO date YYYY-MM-DD",
    )


class LegalChangeImpactResponse(BaseModel):
    change_id: int
    title: str
    affected_section_id: Optional[int]
    impacted_clauses: list[dict[str, Any]]
    disclaimer: str = DISCLAIMER
