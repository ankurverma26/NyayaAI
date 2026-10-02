"""
tests/test_api_contracts.py
───────────────────────────
API integration tests for contract upload, text ingestion,
contract viewing, and statutes browsing.
"""
from __future__ import annotations

import io
# pyrefly: ignore [missing-import]
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.models import Base
from backend.database.session import get_session
from backend.main import app
from scripts.load_laws import load_file


@pytest.fixture
def sqlite_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    return engine


@pytest.fixture
async def async_client(sqlite_engine):
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory

    app.dependency_overrides.clear()
    await sqlite_engine.dispose()


@pytest.mark.asyncio
async def test_ingest_raw_text_api(async_client):
    client, _ = async_client
    payload = {
        "title": "Consultancy Agreement",
        "text": (
            "Clause 1. Services\nConsultant will provide AI services.\n\n"
            "Clause 2. Non-Competition\nConsultant shall not compete for 3 years.\n\n"
            "Clause 3. Indemnity\nConsultant will indemnify client."
        ),
        "filename": "consultancy.txt",
        "jurisdiction": "india",
    }
    resp = await client.post("/api/contracts/text", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["contract_id"] > 0
    assert data["title"] == "Consultancy Agreement"
    assert data["clauses_count"] == 3


@pytest.mark.asyncio
async def test_upload_contract_file_api(async_client):
    client, _ = async_client
    content = b"Clause 1. Scope of Work\nDelivery of software.\n\nClause 2. Payment Terms\nINR 50,000 monthly."
    files = {"file": ("vendor_agreement.txt", io.BytesIO(content), "text/plain")}
    data = {"title": "Vendor Contract", "jurisdiction": "india"}

    resp = await client.post("/api/contracts/upload", files=files, data=data)
    assert resp.status_code == 201
    res = resp.json()
    assert res["contract_id"] > 0
    assert res["clauses_count"] == 2


@pytest.mark.asyncio
async def test_list_and_get_contract_api(async_client):
    client, _ = async_client

    # Ingest one contract
    payload = {
        "title": "NDA Contract",
        "text": "Clause 1. Confidentiality\nKeep all confidential data safe.\n\nClause 2. Governing Law\nGoverned by Indian law.",
    }
    create_resp = await client.post("/api/contracts/text", json=payload)
    contract_id = create_resp.json()["contract_id"]

    # List contracts
    list_resp = await client.get("/api/contracts")
    assert list_resp.status_code == 200
    contracts = list_resp.json()
    assert len(contracts) >= 1
    assert any(c["id"] == contract_id for c in contracts)

    # Get single contract
    detail_resp = await client.get(f"/api/contracts/{contract_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["title"] == "NDA Contract"
    assert len(detail["clauses"]) == 2
    assert detail["clauses"][0]["clause_number"] == 1

    # Get clauses endpoint
    clauses_resp = await client.get(f"/api/contracts/{contract_id}/clauses")
    assert clauses_resp.status_code == 200
    clauses = clauses_resp.json()
    assert len(clauses) == 2


@pytest.mark.asyncio
async def test_statutes_api(async_client, tmp_path):
    client, factory = async_client

    # Seed one test statute
    from pathlib import Path
    law_file = tmp_path / "test_law.json"
    law_file.write_text(
        '{"act": "Test Contract Act", "short_name": "TCA", "year": 2024, "sections": [{"section_number": "1", "heading": "Title", "text": "Verbatim text"}]}',
        encoding="utf-8",
    )
    async with factory() as s:
        await load_file(s, law_file)

    statutes_resp = await client.get("/api/statutes")
    assert statutes_resp.status_code == 200
    statutes = statutes_resp.json()
    assert len(statutes) >= 1
    statute_id = statutes[0]["id"]

    detail_resp = await client.get(f"/api/statutes/{statute_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["title"] == "Test Contract Act"
    assert len(detail["sections"]) == 1
