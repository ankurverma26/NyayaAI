"""Validation and assembly of LLM answers.

The model output is UNTRUSTED. Nothing from it reaches the user unless it passes
`validate_llm_text`. The "Relevant Legal Provisions" block is always built here from the
verified evidence, never taken from the model.

Rejections raise `AnswerRejected(reason)`; the reasoner then falls back to the template.
"""
from __future__ import annotations

import re

from backend.agents.prompts import SECTION_TITLES

MIN_CHARS = 40
MAX_CHARS = 3500
MAX_QUOTE_CHARS = 350


class AnswerRejected(ValueError):
    """The LLM output cannot be shown to the user."""


# ── patterns ───────────────────────────────────────────────────────────────────
# Wording rules. "definitely"/"certainly" are never acceptable. "illegal"/"unlawful" are banned as a VERDICT about the
# user's own clause/agreement (e.g. "this clause is unlawful"), but the model may repeat them when it is describing
# the statute itself, i.e. only if the word occurs in the verified statute text (s.56 literally says "unlawful").
ALWAYS_BANNED = re.compile(r"\b(?:definitely|certainly)\b", re.I)
_ILLEGAL_WORD = re.compile(r"\b(?:illegal|unlawful)\b", re.I)
VERDICT_ILLEGAL = re.compile(
    r"\b(?:this|that|it|they|your|the|such|these|those)\s+(?:[\w-]+\s+){0,3}?"
    r"(?:is|are|was|were|would be|will be|shall be|must be|remains|appears to be|seems to be)\s+(?:\w+\s+)?(?:illegal|unlawful)\b", re.I)
# a definitive verdict about the user's own clause/agreement/contract (stating what a statute says is fine)
DEFINITIVE = re.compile(
    r"(?<!\bif\s)(?<!\bwhether\s)(?<!\bto\sassess\s)\b(?:this|your|the)\s+(?:[\w-]+\s+){0,3}?(?:clause|agreement|contract|covenant|non-compete|bond|term|provision|restriction|restraint|condition|stipulation|undertaking)\s+"
    r"(?:is|will be|would be|shall be|must be|remains|cannot be|can't be)\s+(?:\w+\s+)?"
    r"(?:void|invalid|valid|enforceable|unenforceable|legal|binding|null)\b"
    r"|\bnull\s+and\s+void\b"
    r"|\b(?:is|are)\s+(?:definitely|clearly)\s+(?:void|invalid|valid|illegal|unlawful|lawful|enforceable|unenforceable|binding|null|prohibited|permitted)\b", re.I)
