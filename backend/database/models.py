"""
backend/database/models.py
──────────────────────────
SQLAlchemy 2.x ORM models for NyayaAI.

Design decisions:
- Uses the new-style `DeclarativeBase` + `Mapped`/`mapped_column` API (SQLAlchemy 2.0+).
- All PKs are auto-incrementing integers (simple, portable, no UUID overhead on SQLite).
- JSON columns use `sqlalchemy.JSON` — SQLite stores as TEXT, PostgreSQL uses JSONB.
- `created_at` / timestamps default to `func.now()` at the DB level for portability.
- All FKs are nullable where semantically optional.
- `clause_section_links` is a first-class model (not just an association table) so it
  can carry metadata for the future Legal Impact Graph (confidence, link_type).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Base ───────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared declarative base — all models inherit from this."""
    pass


# ── Users ──────────────────────────────────────────────────────────────────────

class User(Base):
    """
    Minimal user record for future multi-tenant isolation.
    Authentication is out of scope for the current mini-project phase;
    this table is reserved so foreign keys exist from day one.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="user")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="user")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="user")


# ── Documents ─────────────────────────────────────────────────────────────────

class Document(Base):
    """
    Raw uploaded file record (PDF, DOCX, TXT).
    Decoupled from Contract so the same file can produce multiple analyses.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)   # pdf | docx | txt
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="documents")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="document")


# ── Contracts ─────────────────────────────────────────────────────────────────

class Contract(Base):
    """
    A parsed contract derived from a Document.
    doc_type: employment | service | nda | loan | lease | other
    jurisdiction: india | uk | us | …  (jurisdiction-agnostic design)
    """
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="contracts")
    document: Mapped[Optional["Document"]] = relationship(back_populates="contracts")
    clauses: Mapped[list["Clause"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="contract")


# ── Clauses ───────────────────────────────────────────────────────────────────

class Clause(Base):
    """
    A single clause extracted from a Contract.
    clause_type: indemnity | non_compete | ip_assignment | termination | payment | other
    """
    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    clause_number: Mapped[str] = mapped_column(String(40), nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    clause_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clause_label: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    clause_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="clauses")
    risk_findings: Mapped[list["RiskFinding"]] = relationship(
        back_populates="clause", cascade="all, delete-orphan"
    )
    section_links: Mapped[list["ClauseSectionLink"]] = relationship(
        back_populates="clause", cascade="all, delete-orphan"
    )


# ── Legal Sources ─────────────────────────────────────────────────────────────

class LegalSource(Base):
    """
    A statute, regulation, or judgment loaded from data/laws/ or data/judgments/.

    source_type : act | regulation | judgment | notification | circular
    authority   : parliament | state_legislature | supreme_court | high_court | tribunal
    status      : in_force | amended | repealed | draft
    hash        : SHA-256 of the source file (change detection for re-indexing)
    """
    __tablename__ = "legal_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    authority: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(60), nullable=False, default="india")
    court: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)        # ISO date string
    effective_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    retrieved_on: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # YYYY-MM-DD
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="in_force")
    citation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sections: Mapped[list["Section"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="source")
    legal_changes: Mapped[list["LegalChange"]] = relationship(back_populates="source")


# ── Sections ──────────────────────────────────────────────────────────────────

class Section(Base):
    """
    A single section / provision within a LegalSource.
    section_number: "27", "10A", "Schedule II" — stored as text for flexibility.
    """
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("legal_sources.id", ondelete="CASCADE"), nullable=False
    )
    section_number: Mapped[str] = mapped_column(String(40), nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source: Mapped["LegalSource"] = relationship(back_populates="sections")
    risk_findings: Mapped[list["RiskFinding"]] = relationship(back_populates="section")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="section")
    clause_links: Mapped[list["ClauseSectionLink"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )
    legal_changes: Mapped[list["LegalChange"]] = relationship(
        back_populates="affected_section"
    )

    @property
    def citation_str(self) -> str:
        """Display format: '{short_name} s.{section_number}', e.g. 'ICA1872 s.27'."""
        if self.source and self.source.short_name:
            return f"{self.source.short_name} s.{self.section_number}"
        return f"s.{self.section_number}"



# ── Risk Findings ─────────────────────────────────────────────────────────────

class RiskFinding(Base):
    """
    A risk or issue flagged for a specific Clause by the risk engine or LLM.

    risk_level  : high | medium | low | info
    category    : non_compete | ip | indemnity | termination | payment | jurisdiction | other
    status      : open | reviewed | dismissed | escalated
    reason      : always uses cautious language ("potential issue …", "requires review …")
    """
    __tablename__ = "risk_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )

    clause_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("clauses.id", ondelete="CASCADE"), nullable=True
    )
    rule_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    evidence_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    matched_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    category: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    review_recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    clause: Mapped[Optional["Clause"]] = relationship(back_populates="risk_findings")
    section: Mapped[Optional["Section"]] = relationship(back_populates="risk_findings")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


# ── Evidence ──────────────────────────────────────────────────────────────────

class Evidence(Base):
    """
    A verbatim quote from a LegalSource section that supports a RiskFinding.
    If no evidence is found, no Evidence row is created and the UI shows
    "Source verification required." instead.

    support: "supports" | "contradicts" | "neutral"
    """
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("risk_findings.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("legal_sources.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    support: Mapped[str] = mapped_column(String(20), nullable=False, default="supports")
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="verified")

    finding: Mapped["RiskFinding"] = relationship(back_populates="evidence")
    source: Mapped["LegalSource"] = relationship(back_populates="evidence")
    section: Mapped[Optional["Section"]] = relationship(back_populates="evidence")


# ── Agent Runs ────────────────────────────────────────────────────────────────

class AgentRun(Base):
    """
    One execution of the LangGraph workflow.

    step   : plan | retrieve | verify | answer   (current LangGraph node)
    status : running | completed | failed
    detail : arbitrary JSON — stores node inputs/outputs for the execution trace UI
    """
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step: Mapped[str] = mapped_column(String(40), nullable=False, default="plan")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    contract: Mapped[Optional["Contract"]] = relationship(back_populates="agent_runs")
    user: Mapped[Optional["User"]] = relationship(back_populates="agent_runs")


# ── Legal Changes ─────────────────────────────────────────────────────────────

class LegalChange(Base):
    """
    Tracks amendments or notifications that may affect a Section.
    processed = True once the retrieval index has been updated.
    """
    __tablename__ = "legal_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_section_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("legal_sources.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    affected_section: Mapped[Optional["Section"]] = relationship(
        back_populates="legal_changes"
    )
    source: Mapped[Optional["LegalSource"]] = relationship(
        back_populates="legal_changes"
    )


# ── Clause–Section Links (Legal Impact Graph) ─────────────────────────────────

class ClauseSectionLink(Base):
    """
    Many-to-many between Clause and Section for the Legal Impact Graph.

    link_type  : supports | contradicts | governs | references | modifies
    confidence : 0.0–1.0 (retrieval score that produced this link)
    Created by the retrieval pipeline; consumed by the graph visualisation.
    """
    __tablename__ = "clause_section_links"
    __table_args__ = (
        UniqueConstraint("clause_id", "section_id", name="uq_clause_section"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clause_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clauses.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(String(40), nullable=False, default="governs")
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    clause: Mapped["Clause"] = relationship(back_populates="section_links")
    section: Mapped["Section"] = relationship(back_populates="clause_links")
