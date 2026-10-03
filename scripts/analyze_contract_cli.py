"""Analyze a contract file from the command line (no database needed).

  python scripts/analyze_contract_cli.py data/sample_contracts/employment_agreement_demo.txt
  python scripts/analyze_contract_cli.py contract.pdf --json
  python scripts/analyze_contract_cli.py contract.txt --no-dense

Requires the statute corpus to be loaded (python scripts/load_laws.py).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.analysis.clause_classifier import classify_clause  # noqa: E402
from backend.analysis.risk_engine import ClauseInput, analyze_clauses, summarize  # noqa: E402
from backend.ingestion.clause_splitter import split_into_clauses  # noqa: E402
from backend.ingestion.document_parser import parse_document  # noqa: E402
from backend.ingestion.service import _infer_doc_type  # noqa: E402  (imports DB models)
from backend.retrieval.factory import build_retriever  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--no-dense", action="store_true", help="BM25 only (no embedding model)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    path = Path(args.file)
    parsed = parse_document(path.read_bytes(), filename=path.name)
    doc_type = _infer_doc_type(path.stem, parsed.full_text)
    clauses = [
        ClauseInput(
            clause_number=c.clause_number, clause_label=c.clause_label, heading=c.heading, text=c.text,
            clause_types=classify_clause(c.heading, c.text),
        )
        for c in split_into_clauses(parsed)
    ]
    retriever = build_retriever(use_dense=not args.no_dense)
    findings = analyze_clauses(clauses, retriever, doc_type)
    summary = summarize(findings)

    if args.json:
        print(json.dumps({"doc_type": doc_type, "summary": summary,
                          "findings": [f.to_dict() for f in findings]}, indent=2, ensure_ascii=False))
        return 0

    print(f"Document: {path.name} | type: {doc_type} | clauses: {len(clauses)}")
    for c in clauses:
        print(f"  [{c.clause_label or c.clause_number}] {c.heading or '(no heading)'}  -> {', '.join(c.clause_types)}")
    print(f"\nSummary: {summary['counts']} | verified evidence: {summary['verified']} | "
          f"missing clauses: {summary['missing_clauses']}\n")
    for f in findings:
        where = f"Clause {f.clause_label or f.clause_number} ({f.clause_heading})" if f.clause_number else "Contract-level"
        print(f"[{f.risk_level.upper()}] {f.title} - {where}")
        print(f"   {f.reason}")
        if f.evidence:
            e = f.evidence[0]
            print(f"   Evidence: {e['citation']} ({e['heading']}) [{e['status']}] via {e['retrieval_source']}")
            print(f"   Quote: \"{e['quote'][:300]}\"")
        elif f.evidence_status == "source_verification_required":
            print("   Evidence: Source verification required.")
        print()
    print(summary["disclaimer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
