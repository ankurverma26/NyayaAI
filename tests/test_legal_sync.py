"""Tests for live verification (no network: HTTP is faked, the PDF is generated in the test)."""
from __future__ import annotations

import io

from backend.legal_sync.compare import (
    fingerprint,
    omitted_marker,
    verify_act,
    verify_section,
    shingles,
    words,
)
from backend.legal_sync.fetch import FetchResult, fetch_text, pdf_bytes_to_text
from backend.legal_sync.service import check_source

# FIXTURE text (made up for the test, NOT real law) laid out like an India Code PDF:
# table-of-contents line, page numbers, footnote lines and footnote markers inside the section.
S1 = ("Every fixture agreement by which any one is restrained from exercising a lawful fixture profession, "
      "trade or business of any kind, is to that extent treated as void in this fixture.")
S2 = ("When a fixture contract has been broken, the party who suffers by such breach is entitled to receive "
      "compensation for any loss or damage caused to him thereby.")
LIVE = f"""FIXTURE ACT, 2000
ARRANGEMENT OF SECTIONS
1. Fixture restraint heading.
2. Fixture compensation heading.
43A. Fixture data heading.
THE FIXTURE ACT, 2000
1. Fixture restraint heading.—Every fixture agreement by which any one is restrained
from exercising a lawful fixture profession,
18
trade or business of any kind, is to that extent treated as void in this fixture.1[
1. Subs. by Act 3 of 1951, s. 3 and Sch., for certain words.
2. Fixture compensation heading.—When a fixture contract has been broken, the party who suffers
by such breach is entitled to receive compensation for any loss or damage
19
caused to him thereby.
43A. [Omitted by Act 9 of 2030, s. 44.]
"""
S3 = "Fixture body corporate handling sensitive data must keep reasonable security practices and pay compensation."


def test_clean_section_across_page_break_and_footnotes_is_verified():
    r = verify_act([("1", S1), ("2", S2)], LIVE)
    assert r["sections"]["1"]["status"] == "verified" and r["sections"]["2"]["status"] == "verified"
    assert r["outcome"] == "verified"


def test_changed_word_is_not_verified_and_shows_what_differs():
    altered = S1.replace("void", "valid")
    res = verify_section("1", altered, LIVE, shingles(words(LIVE)))
    assert res["status"] in ("minor_differences", "changed") and res["score"] < 0.99
    assert any("valid" in ex for ex in res["missing_examples"])


def test_omitted_section_is_detected():
    assert omitted_marker(LIVE, "43A") and not omitted_marker(LIVE, "2")
    r = verify_act([("43A", S3)], LIVE)
    assert r["sections"]["43A"]["status"] == "omitted_or_repealed" and r["outcome"] == "needs_review"


def test_fingerprint_ignores_page_numbers_and_spacing_but_not_text():
    spaced = LIVE.replace("\n18\n", "\n\n").replace("  ", " ")
    assert fingerprint(LIVE) == fingerprint(spaced)
    assert fingerprint(LIVE) != fingerprint(LIVE.replace("lawful", "unlawful"))


def test_pdf_text_extraction_and_end_to_end_check(tmp_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in (LIVE * 6).splitlines():  # repeat so the PDF has more than 200 words
        c.drawString(40, y, line[:110])
        y -= 12
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    text = pdf_bytes_to_text(buf.getvalue())
    assert "restrained from exercising" in " ".join(text.split())

    class Resp:
        status_code = 200
        content = buf.getvalue()

    fetched = fetch_text("https://example.test/act.pdf", cache_dir=tmp_path, http_get=lambda *a, **k: Resp())
    assert fetched.ok and not fetched.from_cache
    again = fetch_text("https://example.test/act.pdf", cache_dir=tmp_path, http_get=lambda *a, **k: 1 / 0)
    assert again.ok and again.from_cache                      # second call served from cache, no download
    out = check_source("https://example.test/act.pdf", [("2", S2)], fetcher=lambda url, force=False: fetched)
    assert out["outcome"] == "verified" and out["fingerprint"]


def test_unreachable_and_missing_url_do_not_crash(tmp_path):
    def boom(*a, **k):
        raise ConnectionError("offline")

    res = fetch_text("https://example.test/x.pdf", cache_dir=tmp_path, http_get=boom)
    assert not res.ok and "offline" in res.error
    assert check_source("https://example.test/x.pdf", [("1", S1)], fetcher=lambda u, force=False: res)["outcome"] == "unreachable"
    assert check_source(None, [("1", S1)])["outcome"] == "no_source_url"


def test_html_page_is_rejected_with_helpful_message(tmp_path):
    class Html:
        status_code = 200
        content = b"<html>landing page</html>"

    res = fetch_text("https://example.test/handle/1", cache_dir=tmp_path, http_get=lambda *a, **k: Html())
    assert not res.ok and "PDF" in res.error
