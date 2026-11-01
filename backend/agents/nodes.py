"""Workflow nodes: router -> planner -> retriever -> evidence_verifier -> (expander) -> reasoner.

`make_nodes(retriever, llm)` returns plain functions (state -> partial state update),
so they can be wired by LangGraph or run by a simple sequential runner (tests / fallback).
Every node appends to state["trace"], giving an auditable research trace (not chain-of-thought).
"""
from __future__ import annotations

import functools
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from backend.agents.guard import sanitize_user_text
from backend.agents.llm import LLMClient, LLMUnavailable, _cfg
from backend.agents.llm_validation import (AnswerRejected, assemble_answer, clean_llm_text, drop_unverified_label_lines,
                                           validate_llm_text)
from backend.agents.prompts import LEGAL_QA_SYSTEM, build_user_prompt
from backend.analysis.clause_classifier import classify_clause
from backend.analysis.risk_engine import DISCLAIMER, ClauseInput, _best_quote, analyze_clauses, load_rules
from backend.retrieval.query_expansion import expand_query
from backend.retrieval.tokenizer import tokenize

# Tunable thresholds for the evidence verifier
MIN_RELEVANCE = 0.20      # share of a step's query tokens found in the section text
MIN_DENSE_COSINE = 0.40   # raw embedding similarity that counts as relevant on its own
MAX_PLAN_STEPS = 8
MAX_EVIDENCE = 5
MAX_QUOTE_CHARS = 350
MAX_LLM_EVIDENCE = 4      # provisions shown to the model (the rest are listed as "also retrieved")
LLM_MIN_RELEVANCE = 0.50  # a provision counts as "strong" for the model if trusted or at least this relevant (env NYAYA_LLM_MIN_RELEVANCE)

AUDIT_RE = re.compile(r"\b(audit|risk|review|analy[sz]e|check|issues?)\b", re.I)
CLAUSE_REF_RE = re.compile(r"\bclause\s+(\d+(?:\.\d+)*)\b", re.I)
SOURCE_VERIFICATION = "Source verification required."

LLM_SYSTEM = LEGAL_QA_SYSTEM  # kept as a module-level name for backwards compatibility


# ── helpers ────────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(state: dict, step: str, status: str, detail: Optional[dict] = None) -> list[dict]:
    return list(state.get("trace", [])) + [{"step": step, "status": status, "detail": detail or {}, "timestamp": _now()}]


