"""Multi-label, rule-based clause classifier.

A clause can have several labels (e.g. ["termination", "notice_period"]).
Heading patterns are broad; body patterns are deliberately specific so that
common words ("terminate", "consideration") do not label every clause.
The first label returned is the "primary" label (most specific first).
"""
from __future__ import annotations

import re
from functools import lru_cache

# label -> {"heading": [regex...], "body": [regex...]}   (most specific labels first)
RULES: dict[str, dict[str, list[str]]] = {
    "non_compete": {
        "heading": [r"non[\s\-]?compet", r"restrictive\s+covenant", r"restraint"],
        "body": [
            r"non[\s\-]?compet",
            r"restraint\s+of\s+trade",
            r"shall\s+not\b[^.]{0,160}\b(compete|competing|competitor|competitive)\b",
            r"shall\s+not\b[^.]{0,200}\b(engage|work|employed|associated|provide\s+services)\b[^.]{0,120}\b(competing|competitor|similar\s+business|same\s+business)\b",
        ],
    },
    "non_solicitation": {
        "heading": [r"non[\s\-]?solicit"],
        "body": [r"non[\s\-]?solicit", r"shall\s+not\b[^.]{0,120}\bsolicit\w*\b", r"\bsolicit\w*\b[^.]{0,80}\b(employees?|clients?|customers?)\b"],
    },
    "penalty": {
        "heading": [r"liquidated\s+damages", r"penalt", r"\bbond\b"],
        "body": [
            r"liquidated\s+damages",
            r"\bpenalt(y|ies)\b",
            r"\bforfeit\w*\b",
            r"\b(service|training)\s+bond\b",
            r"\b(recover|reimburse)\w*\b[^.]{0,60}\btraining\s+(cost|expense)",
        ],
    },
    "indemnity": {
        "heading": [r"indemn"],
        "body": [r"indemnif(y|ied|ication|ies)", r"hold\s+harmless", r"keep\s+\w+\s+indemnified"],
    },
    "liability": {
        "heading": [r"liabilit"],
        "body": [
            r"limitation\s+of\s+liability",
            r"aggregate\s+liability",
            r"liability\b[^.]{0,60}\b(shall\s+not\s+exceed|capped|limited\s+to)\b",
            r"(consequential|indirect)\s+(loss|damage)",
            r"\bunlimited\s+liability\b",
            r"\buncapped\b",
        ],
    },
    "confidentiality": {
        "heading": [r"confidential", r"non[\s\-]?disclosure"],
        "body": [r"confidential\s+information", r"trade\s+secrets?", r"proprietary\s+information", r"shall\s+not\s+disclose"],
    },
    "ip": {
        "heading": [r"intellectual\s+property", r"inventions?", r"work\s+product", r"copyright"],
        "body": [
            r"intellectual\s+property",
            r"work\s+(made\s+)?for\s+hire",
            r"\bassigns?\b[^.]{0,80}\b(rights?|title|interest)\b",
            r"\bmoral\s+rights\b",
            r"\bcopyright\b",
        ],
    },
    "arbitration": {
        "heading": [r"arbitrat", r"dispute\s+resolution", r"disputes?"],
        "body": [r"arbitrat(ion|or|ors|al)", r"arbitration\s+and\s+conciliation"],
    },
    "jurisdiction": {
        "heading": [r"governing\s+law", r"jurisdiction", r"applicable\s+law"],
        "body": [
            r"governed\s+by\s+(and\s+construed\s+in\s+accordance\s+with\s+)?the\s+laws?\s+of",
            r"exclusive\s+jurisdiction",
            r"subject\s+to\s+the\s+(exclusive\s+)?jurisdiction",
            r"\bcourts?\s+(at|of|in)\s+[A-Z]",
        ],
    },
    "notice_period": {
        "heading": [r"notice\s+period", r"\bnotice\b"],
        "body": [
            r"notice\s+period",
            r"\b(\d+|[a-z\-]+)\s*(\(\d+\)\s*)?(calendar\s+)?(days?|months?|weeks?)['’]?\s*(prior\s+)?(written\s+)?notice",
            r"in\s+lieu\s+of\s+(the\s+)?notice",
        ],
    },
    "termination": {
        "heading": [r"terminat", r"resignation", r"cessation"],
        "body": [
            r"terminate\s+(this|the)\s+(agreement|employment|contract|lease|arrangement)",
            r"\b(right|entitled)\s+to\s+terminate",
            r"\bmay\s+terminate\b",
            r"upon\s+(the\s+)?termination",
            r"notice\s+of\s+termination",
            r"\bresign(s|ation)?\b",
        ],
    },
    "payment": {
        "heading": [r"payment", r"remuneration", r"salary", r"compensation", r"\bfees?\b", r"\brent\b", r"invoice"],
        "body": [r"\b(salary|remuneration|invoices?|ctc|rent)\b", r"per\s+(month|annum)", r"\bgst\b"],
    },
    "warranty": {
        "heading": [r"warrant"],
        "body": [r"\bwarrant(y|ies|s)\b", r"represents?\s+and\s+warrants?"],
    },
    "force_majeure": {
        "heading": [r"force\s+majeure"],
        "body": [r"force\s+majeure", r"act\s+of\s+god"],
    },
    "renewal": {
        "heading": [r"renewal", r"\bterm\b"],
        "body": [r"\brenew(al|ed|s)?\b", r"auto[\s\-]?renew", r"extension\s+of\s+(this\s+)?(agreement|term|lease)"],
    },
    "data_protection": {
        "heading": [r"data\s+protection", r"privacy"],
        "body": [
            r"personal\s+data",
            r"data\s+(protection|privacy)",
            r"information\s+technology\s+act",
            r"digital\s+personal\s+data",
            r"\bdpdp\b",
        ],
    },
}


@lru_cache(maxsize=1)
def _compiled() -> dict[str, tuple[list[re.Pattern], list[re.Pattern]]]:
    flags = re.IGNORECASE | re.DOTALL
    return {
        label: (
            [re.compile(p, flags) for p in spec["heading"]],
            [re.compile(p, flags) for p in spec["body"]],
        )
        for label, spec in RULES.items()
    }


def classify_clause(heading: str | None, text: str) -> list[str]:
    """Return all matching labels (most specific first), or ["other"]."""
    labels: list[str] = []
    for label, (head_pats, body_pats) in _compiled().items():
        if (heading and any(p.search(heading) for p in head_pats)) or any(p.search(text) for p in body_pats):
            labels.append(label)
    return labels or ["other"]
