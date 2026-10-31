"""API tests for the live source check (the download is faked; no internet needed)."""
from __future__ import annotations

from backend.legal_sync.fetch import FetchResult
from tests.test_analysis import FIXTURE
from tests.test_api_legal import _upload, client  # noqa: F401  (client is a pytest fixture)


def _official_text(change_27: bool) -> str:
    parts = []
    for r in FIXTURE:
        text = r.text
        if change_27 and r.section_number == "27" and "Contract" in r.act_title:
            text = "FIXTURE TEXT: an agreement permitting a person to follow any occupation is regarded in this fixture as a lawful bargain."
        parts.append(f"{r.section_number}. {r.heading}.\u2014{text}")
    return "\n".join(parts)


def _fake_fetch(changed: bool):
    return lambda url, force=False: FetchResult(True, _official_text(changed), status_code=200)


def test_status_before_any_check(client):
    rows = client.get("/api/legal/sync/status").json()
    assert rows and all(r["outcome"] == "never_checked" for r in rows)


def test_unchanged_official_text_is_verified_and_creates_no_alerts(client, monkeypatch):
    monkeypatch.setattr("backend.legal_sync.persist.fetch_text", _fake_fetch(False))
    r = client.post("/api/legal/sync/check", json={})
    assert r.status_code == 200, r.text
    assert all(x["outcome"] == "verified" for x in r.json()["results"]) and r.json()["alerts"] == []
    assert all(x["outcome"] == "verified" for x in client.get("/api/legal/sync/status").json())


def test_changed_official_text_raises_alert_for_linked_clause_and_updates_trace(client, monkeypatch):
    cid = _upload(client)
    client.post(f"/api/contracts/{cid}/analyze")
    monkeypatch.setattr("backend.legal_sync.persist.fetch_text", _fake_fetch(True))

    r = client.post("/api/legal/sync/check", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    contract_act = next(x for x in body["results"] if "Contract" in x["title"])
    assert contract_act["outcome"] == "needs_review" and contract_act["sections"]["27"]["status"] in ("changed", "minor_differences")
    assert any(c["clause_label"] == "7" for a in body["alerts"] for c in a["impacted_clauses"])

    status = next(x for x in client.get("/api/legal/sync/status").json() if "Contract" in x["title"])
    assert any(f["section_number"] == "27" for f in status["flagged"])

    again = client.post("/api/legal/sync/check", json={}).json()   # same day: no duplicate alerts
    assert again["alerts"] == []

    issues = client.get(f"/api/contracts/{cid}/issues").json()["issues"]
    high = next(i for i in issues if i["rule_id"] == "R001_post_employment_non_compete")
    steps = client.get(f"/api/analysis/findings/{high['id']}/trace").json()["steps"]
    temporal = next(s for s in steps if s["stage"] == "Temporal check")
    assert "last_live_check" in temporal["detail"]


def test_unreachable_source_is_reported_not_raised(client, monkeypatch):
    monkeypatch.setattr("backend.legal_sync.persist.fetch_text", lambda url, force=False: FetchResult(False, error="offline"))
    r = client.post("/api/legal/sync/check", json={})
    assert r.status_code == 200 and all(x["outcome"] == "unreachable" for x in r.json()["results"])