def _node(name: str) -> Callable:
    """Wrap a node: time it, and turn exceptions into a failed trace entry (workflow continues)."""
    def deco(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            t0 = time.perf_counter()
            try:
                out = fn(state)
            except Exception as exc:  # keep the workflow alive; reasoner will say "Source verification required."
                msg = f"{name} failed: {type(exc).__name__}: {exc}"
                return {"errors": list(state.get("errors", [])) + [msg], "trace": _log(state, name, "failed", {"error": msg})}
            if out.get("trace"):
                out["trace"][-1]["detail"].setdefault("ms", int((time.perf_counter() - t0) * 1000))
            return out
        return wrapper
    return deco


def _matches(act: str, number: str, exp: dict) -> bool:
    kw = exp.get("act_keyword")
    return (kw is None or kw in act.lower()) and number.lower() == str(exp["number"]).lower()


def _step(idx: int, action: str, query: str, purpose: str, k: int = 4, expected: Optional[dict] = None) -> dict:
    return {"id": f"s{idx}", "action": action, "query": query, "purpose": purpose, "k": k, "expected": expected, "done": False}


# ── node factory ───────────────────────────────────────────────────────────────
def make_nodes(retriever: Any, llm: LLMClient, max_workers: int = 2) -> dict[str, Callable[[dict], dict]]:
    records = {r.section_id: r for r in getattr(retriever, "records", [])}
    rules_by_id = {r["id"]: r for r in load_rules()["rules"]}

    # ── router ─────────────────────────────────────────────────────────────────
    @_node("router")
    def router(state: dict) -> dict:
        query, f1 = sanitize_user_text(state.get("query") or "")
        clause_text, f2 = sanitize_user_text(state.get("clause_text") or "", max_len=4000)
        clauses = state.get("clauses") or []
        flags = f1 + f2
        if not clause_text and clauses:
            m = CLAUSE_REF_RE.search(query)
            if m:
                ref = m.group(1)
                hit = next((c for c in clauses if str(c.get("clause_label") or "") == ref or str(c.get("clause_number")) == ref), None)
                if hit:
                    clause_text = hit["text"]
        if state.get("intent"):
            intent = state["intent"]
        elif clause_text:
            intent = "clause_explain"
        elif clauses and (not query or AUDIT_RE.search(query)):
            intent = "contract_risk_audit"
        else:
            intent = "legal_qa"
        trace = _log(state, "router", "completed", {"intent": intent})
        if flags:
            trace = trace + [{"step": "input_guard", "status": "warning",
                              "detail": {"neutralised_patterns": len(flags), "note": "instruction-like text was removed and treated as data"},
                              "timestamp": _now()}]
        return {"query": query, "clause_text": clause_text, "intent": intent, "guard_flags": flags, "trace": trace}

    # ── planner ────────────────────────────────────────────────────────────────
    @_node("planner")
    def planner(state: dict) -> dict:
        intent, query = state.get("intent", "legal_qa"), state.get("query", "")
        steps: list[dict] = []
        findings: list[dict] = []

        if intent == "legal_qa":
            ex = expand_query(query)
            steps.append(_step(1, "search", query, "hybrid search for the question"))
            for ref in ex.section_refs:
                kw = ex.act_hints[0] if ex.act_hints else None
                steps.append(_step(len(steps) + 1, "lookup", f"section {ref}", "direct lookup of the cited section",
                                   expected={"act_keyword": kw, "number": ref}))
            if ex.extra_terms:
                steps.append(_step(len(steps) + 1, "search", " ".join(ex.extra_terms), "search with expanded legal terms", k=3))
            if llm.enabled:
                try:
                    for q in llm.suggest_queries(query):
                        clean, _ = sanitize_user_text(q, max_len=120)
                        steps.append(_step(len(steps) + 1, "search", clean, "LLM-suggested phrasing", k=3))
                except LLMUnavailable:
                    pass
        else:
            if intent == "clause_explain":
                inputs = [ClauseInput(clause_number=0, text=state.get("clause_text", ""))]
            else:
                inputs = [ClauseInput(clause_number=c["clause_number"], text=c["text"], heading=c.get("heading"),
                                      clause_label=c.get("clause_label")) for c in state.get("clauses", [])]
            drafts = analyze_clauses(inputs, None, state.get("doc_type", "other"))
            if intent == "clause_explain":
                drafts = [d for d in drafts if d.category != "missing_clause"]
            findings = [d.to_dict() for d in drafts]
            seen: set[str] = set()
            for d in drafts:
                rule = rules_by_id.get(d.rule_id)
                if not rule or not rule.get("expected_section") or rule["retrieval_query"] in seen:
                    continue
                seen.add(rule["retrieval_query"])
                steps.append(_step(len(steps) + 1, "search", rule["retrieval_query"], f"statute for: {d.title}",
                                   expected=rule["expected_section"]))
            if not steps and state.get("clause_text"):
                steps.append(_step(1, "search", state["clause_text"][:300], "semantic search on the clause text"))

        steps = steps[:MAX_PLAN_STEPS]
        return {"research_plan": steps, "findings": findings,
                "trace": _log(state, "planner", "completed",
                              {"steps": [f"{s['action']}: {s['query'][:70]}" for s in steps], "findings_from_rules": len(findings)})}

    # ── retriever ──────────────────────────────────────────────────────────────
    @_node("retriever")
    def retrieve(state: dict) -> dict:
        plan = [dict(s) for s in state.get("research_plan", [])]
        pending = [s for s in plan if not s["done"]]
        candidates = {c["section_id"]: dict(c) for c in state.get("retrieved", [])}

        def run(step: dict) -> list[dict]:
            exp, found = step.get("expected"), []
            if step["action"] == "lookup":
                for rec in records.values():
                    if _matches(rec.act_title, rec.section_number, exp):
                        found.append({"section_id": rec.section_id, "score": 1.0, "bm25": 0.0, "dense": 0.0, "dense_raw": 0.0, "via": "lookup", "expected": True})
                return found
            hit_expected = False
            for res in retriever.search(step["query"], k=step.get("k", 4)):
                is_exp = bool(exp and _matches(res.act, res.section_number, exp))
                hit_expected = hit_expected or is_exp
                found.append({"section_id": res.section_id, "score": res.score, "bm25": res.bm25_score,
                              "dense": res.dense_score, "dense_raw": res.dense_raw, "via": "search", "expected": is_exp})
            if exp and not hit_expected:  # rule-mapped section missing from results: look it up directly
                for rec in records.values():
                    if _matches(rec.act_title, rec.section_number, exp):
                        found.append({"section_id": rec.section_id, "score": 0.0, "bm25": 0.0, "dense": 0.0, "dense_raw": 0.0, "via": "rule_mapped", "expected": True})
                        break
            return found

        with ThreadPoolExecutor(max_workers=max_workers) as pool:  # limited concurrency (8 GB RAM)
            outcomes = list(pool.map(lambda s: _safe_run(run, s), pending))

        per_step = {}
        for step, (res, err) in zip(pending, outcomes):
            step["done"] = True
            per_step[step["id"]] = len(res) if not err else f"error: {err}"
            for r in res:
                rec = records.get(r["section_id"])
                if rec is None:
                    continue
                c = candidates.setdefault(r["section_id"], {
                    "section_id": rec.section_id, "citation": rec.citation, "act": rec.act_title,
                    "section_number": rec.section_number, "heading": rec.heading,
                    "score": 0.0, "dense_raw": 0.0, "found_by": [], "via": [], "matched_expected": False})
                c["score"] = max(c["score"], r["score"])
                c["dense_raw"] = max(c["dense_raw"], r["dense_raw"])
                c["found_by"] = sorted(set(c["found_by"]) | {step["id"]})
                c["via"] = sorted(set(c["via"]) | {r["via"]})
                c["matched_expected"] = c["matched_expected"] or r["expected"]
        # keep updated plan (with done flags) in state
        return {"research_plan": plan, "retrieved": list(candidates.values()),
                "trace": _log(state, "retriever", "completed", {"results_per_step": per_step, "unique_sections": len(candidates)})}

    # ── evidence verifier ──────────────────────────────────────────────────────
    @_node("evidence_verifier")
    def verifier(state: dict) -> dict:
        plan = {s["id"]: s for s in state.get("research_plan", [])}
        verified, rejected = [], []
        for cand in state.get("retrieved", []):
            rec = records.get(cand["section_id"])
            if rec is None:
                rejected.append({"citation": cand.get("citation"), "reason": "section not found in database"})
                continue
            step_queries = [plan[i]["query"] for i in cand["found_by"] if i in plan]
            relevance = 0.0
            for q in step_queries:
                qt = set(tokenize(q)) - {"section", "act"}
                if qt:
                    relevance = max(relevance, len(qt & set(tokenize(rec.search_text))) / len(qt))
            trusted = cand["matched_expected"] or "lookup" in cand["via"]
            quote = _best_quote(rec.text, " ".join(step_queries) or state.get("query", ""))
            if not quote or quote not in rec.text:
                rejected.append({"citation": rec.citation, "reason": "quote could not be matched to stored text"})
                continue
            if not (trusted or relevance >= MIN_RELEVANCE or cand["dense_raw"] >= MIN_DENSE_COSINE):
                rejected.append({"citation": rec.citation, "reason": f"low relevance ({relevance:.2f})"})
                continue
            verified.append({
                "section_id": rec.section_id, "citation": rec.citation, "act": rec.act_title,
                "section_number": rec.section_number, "heading": rec.heading, "law_status": rec.status,
                "quote": quote, "support": "supports", "relevance": round(relevance, 2),
                "score": round(cand["score"], 3), "via": cand["via"], "trusted": trusted,
            })
        verified.sort(key=lambda e: (not e["trusted"], -e["score"], -e["relevance"]))
        verified = verified[:MAX_EVIDENCE]
        return {"verified_evidence": verified, "rejected": rejected,
                "trace": _log(state, "evidence_verifier", "completed" if verified else "warning",
                              {"verified": [e["citation"] for e in verified], "rejected": rejected[:6],
                               "strength": {e["citation"]: f"relevance {e['relevance']}, score {e['score']}{', trusted' if e['trusted'] else ''}"
                                            for e in verified}})}

    # ── retry: query expander ──────────────────────────────────────────────────
    @_node("query_expander")
    def expander(state: dict) -> dict:
        plan = [dict(s) for s in state.get("research_plan", [])]
        query = state.get("query") or state.get("clause_text", "")[:200]
        extra = expand_query(query).extra_terms
        broadened = " ".join(dict.fromkeys(tokenize(query, use_stemming=False)))[:200]
        new_queries = [q for q in (" ".join(extra), broadened) if q and q not in {s["query"] for s in plan}]
        for q in new_queries:
            plan.append(_step(len(plan) + 1, "search", q, "retry with broadened query", k=5))
        return {"research_plan": plan, "retry_count": state.get("retry_count", 0) + 1,
                "trace": _log(state, "query_expander", "completed", {"added_queries": new_queries})}

    # ── reasoner ───────────────────────────────────────────────────────────────
    @_node("reasoner")
    def reasoner(state: dict) -> dict:
        intent = state.get("intent", "legal_qa")
        verified = state.get("verified_evidence", [])
        findings = state.get("findings", [])
        evidence_objects = _build_evidence_objects(intent, state, verified, findings, rules_by_id)
        confidence = _confidence(verified)
        template = _template_answer(intent, state, verified, findings, evidence_objects)
        answer, used_llm, note, raw = template, False, None, None

        if llm.enabled and verified and intent in ("legal_qa", "clause_explain"):
            try:
                shown = [dict(e, quote=_prompt_excerpt(e, records)) for e in _evidence_for_llm(verified)]
                prompt = build_user_prompt(
                    question=state.get("query") or "", verified=shown, intent=intent,
                    clause_text=state.get("clause_text") if intent == "clause_explain" else None,
                    findings=findings if intent == "clause_explain" else None, confidence=confidence)
                raw = llm.chat(LLM_SYSTEM, prompt)
                text = clean_llm_text(raw)
                trimmed = drop_unverified_label_lines(text, shown)
                if trimmed != text:
                    note, text = "removed 1 bullet that named an Act label not in the evidence; the rest of the answer was kept", trimmed
                validate_llm_text(text, shown)             # evidence integrity: only what the model was shown may be cited
                answer, used_llm = assemble_answer(text, verified, confidence, question=state.get("query") or ""), True
            except AnswerRejected as exc:
                note = f"LLM answer rejected ({exc}); template used"
            except LLMUnavailable as exc:
                note = f"LLM unavailable; template used ({exc})"
            except Exception as exc:  # a bug in prompt/validation code must never cost the user the verified answer
                note = f"LLM answer discarded after {type(exc).__name__}; template used"

        answer = f"{answer}\n\n{DISCLAIMER}"
        return {"answer": answer, "evidence": evidence_objects, "confidence": confidence,
                "trace": _log(state, "reasoner", "completed" if verified or findings else "warning",
                              {"used_llm": used_llm, "confidence": confidence, "evidence_objects": len(evidence_objects), "note": note,
                               # debugging aid, off by default: set NYAYA_DEBUG_LLM=1 to see the rejected model text in the trace
                               **({"rejected_text": str(raw)[:1500]} if (note and raw is not None and str(_cfg("NYAYA_DEBUG_LLM", "")) == "1") else {})})}

    return {"router": router, "planner": planner, "retriever": retrieve, "evidence_verifier": verifier,
            "query_expander": expander, "reasoner": reasoner}


def _safe_run(fn: Callable, step: dict) -> tuple[list, Optional[str]]:
    try:
        return fn(step), None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


# ── answer construction ────────────────────────────────────────────────────────
def _confidence(verified: list[dict]) -> str:
    if not verified:
        return "none"
    top = verified[0]
    return "moderate" if (top["trusted"] or top["relevance"] >= 0.5) else "low"


def _evidence_for_llm(verified: list[dict]) -> list[dict]:
    """Provisions the small model gets to see. The verifier admits loosely related sections (relevance >= 0.20); a 3B model
    tends to force them into its reasoning (e.g. s.56 'impossible act' in a non-compete answer). When at least one provision is
    strongly matched (trusted lookup, or relevance >= LLM_MIN_RELEVANCE), only the strong ones are shown; when none is, all
    are shown and the prompt says the evidence is weak. Hidden provisions stay in `evidence` and are listed as 'also retrieved'."""
    try:
        floor = float(_cfg("NYAYA_LLM_MIN_RELEVANCE", LLM_MIN_RELEVANCE))
    except ValueError:
        floor = LLM_MIN_RELEVANCE
    strong = [e for e in verified if e.get("trusted") or e.get("relevance", 0.0) >= floor]
    return (strong or verified)[:MAX_LLM_EVIDENCE]


def _prompt_excerpt(e: dict, records: dict) -> str:
    """The verified quote plus whatever follows it in the stored section text (verbatim corpus text). The quote shown to
    users is clipped at ~350 chars, which can cut off the operative words (s.74: 'reasonable compensation not exceeding...')."""
    rec = records.get(e.get("section_id"))
    if rec is None:
        return e["quote"]
    full = " ".join(str(rec.text).split())
    head = " ".join(str(e["quote"]).split()).rstrip("… ").strip()[:80]
    i = full.find(head) if head else -1
    return full[i:] if i >= 0 else e["quote"]


def _clip(quote: str) -> str:
    return quote if len(quote) <= MAX_QUOTE_CHARS else quote[:MAX_QUOTE_CHARS].rsplit(" ", 1)[0] + " …"


def _evidence_item(e: dict) -> dict:
    return {"source": e["act"], "section": e["section_number"], "citation": e["citation"], "heading": e["heading"],
            "law_status": e["law_status"], "quote": e["quote"], "support": e["support"]}


def _build_evidence_objects(intent: str, state: dict, verified: list[dict], findings: list[dict], rules_by_id: dict) -> list[dict]:
    if intent == "legal_qa" or not findings:
        claim = f"Provisions that appear relevant to: {state.get('query') or 'the clause'}"
        return [{"claim": claim, "evidence": [_evidence_item(e) for e in verified], "confidence": _confidence(verified), "conflicts": [],
                 "status": "verified" if verified else SOURCE_VERIFICATION}]
    objs = []
    for f in findings:
        exp = (rules_by_id.get(f["rule_id"]) or {}).get("expected_section")
        ev = [e for e in verified if exp and _matches(e["act"], e["section_number"], exp)]
        where = f"Clause {f.get('clause_label') or f.get('clause_number')}" if f.get("clause_number") else "Contract"
        status = "verified" if ev else (SOURCE_VERIFICATION if exp else "no statutory source expected for this finding")
        objs.append({"claim": f"{f['title']} ({where})", "risk_level": f["risk_level"], "reason": f["reason"],
                     "evidence": [_evidence_item(e) for e in ev], "confidence": "moderate" if ev else "none",
                     "conflicts": [], "status": status})
    return objs


def _provision_lines(verified: list[dict]) -> list[str]:
    lines = []
    for i, e in enumerate(verified, 1):
        flag = " — verify current status on India Code" if e["law_status"] == "verify_current_status" else ""
        lines.append(f"{i}. {e['citation']} — {e['heading'] or ''} (status: {e['law_status']}){flag}\n   \"{_clip(e['quote'])}\"")
    return lines


def _template_answer(intent: str, state: dict, verified: list[dict], findings: list[dict], objs: list[dict]) -> str:
    if intent == "contract_risk_audit":
        order = {"high": 0, "medium": 1, "low": 2, "info": 3}
        counts = {k: sum(1 for f in findings if f["risk_level"] == k) for k in order}
        out = [f"Contract review summary: {len(findings)} potential issue(s) flagged for review "
               f"(high {counts['high']}, medium {counts['medium']}, low {counts['low']}, informational {counts['info']})."]
        for f, o in zip(findings[:8], objs[:8]):
            out.append(f"\n[{f['risk_level'].upper()}] {o['claim']}\n{f['reason']}")
            if o["evidence"]:
                e = o["evidence"][0]
                out.append(f"Evidence: {e['citation']} — \"{_clip(e['quote'])}\"")
            else:
                out.append(f"Evidence: {SOURCE_VERIFICATION if 'verification' in o['status'] else 'none mapped for this finding'}")
        if not findings:
            out.append("No potential issues were identified by the rule set. This does not confirm the contract is free of issues.")
        return "\n".join(out)

    if not verified:
        return (f"{SOURCE_VERIFICATION} No provision in the loaded statute corpus could be verified as relevant to "
                "this request. Missing: a provision in the loaded corpus that matches the topic. To help, name the Act or section, "
                "the type of agreement and the key facts (for example duration, parties, amount), or check that the relevant law has been loaded.")

    parts: list[str] = []
    if intent == "clause_explain":
        types = classify_clause(None, state.get("clause_text", ""))
        parts.append(f"This clause appears to concern: {', '.join(types)}.")
        if findings:
            parts.append("Potential issues identified by the rule set:")
            parts += [f"- [{f['risk_level'].upper()}] {f['reason']}" for f in findings]
    else:
        parts.append(f"Question: {state.get('query', '')}")
    low = _confidence(verified) == "low"
    parts.append("\nProvisions retrieved from the local statute corpus that are only loosely related to the request:\n" if low
                 else "\nProvisions retrieved from the local statute corpus that appear relevant:\n")
    shown = _evidence_for_llm(verified) if intent == "legal_qa" else verified
    parts += _provision_lines(shown)
    rest = [e["citation"] for e in verified if e not in shown]
    if rest:
        parts.append("\nAlso retrieved (weaker matches, not listed above): " + "; ".join(rest))
    if low:
        parts.append("\nThe match is weak, so these provisions may not address your question at all. Missing: a provision in the loaded "
                     "corpus on the topic you asked about. To get a better answer, name the Act or section, the type of agreement and "
                     "the key facts (for example duration, parties, amount), or check that the relevant law has been loaded.")
    parts.append("\nThese provisions are potentially relevant. Whether and how they apply to specific facts requires "
                 "professional legal review; this is not a determination of legality or enforceability.")
    return "\n".join(parts)
