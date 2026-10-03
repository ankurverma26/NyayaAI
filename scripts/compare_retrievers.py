"""Compare BM25-only vs dense-only vs hybrid on two small hand-labelled query sets.

  python scripts/compare_retrievers.py                 # both sets
  python scripts/compare_retrievers.py --set lay       # only the plain-language set

"formal"  : queries that reuse statute vocabulary (favours keyword search)
"lay"     : plain-language questions with little shared vocabulary (where semantic search should help)

Writes docs/retrieval_results.md. Queries whose expected section is not in your corpus are skipped.
Both sets are small and hand-labelled: report them as sanity benchmarks, not a rigorous evaluation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.retrieval.factory import build_retriever  # noqa: E402

# (query, keyword expected inside the Act title, expected section number)
FORMAL: list[tuple[str, str, str]] = [
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

LAY: list[tuple[str, str, str]] = [
    ("Can my employer stop me from joining a competitor after I quit?", "contract", "27"),
    ("My contract says I must pay five lakh rupees if I resign early", "contract", "74"),
    ("The company leaked my personal details because of poor security", "information technology", "43a"),
    ("If the two sides cannot agree, who picks the arbitrator?", "arbitration", "11"),
    ("Does an arbitration clause have to be written down?", "arbitration", "7"),
    ("The other party broke the contract and I lost money, what can I claim?", "contract", "73"),
    ("Can a contract be valid if its purpose is against the law?", "contract", "23"),
    ("If I promise to cover someone's losses, what is that called?", "contract", "124"),
    ("Someone revealed confidential information they got through a contract", "information technology", "72a"),
    ("Can parties agree that nobody may go to court over their disputes?", "contract", "28"),
    ("A court tells the parties to go to arbitration instead; which rule allows that?", "arbitration", "8"),
    ("Was my consent valid if I was pressured or lied to?", "contract", "14"),
]

MODES = ["bm25", "dense", "hybrid"]


def rank_of(results, keyword: str, number: str) -> int | None:
    for i, r in enumerate(results, 1):
        if keyword in r.act.lower() and r.section_number.lower() == number:
            return i
    return None


def evaluate(retriever, name: str, queries, alpha: float) -> list[str]:
    present = {(r.act_title.lower(), r.section_number.lower()) for r in retriever.records}
    stats = {m: {"hit1": 0, "hit3": 0, "rr": 0.0} for m in MODES}
    rows, used = [], 0
    for query, kw, num in queries:
        if not any(kw in t and n == num for t, n in present):
            rows.append(f"| {query} | {kw} s.{num} | skipped (not in corpus) | | |")
            continue
        used += 1
        cells = []
        for m in MODES:
            res = retriever.search(query, k=len(retriever.records), mode=m, alpha=alpha)
            rk = rank_of(res, kw, num)
            cells.append(str(rk) if rk else "-")
            stats[m]["hit1"] += rk == 1
            stats[m]["hit3"] += bool(rk and rk <= 3)
            stats[m]["rr"] += (1.0 / rk) if rk else 0.0
        rows.append(f"| {query} | {kw} s.{num} | {cells[0]} | {cells[1]} | {cells[2]} |")
    out = [f"## {name} queries ({used} evaluated)", "",
           "| Query | Expected | BM25 rank | Dense rank | Hybrid rank |", "|---|---|---|---|---|", *rows, ""]
    if used:
        out += ["| Metric | BM25 | Dense | Hybrid |", "|---|---|---|---|",
                f"| Hit@1 | {stats['bm25']['hit1']}/{used} | {stats['dense']['hit1']}/{used} | {stats['hybrid']['hit1']}/{used} |",
                f"| Hit@3 | {stats['bm25']['hit3']}/{used} | {stats['dense']['hit3']}/{used} | {stats['hybrid']['hit3']}/{used} |",
                f"| MRR | {stats['bm25']['rr']/used:.2f} | {stats['dense']['rr']/used:.2f} | {stats['hybrid']['rr']/used:.2f} |", ""]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--set", choices=["formal", "lay", "both"], default="both")
    ap.add_argument("--out", default=str(ROOT / "docs" / "retrieval_results.md"))
    args = ap.parse_args()

    retriever = build_retriever(alpha=args.alpha)
    if not retriever.dense_available:
        print("WARNING: dense retriever unavailable. Dense/hybrid columns are not meaningful.")
    lines = ["# Retrieval comparison (BM25 vs Dense vs Hybrid)", "",
             f"Corpus: {len(retriever.records)} sections. Hybrid alpha = {args.alpha}. Hand-labelled sanity benchmarks, not a rigorous evaluation.", ""]
    if args.set in ("formal", "both"):
        lines += evaluate(retriever, "Formal (statute vocabulary)", FORMAL, args.alpha)
    if args.set in ("lay", "both"):
        lines += evaluate(retriever, "Plain-language", LAY, args.alpha)
    text = "\n".join(lines)
    print(text)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
