"""Search the statute corpus from the command line.

Examples (run from the project root):
  python scripts/search_cli.py "restraint of trade after employment"
  python scripts/search_cli.py "section 74 liquidated damages" -k 3
  python scripts/search_cli.py "arbitration agreement in writing" --mode bm25
  python scripts/search_cli.py --stats
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.retrieval.factory import build_retriever  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Hybrid statute search")
    p.add_argument("query", nargs="?", help="search query")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--mode", choices=["hybrid", "bm25", "dense"], default="hybrid")
    p.add_argument("--alpha", type=float, default=0.5, help="dense weight in fusion (0..1)")
    p.add_argument("--no-dense", action="store_true", help="BM25 only (no embedding model)")
    p.add_argument("--rebuild", action="store_true", help="re-embed every section")
    p.add_argument("--stats", action="store_true", help="show corpus statistics and exit")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)
    retriever = build_retriever(use_dense=not args.no_dense, rebuild=args.rebuild, alpha=args.alpha)

    if args.stats or not args.query:
        acts: dict[str, int] = {}
        for r in retriever.records:
            acts[r.act_title] = acts.get(r.act_title, 0) + 1
        print(f"Sections indexed: {len(retriever.records)} | dense available: {retriever.dense_available}")
        for title, n in acts.items():
            print(f"  {n:4d}  {title}")
        return 0

    results = retriever.search(args.query, k=args.k, mode=args.mode)
    if not results:
        print("No results. (Source verification required.)")
        return 0
    for rank, r in enumerate(results, 1):
        snippet = " ".join(r.text.split())[:200]
        print(f"{rank}. {r.citation}  [{r.heading or ''}]")
        print(f"   score={r.score:.3f} bm25={r.bm25_score:.2f} dense={r.dense_score:.2f} "
              f"via={','.join(r.contributed_by) or '-'} status={r.status}")
        print(f"   {snippet}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
