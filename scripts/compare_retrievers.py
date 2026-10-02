"""Compare BM25-only vs dense-only vs hybrid on a small hand-labelled query set.

Writes docs/retrieval_results.md (paste the table into your report).
Queries whose expected section is not in your loaded corpus are skipped.
NOTE: the query set is small and hand-labelled; report it as a sanity benchmark,
not a rigorous evaluation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.retrieval.factory import build_retriever  # noqa: E402

# (query, keyword expected in Act title, expected section number)
QUERIES: list[tuple[str, str, str]] = [
    ("restraint of trade after employment", "contract", "27"),
    ("agreement restraining a lawful profession or business", "contract", "27"),
    ("liquidated damages and penalty for breach", "contract", "74"),
    ("compensation for loss caused by breach of contract", "contract", "73"),
    ("agreement with unlawful object or consideration", "contract", "23"),
    ("agreement in restraint of legal proceedings", "contract", "28"),
    ("contract of indemnity", "contract", "124"),
    ("compensation for failure to protect sensitive personal data", "information technology", "43a"),
    ("punishment for disclosure of information in breach of lawful contract", "information technology", "72a"),
    ("arbitration agreement must be in writing", "arbitration", "7"),
    ("judicial authority refers parties to arbitration", "arbitration", "8"),
    ("appointment of arbitrators", "arbitration", "11"),
]


def rank_of(results, keyword: str, number: str) -> int | None:
    for i, r in enumerate(results, 1):
        if keyword in r.act.lower() and r.section_number.lower() == number:
            return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--out", default=str(ROOT / "docs" / "retrieval_results.md"))
    args = ap.parse_args()

    retriever = build_retriever(alpha=args.alpha)
    if not retriever.dense_available:
        print("WARNING: dense retriever unavailable (install sentence-transformers). "
              "Dense/hybrid columns will not be meaningful.")
    modes = ["bm25", "dense", "hybrid"]
    stats = {m: {"hit1": 0, "hit3": 0, "rr": 0.0} for m in modes}
    rows, used = [], 0
    present = {(r.act_title.lower(), r.section_number.lower()) for r in retriever.records}

    for query, kw, num in QUERIES:
        if not any(kw in t and n == num for t, n in present):
            rows.append(f"| {query} | {kw} s.{num} | skipped (not in corpus) | | |")
            continue
        used += 1
        cells = []
        for m in modes:
            res = retriever.search(query, k=len(retriever.records), mode=m, alpha=args.alpha)
            rk = rank_of(res, kw, num)
            cells.append(str(rk) if rk else "-")
            if rk == 1:
                stats[m]["hit1"] += 1
            if rk and rk <= 3:
                stats[m]["hit3"] += 1
            stats[m]["rr"] += (1.0 / rk) if rk else 0.0
        rows.append(f"| {query} | {kw} s.{num} | {cells[0]} | {cells[1]} | {cells[2]} |")

    lines = [
        "# Retrieval comparison (BM25 vs Dense vs Hybrid)",
        "",
        f"Queries evaluated: {used} (hand-labelled; small sanity benchmark). Hybrid alpha = {args.alpha}.",
        "",
        "| Query | Expected | BM25 rank | Dense rank | Hybrid rank |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "| Metric | BM25 | Dense | Hybrid |",
        "|---|---|---|---|",
    ]
    if used:
        lines += [
            f"| Hit@1 | {stats['bm25']['hit1']}/{used} | {stats['dense']['hit1']}/{used} | {stats['hybrid']['hit1']}/{used} |",
            f"| Hit@3 | {stats['bm25']['hit3']}/{used} | {stats['dense']['hit3']}/{used} | {stats['hybrid']['hit3']}/{used} |",
            f"| MRR | {stats['bm25']['rr']/used:.2f} | {stats['dense']['rr']/used:.2f} | {stats['hybrid']['rr']/used:.2f} |",
        ]
    text = "\n".join(lines)
    print(text)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
