"""Compare stored statute sections with the text of the official Act.

Why not simple string matching? The official PDF has page numbers, footnotes
("1. Subs. by Act 3 of 1951 ...") and footnote markers ("1[India]") mixed into the text,
so even an unchanged section never matches exactly. Instead we measure how much of the
stored section still appears in the official text, using overlapping word groups
(shingles). Removing, rewording or omitting text lowers the score.

Limits: this detects text that was removed, changed or marked omitted/repealed. Text
*added* to a section is only noticed through the document-level fingerprint.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

SHINGLE = 4            # words per overlapping group
VERIFIED_MIN = 0.99    # essentially every word group of the stored text is found in the official text
MINOR_MIN = 0.85       # below VERIFIED_MIN but above this: a few words differ (PDF artefacts or a small edit)

_PAGE_NUMBER = re.compile(r"(?m)^\s*\d{1,3}\s*$")
_FOOTNOTE_LINE = re.compile(
    r"(?m)^\s*\d{1,2}\s*\.\s+(?:Subs\.|Ins\.|Rep\.|Added|Omitted|The words|See\b|Cf\.|C\.f\.|For\b|Now\b|Vide\b|Re-numbered|Sub-section|Clause|This\b).*$"
)
_MARKERS = re.compile(r"\d{1,2}\s*\[|\]|\*+")
_WORD = re.compile(r"[a-z0-9]+")


def clean(text: str) -> str:
    """Remove page numbers, footnote lines and footnote markers."""
    text = _PAGE_NUMBER.sub(" ", text)
    text = _FOOTNOTE_LINE.sub(" ", text)
    return _MARKERS.sub(" ", text)


def words(text: str) -> list[str]:
    return _WORD.findall(clean(text).lower().replace("\u2019", "'"))


def shingles(tokens: list[str], n: int = SHINGLE) -> set[tuple[str, ...]]:
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def fingerprint(live_text: str) -> str:
    """Stable hash of the official text (ignores page numbers, footnotes, spacing)."""
    return hashlib.sha256(" ".join(words(live_text)).encode("utf-8")).hexdigest()


def containment(stored_text: str, live_shingles: set[tuple[str, ...]]) -> float:
    """Share (0..1) of the stored section's word groups that appear in the official text."""
    stored = shingles(words(stored_text))
    if not stored:
        return 0.0
    return len(stored & live_shingles) / len(stored)


def missing_examples(stored_text: str, live_shingles: set[tuple[str, ...]], limit: int = 3) -> list[str]:
    """Short snippets of the stored text that were NOT found in the official text (to show what differs)."""
    toks = words(stored_text)
    out: list[str] = []
    i = 0
    while i <= len(toks) - SHINGLE and len(out) < limit:
        if tuple(toks[i:i + SHINGLE]) not in live_shingles:
            out.append(" ".join(toks[i:i + SHINGLE + 3]))
            i += SHINGLE + 3
        else:
            i += 1
    return out


def omitted_marker(live_text: str, number: str) -> bool:
    """True if the official text shows the section as omitted / repealed ('43A. [Omitted by ...]')."""
    pattern = rf"(?m)^\s*\[?\s*{re.escape(number)}\s*\.\s*\[?\s*(?:omitted|repealed|rep\.)"
    return re.search(pattern, live_text, re.IGNORECASE) is not None


def verify_section(number: str, stored_text: str, live_text: str, live_shingles: set[tuple[str, ...]]) -> dict[str, Any]:
    score = containment(stored_text, live_shingles)
    if omitted_marker(live_text, number) and score < VERIFIED_MIN:
        status = "omitted_or_repealed"
    elif score >= VERIFIED_MIN:
        status = "verified"
    elif score >= MINOR_MIN:
        status = "minor_differences"
    else:
        status = "changed"
    result: dict[str, Any] = {"section_number": number, "status": status, "score": round(score, 3)}
    if status != "verified":
        result["missing_examples"] = missing_examples(stored_text, live_shingles)
    return result


def verify_act(sections: list[tuple[str, str]], live_text: str) -> dict[str, Any]:
    """sections: [(section_number, stored_text), ...]. Returns per-section results and an overall outcome."""
    live_sh = shingles(words(live_text))
    results = [verify_section(num, txt, live_text, live_sh) for num, txt in sections]
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    needs_review = counts.get("changed", 0) + counts.get("omitted_or_repealed", 0) > 0
    return {
        "outcome": "needs_review" if needs_review else "verified",
        "counts": counts,
        "sections": {r["section_number"]: {k: v for k, v in r.items() if k != "section_number"} for r in results},
        "fingerprint": fingerprint(live_text),
    }