# an opening "Yes,"/"No," is a verdict on the user's question; "X does not apply to your startup" is a verdict too
LEADING_VERDICT = re.compile(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?(?:yes|no)\b\s*[,.:;!\u2014-]")
APPLY_VERDICT = re.compile(
    r"\b(?:does|do|will|would)\s+(?:not\s+)?apply\s+to\s+(?:your|this|the)\s+(?:[\w-]+\s+){0,2}?"
    r"(?:clause|agreement|contract|startup|company|business|employee|employer|case|situation|organi[sz]ation)\b"
    r"|\bis\s+not\s+applicable\s+to\s+your\b", re.I)
# an honest "the evidence does not cover this" is a valid answer even when it cites no provision
INSUFFICIENT = re.compile(
    r"\b(?:do(?:es)?\s+not\s+(?:directly\s+)?(?:address|cover|mention|relate\s+to|deal\s+with|contain)"
    r"|(?:not\s+enough|insufficient)\s+(?:evidence|information)|no\s+(?:directly\s+)?(?:relevant|verified)\s+provisions?"
    r"|(?:cannot|can't|unable\s+to)\s+(?:be\s+)?determine[d]?|(?:is|are)\s+unclear)\b", re.I)
# Definitive claims about the user's own amount or about penalty clauses in general: "can recover Rs. 5,00,000",
# "Rs. 5,00,000 is valid", "penalties are valid/enforceable", "supports the right to recover", "supports the enforceability of ..."
_RS = r"(?:Rs\.?|\u20b9|INR)\s*[\d,]+"
_GAP = r"(?:(?!\bwhether\b|\bif\b|;)[^.\n]){0,40}?"          # stays inside one clause; never crosses "whether", "if" or ";"
_NOT_QUESTION = r"(?<!whether\s)(?<!whether\sa\s)(?<!whether\sthe\s)(?<!if\s)(?<!if\sa\s)(?<!if\sthe\s)"
VALIDITY_CLAIM = re.compile(
    rf"\b(?:can|will|shall|must)\s+(?:\w+\s+){{0,2}}?(?:recover|claim|collect|enforce)\b{_GAP}{_RS}"
    rf"|{_RS}{_GAP}\b(?:is|are)\s+(?:\w+\s+)?(?:valid|enforceable|recoverable|payable|binding|lawful)\b"
    r"|\b(?:supports?|confirms?|establishes?)\s+(?:the\s+)?[\w' -]{0,30}?\b(?:right|entitlement)\s+to\b"
    r"|\b(?:supports?|confirms?)\s+the\s+(?:validity|enforceability)\s+of\b"
    rf"|{_NOT_QUESTION}\b(?:penalt(?:y|ies)|penalty\s+clauses?|liquidated\s+damages)\s+(?:\w+\s+){{0,3}}?(?:is|are)\s+(?:\w+\s+)?(?:valid|enforceable|binding|lawful|legal)\b", re.I)
_LABEL_LIKE = re.compile(r"\b[A-Z]{2,8}\d{4}\b")      # citation labels look like ICA1872, ACA1996, ITA2000
# Short Answer that leans to "valid" although a provision it relies on is headed "...void" and the Short Answer never says so
VALID_LEAN = re.compile(r"\b(?:may|might|could|can|would|potentially|possibly)\s+(?:\w+\s+){0,2}?valid\b", re.I)
SAYS_VOID = re.compile(r"\b(?:void|invalid|unenforceable|illegal|unlawful|not\s+(?:be\s+)?(?:valid|enforceable))\b", re.I)
CASELAW_CS = re.compile(r"\b[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*)*\s+(?:v\.?|vs\.?|versus)\s+[A-Z]")
CASELAW_CI = re.compile(
    r"\bAIR\s*(?:\d{4}|SC)\b|\bSCC\b|\bSCR\b|\bin\s+the\s+(?:case|matter)\s+of\b"
    r"|\b(?:supreme|high)\s+court\s+(?:has\s+|have\s+)?(?:held|ruled|decided|observed|laid)\b"
    r"|\bcourts?\s+(?:in\s+india\s+)?(?:has\s+|have\s+)?(?:consistently\s+|generally\s+|often\s+)?(?:held|ruled|decided|interpreted)\b"
    r"|\b(?:case[\s-]?law|precedents?)\s+(?:\w+\s+){0,6}?(?:has|have|shows?|holds?|establish\w*|confirms?|indicates?|suggests?|states?|settled)\b"
    r"|\b(?:established|settled|well[\s-]settled)\s+(?:case[\s-]?law|precedents?)\b"
    r"|\blandmark\s+(?:judg(?:e)?ments?|cases?|decisions?)\b", re.I)
REFUSAL_OR_LEAK = re.compile(
    r"\bas\s+an\s+ai\b|\blanguage\s+model\b|\bi(?:'m| am)\s+sorry\b|<\s*/?\s*(?:evidence|question|clause|findings)\b"
    r"|‹\s*/?\s*(?:evidence|question|clause|findings)\b|\buntrusted\s+data\b|(?-i:\bRULES\b)", re.I)
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")

# "section 27", "sections 27 and 28", "s.27", "§ 27A(1)", "article 19" - number lists only after a plural keyword
_SINGLE = re.compile(r"(?:\bsection|\bsec\.?|\bs\.|§|\barticle)\s*(\d+[A-Za-z]?)(?:\s*\([^)]*\))*", re.I)
_PLURAL = re.compile(r"(?:\bsections|\bsecs\.?|\bss\.|\barticles)\s*((?:\d+[A-Za-z]?(?:\s*\([^)]*\))*(?:\s*(?:,|and|&|or|to)\s*)?)+)", re.I)
_ACT = re.compile(r"\b((?:[A-Z][\w'&-]*\s+){0,6}?[A-Z][\w'&-]*\s+Act)\b")
_HEADING = re.compile(
    r"^\s*(?:#{1,4}\s*|\*\*\s*)?(?:\d+[.)]\s*)?(?P<title>[A-Za-z][A-Za-z ]{2,40}?)\s*(?:\*\*)?\s*:?\s*(?:\*\*)?\s*$")
_SKIP_TITLES = {"provisions retrieved", "relevant legal provisions", "legal provisions", "provisions", "sources", "source", "disclaimer", "evidence"}
_CANON = {t.lower(): t for t in SECTION_TITLES}
_CANON.update({"answer": "Short Answer", "explanation": "Legal Explanation", "application": "Application to the Question",
               "application to question": "Application to the Question", "conclusions": "Conclusion"})


def _numbers(text: str) -> set[str]:
    found = {m.group(1).lower() for m in _SINGLE.finditer(text)}
    for m in _PLURAL.finditer(text):
        found |= {n.lower() for n in re.findall(r"\d+[A-Za-z]?", re.sub(r"\([^)]*\)", "", m.group(1)))}
    return found


def _norm_act(name: str) -> str:
    name = re.sub(r"\b(?:19|20)\d{2}\b|\b18\d{2}\b", " ", name.lower())
    name = re.sub(r"[^a-z ]", " ", name)
    return " ".join(w for w in name.split() if w not in {"the", "this", "that", "said", "an", "a", "of", "under", "in"})


def _act_ok(mentioned: str, allowed_titles: list[str]) -> bool:
    words = _norm_act(mentioned).split()
    if len(words) < 2:                        # "the Act", "this Act": generic reference
        return True
    return any(" ".join(words[i:]) in t for t in allowed_titles for i in range(len(words) - 1))


# ── cleaning ───────────────────────────────────────────────────────────────────
def _trim_incomplete(text: str) -> str:
    """If generation stopped mid-sentence (token limit), cut back to the last full sentence/line."""
    if re.search(r"[.!?)\"”’]\s*$", text):
        return text
    cut = max(text.rfind(". "), text.rfind(".\n"), text.rfind("?\n"), text.rfind("!\n"))
    if cut < len(text) * 0.6:
        raise AnswerRejected("answer truncated mid-sentence")
    return text[:cut + 1].rstrip()


_OPENER = re.compile(r"(?im)^(\s*(?:[-*]\s*)?(?:\*\*)?)(?:yes|no)\b\s*[,.:;!\u2014-]\s*([a-z]?)")
_HEDGE = re.compile(
    r"\b(?:may|might|could|appears?|seems?|potential(?:ly)?|possibl[ey]|unclear|uncertain|tentative|depends?|subject\s+to"
    r"|(?:do(?:es)?\s+)?not\s+(?:directly\s+)?(?:address|cover))", re.I)


def _strip_verdict_opener(text: str) -> tuple[str, bool]:
    """Drop a leading 'Yes,'/'No,' (a verdict on the user's question). Returns (text, was_stripped)."""
    out, n = _OPENER.subn(lambda m: m.group(1) + m.group(2).upper(), text)
    return out, n > 0


def clean_llm_text(raw: object) -> str:
    """Normalise raw model output or raise AnswerRejected."""
    if not isinstance(raw, str):
        raise AnswerRejected("model returned a non-text response")
    text = re.sub(r"```[a-zA-Z]*", "", raw).replace("```", "").replace("\r", "").strip()
    text = re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", text))
    text, stripped = _strip_verdict_opener(text)
    if len(text) < MIN_CHARS:
        raise AnswerRejected("answer empty or too short")
    if len(text) > MAX_CHARS:
        raise AnswerRejected("answer too long")
    if text.lstrip().startswith(("{", "[")):
        raise AnswerRejected("answer is JSON, not prose")
    if len(CJK.findall(text)) > 3:
        raise AnswerRejected("answer contains non-English text")
    sentences = [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 15]
    if len(sentences) >= 6 and len(set(sentences)) / len(sentences) < 0.6:
        raise AnswerRejected("answer is repetitive")
    text = _trim_incomplete(text)
    if stripped:  # the model opened with a flat Yes/No: keep the answer only if what follows is itself cautious
        short = parse_sections(text).get("Short Answer") or text
        if not _HEDGE.search(short):
            raise AnswerRejected("answer opened with a Yes/No verdict and the Short Answer has no cautious wording")
    return text


def drop_unverified_label_lines(text: str, verified: list[dict]) -> str:
    """If exactly ONE bullet names an Act label that is not in the evidence (a typo like 'ICA1827'), remove that bullet and
    keep the rest; the whole text is still validated afterwards. Anything else (several lines, or a non-bullet line) is left
    for validate_llm_text to reject."""
    ok = {m.group(0) for e in verified for m in _LABEL_LIKE.finditer(str(e["citation"]))}
    lines = text.split("\n")
    bad = [i for i, ln in enumerate(lines) if any(m.group(0) not in ok for m in _LABEL_LIKE.finditer(ln))]
    if len(bad) != 1 or not re.match(r"\s*(?:[-*\u2022]|\d+[.)])\s", lines[bad[0]]):
        return text
    return "\n".join(ln for i, ln in enumerate(lines) if i != bad[0])


# ── validation ─────────────────────────────────────────────────────────────────
def validate_llm_text(text: str, verified: list[dict]) -> None:
    """Raise AnswerRejected if the text breaks any evidence-integrity or wording rule."""
    if REFUSAL_OR_LEAK.search(text):
        raise AnswerRejected("answer is a refusal or leaks the prompt")
    hit = (ALWAYS_BANNED.search(text) or DEFINITIVE.search(text) or VERDICT_ILLEGAL.search(text)
           or LEADING_VERDICT.search(text) or APPLY_VERDICT.search(text) or VALIDITY_CLAIM.search(text))   # LEADING_VERDICT is a backstop for direct callers
    if hit:
        raise AnswerRejected(f"non-cautious wording: '{hit.group(0)[:60]}'")
    statute_text = " ".join(str(e.get("quote", "")) for e in verified).lower()
    for w in _ILLEGAL_WORD.finditer(text):
        if w.group(0).lower() not in statute_text:
            raise AnswerRejected(f"non-cautious wording: '{w.group(0)}' is not part of the verified statute text")
    if CASELAW_CS.search(text) or CASELAW_CI.search(text):
        raise AnswerRejected("case-law citation not present in verified evidence")
    short = parse_sections(text).get("Short Answer") or text.split("\n\n")[0]
    if VALID_LEAN.search(short) and not SAYS_VOID.search(short):
        void_cited = [e["citation"] for e in _relied_on(text, verified) if re.search(r"\bvoid\b", str(e.get("heading") or ""), re.I)]
        if void_cited:
            raise AnswerRejected(f"Short Answer leans to 'valid' although {void_cited[0]} is headed 'void' and the Short Answer never says so")
    ok_labels = {m.group(0) for e in verified for m in _LABEL_LIKE.finditer(str(e["citation"]))}
    for m in _LABEL_LIKE.finditer(text):               # e.g. "ICA1827 s.74": a mangled or invented Act label
        if m.group(0) not in ok_labels:
            raise AnswerRejected(f"unverified Act label: {m.group(0)}")
    allowed = {str(e["section_number"]).lower() for e in verified}
    cited = _numbers(text)
    if not cited <= allowed:
        raise AnswerRejected(f"unverified section cited: {sorted(cited - allowed)}")
    titles = [_norm_act(e["act"]) for e in verified]
    for m in _ACT.finditer(text):
        if not _act_ok(m.group(1), titles):
            raise AnswerRejected(f"unverified Act named: {m.group(1)}")
    labels = [e["citation"].lower() for e in verified]
    if not cited and not any(lbl in text.lower() for lbl in labels) and not INSUFFICIENT.search(text):
        raise AnswerRejected("answer does not refer to any verified provision")


# ── assembly ───────────────────────────────────────────────────────────────────
def parse_sections(text: str) -> dict[str, str]:
    """Split model text into the canonical sections. Unknown headings become bold lines; code-owned ones are dropped."""
    sections: dict[str, list[str]] = {}
    current, skipping = None, False
    for line in text.split("\n"):
        m = _HEADING.match(line)
        title = m.group("title").strip().lower() if m else None
        is_marked = bool(m) and (line.lstrip().startswith(("#", "**")) or line.rstrip().endswith(":") or title in _CANON)
        if m and is_marked and title in _SKIP_TITLES:
            current, skipping = None, True
            continue
        if m and is_marked and title in _CANON:
            current, skipping = _CANON[title], False
            sections.setdefault(current, [])
            continue
        if skipping:
            continue
        if m and is_marked and line.lstrip().startswith(("#", "**")):
            line = f"**{m.group('title').strip()}**"
        if current is None:
            current = "_pre"
            sections.setdefault(current, [])
        sections[current].append(line.rstrip())
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _relied_on(text: str, verified: list[dict]) -> list[dict]:
    """Verified provisions that the model's text actually names (by label or section number)."""
    low, nums = text.lower(), _numbers(text)
    return [e for e in verified if e["citation"].lower() in low or str(e["section_number"]).lower() in nums]


def provisions_block(verified: list[dict]) -> str:
    lines = []
    for e in verified:
        status = e.get("law_status") or "unknown"
        flag = "; verify current status on India Code" if status == "verify_current_status" else ""
        quote = e["quote"] if len(e["quote"]) <= MAX_QUOTE_CHARS else e["quote"][:MAX_QUOTE_CHARS].rsplit(" ", 1)[0] + " …"
        head = f" — {e['heading']}" if e.get("heading") else ""
        lines.append(f"- **{e['citation']}**{head} (status: {status}{flag})\n  > \"{quote}\"")
    return "\n".join(lines)


# "- Facts given: none stated (...)": a 7B model writes this even when the question states facts (e.g. "3-year").
_NO_FACTS = re.compile(r"(?im)^(?P<lead>\s*(?:[-*]\s*)?(?:\*\*)?facts\s+given(?:\*\*)?\s*:?\s*(?:\*\*)?)\s*none\s+(?:stated|given|provided)\b[^\n]*$")


# "- Facts given: A 3-year non-compete after resignation (none stated)": real facts followed by a contradicting note
_FACTS_THEN_NONE = re.compile(
    r"(?im)^(?P<head>\s*(?:[-*]\s*)?(?:\*\*)?facts\s+given(?:\*\*)?\s*:?\s*(?:\*\*)?\s*)(?P<body>(?!none\b).+?)\s*"
    r"\((?:none|nothing)\s+(?:stated|given|provided)\)\.?\s*$")
_SECTION_REF = re.compile(r"\b(?:sections?|secs?\.?|s\.)\s*\d+[A-Za-z]?\b", re.I)
_FIRST_PERSON = re.compile(r"\b(?:i|me|my|mine|we|our|ours|us)\b", re.I)


def _question_states_facts(question: str) -> bool:
    """True if the question carries facts of the user's own (a number such as '3-year' or 'Rs. 5,00,000', or 'my'/'I'/'we').
    A pure lookup question ('What does section 74 say?', 'What is a contract of indemnity?') states none, so 'none stated' is right."""
    q = _SECTION_REF.sub(" ", question or "")
    return bool(re.search(r"\d", q) or _FIRST_PERSON.search(q))


def _facts_from_question(text: str, question: str | None) -> str:
    text = _FACTS_THEN_NONE.sub(lambda m: m.group("head") + m.group("body"), text)
    q = " ".join((question or "").split())
    if not q or not _question_states_facts(q):
        return text
    q = q if len(q) <= 200 else q[:200].rsplit(" ", 1)[0] + " ..."
    return _NO_FACTS.sub(lambda m: f'{m.group("lead").rstrip()} as stated in your question: "{q}"', text)


def assemble_answer(text: str, verified: list[dict], confidence: str, question: str | None = None) -> str:
    """Build the final markdown answer: model sections + code-built provisions + code-built footer."""
    secs = parse_sections(_facts_from_question(text, question))
    heading = "Provisions Retrieved (only loosely related)" if confidence == "low" else "Relevant Legal Provisions"
    used = _relied_on(text, verified) or verified          # if the model named none, show everything that was retrieved
    others = [e for e in verified if e not in used]
    provisions = f"## {heading}\n" + provisions_block(used)
    if others:
        provisions += "\n\nAlso retrieved, not relied on in the explanation: " + "; ".join(e["citation"] for e in others)
    out: list[str] = []
    if not any(t in secs for t in SECTION_TITLES):   # model ignored the format: keep its prose, labelled
        out += [provisions, "## Explanation\n" + secs.get("_pre", text)]
    else:
        if not secs.get("Short Answer") and secs.get("_pre"):
            secs["Short Answer"] = secs["_pre"]
        relied = _relied_on(text, verified)
        says_no_evidence = confidence == "low" or bool(INSUFFICIENT.search(secs.get("Short Answer", "")))
        basis = ("**Basis:** " + "; ".join(f"{e['citation']} — {e['heading']}" if e.get("heading") else e["citation"]
                                          for e in relied[:2]) + "\n") if relied and not says_no_evidence else ""
        for title in SECTION_TITLES:
            if secs.get(title):
                out.append(f"## {title}\n{basis if title == 'Short Answer' else ''}{secs[title]}")
            if title == "Short Answer":
                out.append(provisions)               # statute block always follows the short answer
    if confidence == "low":
        out.append("> **Evidence strength: low.** The retrieved provisions are only loosely matched to your request, "
                   "so treat this explanation as tentative and check the source text.")
    out.append("Sources: " + "; ".join(e["citation"] for e in used))
    return "\n\n".join(out)
