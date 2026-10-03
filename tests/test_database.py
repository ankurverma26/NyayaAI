"""
tests/test_database.py
───────────────────────
Tests for:
  - Database initialisation (create_all)
  - All ORM models (CRUD round-trips)
  - load_laws seed script (dry-run + real insert + idempotency)

Uses in-memory SQLite so no files are written to disk.
Each test gets its own engine + fresh tables to avoid order-dependence.
Run with: pytest tests/test_database.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import (
    Base,
    AgentRun,
    Clause,
    ClauseSectionLink,
    Contract,
    Document,
    Evidence,
    LegalChange,
    LegalSource,
    RiskFinding,
    Section,
    User,
)
from scripts.load_laws import load_file, _is_placeholder, _validate

# ── Shared in-memory URL ───────────────────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_CONNECT_ARGS = {"check_same_thread": False}


async def _make_engine():
    """Create a fresh async engine with all tables."""
    eng = create_async_engine(TEST_DB_URL, connect_args=_CONNECT_ARGS)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return eng


# ── Reusable fixtures (function scope — compatible with pytest-asyncio) ────────

@pytest_asyncio.fixture
async def engine():
    eng = await _make_engine()
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Yields an uncommitted session; rolls back after each test."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


# ── Helper ─────────────────────────────────────────────────────────────────────

def _make_law_file(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "test_act.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ── Sample law data ────────────────────────────────────────────────────────────

VALID_LAW: dict = {
    "act": "Test Contracts Act",
    "short_name": "TCA2024",
    "year": 2024,
    "citation": "Act No. 1 of 2024",
    "url": "https://example.com/tca2024",
    "status": "in_force",
    "jurisdiction": "india",
    "source_type": "act",
    "authority": "parliament",
    "sections": [
        {"number": "1", "heading": "Short title", "text": "This Act may be cited as the Test Contracts Act."},
        {"number": "2", "heading": "Definitions", "text": "In this Act, 'contract' means a lawful agreement."},
    ],
}

PLACEHOLDER_LAW: dict = {
    "act": "Sample Format",
    "year": 1872,
    "status": "in_force",
    "jurisdiction": "india",
    "source_type": "act",
    "sections": [
        {"number": "1", "heading": "Title", "text": "PLACEHOLDER — paste verbatim text here."},
    ],
}

INVALID_NO_ACT: dict = {
    "year": 2024,
    "status": "in_force",
    "sections": [{"number": "1", "text": "Something"}],
}

INVALID_EMPTY_SECTIONS: dict = {
    "act": "Empty Act",
    "year": 2024,
    "status": "in_force",
    "sections": [],
}


# ── DB initialisation ──────────────────────────────────────────────────────────

async def test_tables_exist(engine):
    """All 11 expected tables must exist after create_all."""
    expected = {
        "users", "documents", "contracts", "clauses",
        "legal_sources", "sections", "risk_findings",
        "evidence", "agent_runs", "legal_changes", "clause_section_links",
    }
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        actual = {row[0] for row in result}
    assert expected.issubset(actual), f"Missing tables: {expected - actual}"


# ── ORM round-trips ────────────────────────────────────────────────────────────

async def test_user_create_read(session: AsyncSession):
    user = User(email="test@example.com", display_name="Tester")
    session.add(user)
    await session.flush()
    assert user.id is not None

    fetched = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert fetched.email == "test@example.com"
    assert fetched.display_name == "Tester"


async def test_document_model(session: AsyncSession):
    doc = Document(filename="contract.pdf", file_type="pdf", file_path="/uploads/contract.pdf")
    session.add(doc)
    await session.flush()
    assert doc.id is not None


async def test_contract_clause_relationship(session: AsyncSession):
    contract = Contract(title="Employment Agreement", jurisdiction="india", doc_type="employment")
    session.add(contract)
    await session.flush()

    clause = Clause(
        contract_id=contract.id,
        clause_number=1,
        heading="Non-Compete",
        text="Employee shall not compete for 2 years.",
        clause_type="non_compete",
        page=3,
    )
    session.add(clause)
    await session.flush()

    fetched = (await session.execute(select(Clause).where(Clause.contract_id == contract.id))).scalar_one()
    assert fetched.clause_type == "non_compete"
    assert fetched.page == 3


async def test_legal_source_and_section(session: AsyncSession):
    source = LegalSource(
        title="Indian Contract Act",
        source_type="act",
        jurisdiction="india",
        status="in_force",
        version="1872",
        citation="Act No. 9 of 1872",
    )
    session.add(source)
    await session.flush()

    section = Section(
        source_id=source.id,
        section_number="27",
        heading="Agreement in restraint of trade, void",
        text="Every agreement by which any one is restrained...",
    )
    session.add(section)
    await session.flush()

    assert section.source_id == source.id
    assert section.section_number == "27"


async def test_risk_finding_and_evidence(session: AsyncSession):
    contract = Contract(title="Risk Test Contract")
    session.add(contract)
    await session.flush()

    clause = Clause(contract_id=contract.id, clause_number=1, text="Employee shall not compete.")
    session.add(clause)

    source = LegalSource(title="ICA Test", source_type="act", jurisdiction="india", status="in_force")
    session.add(source)
    await session.flush()

    section = Section(source_id=source.id, section_number="27", text="Verbatim statutory text.")
    session.add(section)
    await session.flush()

    finding = RiskFinding(
        contract_id=contract.id,
        clause_id=clause.id,
        risk_level="high",
        category="non_compete",
        reason="Potential issue: clause may be void under Section 27 ICA — requires review.",
        section_id=section.id,
        status="open",
    )
    session.add(finding)
    await session.flush()

    ev = Evidence(
        finding_id=finding.id,
        source_id=source.id,
        section_id=section.id,
        quote="Verbatim statutory text.",
        support="supports",
    )
    session.add(ev)
    await session.flush()

    assert finding.risk_level == "high"
    assert ev.support == "supports"
    # Safety: reason must use cautious language
    assert (
        "potential issue" in finding.reason.lower()
        or "requires review" in finding.reason.lower()
    )


async def test_agent_run_json_detail(session: AsyncSession):
    run = AgentRun(
        query="Is this non-compete clause enforceable?",
        step="plan",
        status="running",
        detail={"nodes": ["plan", "retrieve"], "current": "plan"},
    )
    session.add(run)
    await session.flush()

    fetched = (await session.execute(select(AgentRun).where(AgentRun.id == run.id))).scalar_one()
    assert fetched.detail["current"] == "plan"
    assert fetched.status == "running"


async def test_clause_section_link(session: AsyncSession):
    contract = Contract(title="Link Test Contract")
    session.add(contract)
    await session.flush()

    clause = Clause(contract_id=contract.id, clause_number=1, text="x")
    session.add(clause)

    source = LegalSource(title="Link Test Act", source_type="act", jurisdiction="india", status="in_force")
    session.add(source)
    await session.flush()

    section = Section(source_id=source.id, section_number="1", text="y")
    session.add(section)
    await session.flush()

    link = ClauseSectionLink(
        clause_id=clause.id,
        section_id=section.id,
        link_type="governs",
        confidence=0.91,
    )
    session.add(link)
    await session.flush()
    assert link.confidence == pytest.approx(0.91)
    assert link.link_type == "governs"


async def test_legal_change(session: AsyncSession):
    change = LegalChange(
        title="Amendment to Section 27",
        description="Prospective update.",
        processed=False,
    )
    session.add(change)
    await session.flush()
    assert change.processed is False


# ── load_laws helper unit tests ────────────────────────────────────────────────

def test_is_placeholder_true():
    assert _is_placeholder(PLACEHOLDER_LAW) is True


def test_is_placeholder_false():
    assert _is_placeholder(VALID_LAW) is False


def test_validate_valid():
    assert _validate(VALID_LAW, Path("x.json")) == []


def test_validate_missing_act():
    errors = _validate(INVALID_NO_ACT, Path("x.json"))
    assert any("act" in e for e in errors)


def test_validate_empty_sections():
    errors = _validate(INVALID_EMPTY_SECTIONS, Path("x.json"))
    assert any("sections" in e for e in errors)


# ── load_laws integration tests ────────────────────────────────────────────────

async def test_load_dry_run(engine, tmp_path):
    path = _make_law_file(tmp_path, VALID_LAW)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, path, dry_run=True)
    assert result["status"] == "ok"
    assert "DRY-RUN" in result["message"]
    assert result["sections_added"] == 2


async def test_load_real_insert(engine, tmp_path):
    law = {**VALID_LAW, "act": "Real Insert Act"}
    path = _make_law_file(tmp_path, law)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, path, dry_run=False)
    assert result["status"] == "ok"
    assert result["sections_added"] == 2

    # Verify rows persisted
    async with factory() as s:
        src = (await s.execute(select(LegalSource).where(LegalSource.title == "Real Insert Act"))).scalar_one()
        secs = (await s.execute(select(Section).where(Section.source_id == src.id))).scalars().all()
    assert len(secs) == 2
    assert secs[0].section_number == "1"
    assert secs[1].section_number == "2"


async def test_load_idempotent(engine, tmp_path):
    """Same file loaded twice: first ok, second skipped."""
    law = {**VALID_LAW, "act": "Idempotent Act"}
    path = _make_law_file(tmp_path, law)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        r1 = await load_file(s, path, dry_run=False)
    async with factory() as s:
        r2 = await load_file(s, path, dry_run=False)
    assert r1["status"] == "ok"
    assert r2["status"] == "skipped"


async def test_load_placeholder_skipped(engine, tmp_path):
    path = _make_law_file(tmp_path, PLACEHOLDER_LAW)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, path, dry_run=False)
    assert result["status"] == "skipped"
    assert "PLACEHOLDER" in result["message"]


async def test_load_invalid_json(engine, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, bad, dry_run=False)
    assert result["status"] == "error"
    assert "parse error" in result["message"]


async def test_load_with_section_number_key(engine, tmp_path):
    """Verify that 'section_number' key works in place of 'number'."""
    law = {
        "act": "Section Number Key Act",
        "short_name": "SNKA",
        "year": 2024,
        "sections": [
            {"section_number": "10", "heading": "Short Title", "text": "This is test law."},
        ],
    }
    path = _make_law_file(tmp_path, law)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, path, dry_run=False)
    assert result["status"] == "ok"
    assert result["sections_added"] == 1


async def test_load_skips_sample_format_filename(engine, tmp_path):
    """Rule 5: Any file with 'sample_format' in its name is skipped."""
    sample_path = tmp_path / "sample_format.json"
    sample_path.write_text(json.dumps(VALID_LAW), encoding="utf-8")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, sample_path, dry_run=False)
    assert result["status"] == "skipped"
    assert "sample_format" in result["message"]


async def test_load_ignores_underscore_keys_and_supports_retrieved_on(engine, tmp_path):
    """Rule 1 & 2: Top-level keys with '_' are ignored; retrieved_on and notes are saved."""
    law_with_meta = {
        **VALID_LAW,
        "act": "Metadata Test Act",
        "short_name": "MTA2024",
        "retrieved_on": "2024-05-15",
        "_schema_notes": {"act": "Should be ignored by loader"},
        "_custom_internal_field": 12345,
        "sections": [
            {
                "section_number": "1",
                "heading": "Title",
                "text": "Valid verbatim text.",
                "notes": "Important case note",
            }
        ],
    }
    path = _make_law_file(tmp_path, law_with_meta)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, path, dry_run=False)
    assert result["status"] == "ok"

    async with factory() as s:
        src = (
            await s.execute(
                select(LegalSource).where(LegalSource.title == "Metadata Test Act")
            )
        ).scalar_one()
        assert src.retrieved_on == "2024-05-15"
        sec = (
            await s.execute(select(Section).where(Section.source_id == src.id))
        ).scalar_one()
        assert sec.notes == "Important case note"
        assert sec.citation_str == "MTA2024 s.1"


async def test_load_status_verify_current_status(engine, tmp_path):
    """Rule 3: verify_current_status is an accepted status."""
    law = {
        **VALID_LAW,
        "act": "Status Test Act",
        "status": "verify_current_status",
    }
    path = _make_law_file(tmp_path, law)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await load_file(s, path, dry_run=False)
    assert result["status"] == "ok"

    async with factory() as s:
        src = (
            await s.execute(
                select(LegalSource).where(LegalSource.title == "Status Test Act")
            )
        ).scalar_one()
        assert src.status == "verify_current_status"


async def test_load_updates_section_on_text_hash_change(engine, tmp_path):
    """Rule 4: Section is updated if text hash changed; unchanged section is skipped."""
    law = {
        "act": "Hash Check Act",
        "short_name": "HCA2024",
        "year": 2024,
        "sections": [
            {"section_number": "1", "heading": "Old Heading", "text": "Original text."},
            {"section_number": "2", "heading": "Unchanged", "text": "Unchanged text."},
        ],
    }
    path = _make_law_file(tmp_path, law)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        r1 = await load_file(s, path, dry_run=False)
    assert r1["sections_loaded"] == 2
    assert r1["sections_skipped"] == 0

    # Modify Section 1 text, leave Section 2 identical
    updated_law = {
        **law,
        "sections": [
            {"section_number": "1", "heading": "New Heading", "text": "Amended text here."},
            {"section_number": "2", "heading": "Unchanged", "text": "Unchanged text."},
        ],
    }
    path.write_text(json.dumps(updated_law), encoding="utf-8")

    async with factory() as s:
        r2 = await load_file(s, path, dry_run=False)
    assert r2["status"] == "ok"
    assert r2["sections_loaded"] == 1  # 1 section updated
    assert r2["sections_skipped"] == 1  # 1 section skipped

    # Verify updated section text in DB
    async with factory() as s:
        src = (
            await s.execute(
                select(LegalSource).where(LegalSource.title == "Hash Check Act")
            )
        ).scalar_one()
        sec1 = (
            await s.execute(
                select(Section).where(
                    Section.source_id == src.id, Section.section_number == "1"
                )
            )
        ).scalar_one()
        assert sec1.text == "Amended text here."
        assert sec1.heading == "New Heading"


