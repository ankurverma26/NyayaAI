"""Run the research workflow from the command line and print the answer + trace.

  python scripts/agent_cli.py "Is a 3-year non-compete after resignation valid?"
  python scripts/agent_cli.py "What does section 74 say?"
  python scripts/agent_cli.py --contract data/sample_contracts/employment_agreement_demo.txt --audit
  python scripts/agent_cli.py --contract data/sample_contracts/employment_agreement_demo.txt "explain clause 7"
  python scripts/agent_cli.py "..." --no-dense --engine sequential --json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.graph import run_agent  # noqa: E402
from backend.agents.llm import get_llm_client  # noqa: E402
from backend.retrieval.factory import build_retriever  # noqa: E402


def _load_contract(path: Path) -> tuple[list[dict], str]:
    from backend.ingestion.clause_splitter import split_into_clauses
    from backend.ingestion.document_parser import parse_document
    from backend.ingestion.service import _infer_doc_type

    parsed = parse_document(path.read_bytes(), filename=path.name)
    clauses = [{"clause_number": c.clause_number, "clause_label": c.clause_label, "heading": c.heading, "text": c.text}
               for c in split_into_clauses(parsed)]
    return clauses, _infer_doc_type(path.stem, parsed.full_text)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--contract", help="contract file for audit / clause explain")
    ap.add_argument("--audit", action="store_true", help="audit the whole contract")
    ap.add_argument("--no-dense", action="store_true")
    ap.add_argument("--llm", action="store_true", help="use Ollama (otherwise templates only)")
    ap.add_argument("--engine", choices=["auto", "langgraph", "sequential"], default="auto")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    ctx: dict = {}
    if args.contract:
        ctx["clauses"], ctx["doc_type"] = _load_contract(Path(args.contract))
    if args.audit:
        ctx["intent"] = "contract_risk_audit"

    retriever = build_retriever(use_dense=not args.no_dense)
    state = run_agent(retriever, args.query, llm=get_llm_client(args.llm), engine=args.engine, **ctx)

    if args.json:
        keep = ("intent", "workflow_engine", "research_plan", "verified_evidence", "evidence", "confidence", "answer", "trace", "errors")
        print(json.dumps({k: state.get(k) for k in keep}, indent=2, ensure_ascii=False))
        return 0

    print(f"Workflow: {state['workflow_engine']} | intent: {state.get('intent')} | confidence: {state.get('confidence')}")
    print("\nRESEARCH PLAN")
    for s in state.get("research_plan", []):
        print(f"  {s['id']} [{s['action']}] {s['query'][:80]}  ({s['purpose']})")
    print("\nANSWER\n" + state.get("answer", ""))
    print("\nEXECUTION TRACE")
    for t in state.get("trace", []):
        mark = {"completed": "✓", "warning": "!", "failed": "✗"}.get(t["status"], "•")
        print(f"  {mark} {t['step']:<18} {json.dumps(t['detail'], ensure_ascii=False)[:150]}")
    if state.get("errors"):
        print("\nERRORS:", state["errors"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
