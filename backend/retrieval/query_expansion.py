"""Rule-based query expansion (no LLM needed).

TERM_MAP only adds *search terms* (synonyms / related legal vocabulary) to help
retrieval. It contains no statute text and is never shown as legal authority.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# phrase found in query -> extra search terms
TERM_MAP: dict[str, list[str]] = {
    "non-compete": ["restraint of trade", "restrain", "lawful profession trade business"],
    "non compete": ["restraint of trade", "restrain", "lawful profession trade business"],
    "noncompete": ["restraint of trade", "restrain", "lawful profession trade business"],
    "competing": ["restraint of trade", "restrain", "profession trade business"],
    "compete": ["restraint of trade", "restrain", "profession trade business"],
    "post-employment": ["restraint of trade", "after employment"],
    "after employment": ["restraint of trade"],
    "non-solicit": ["restraint of trade", "restrain"],
    "liquidated damages": ["penalty", "compensation breach", "stipulated sum"],
    "penalty": ["liquidated damages", "compensation breach", "stipulated sum"],
    "damages": ["compensation", "loss or damage", "breach of contract"],
    "indemnity": ["indemnify", "loss caused", "contract of indemnity"],
    "indemnify": ["indemnity", "loss caused", "contract of indemnity"],
    "arbitration": ["arbitration agreement", "arbitral", "arbitrator"],
    "arbitrator": ["arbitration", "appointment of arbitrators"],
    "personal data": ["sensitive personal data", "reasonable security practices", "body corporate"],
    "data protection": ["sensitive personal data", "reasonable security practices", "body corporate"],
    "data breach": ["sensitive personal data", "compensation", "body corporate"],
    "confidential": ["disclosure of information", "breach of lawful contract"],
    "confidentiality": ["disclosure of information", "breach of lawful contract"],
    "void": ["void agreement", "unlawful", "not enforceable"],
    "unlawful": ["lawful object", "lawful consideration", "void"],
    "termination": ["breach of contract", "rescission", "notice"],
    "impossible": ["impossibility", "agreement to do impossible act"],
    "frustration": ["impossibility", "contract becoming impossible"],
    "specific performance": ["specific relief", "enforce performance"],
}

# phrase in query -> keyword expected inside the Act title (lowercase)
ACT_ALIASES: dict[str, str] = {
    "indian contract act": "contract",
    "contract act": "contract",
    "ica": "contract",
    "information technology act": "information technology",
    "it act": "information technology",
    "arbitration and conciliation": "arbitration",
    "arbitration act": "arbitration",
    "companies act": "companies",
    "specific relief act": "specific relief",
}

_SECTION_GROUP_RE = re.compile(
    r"\b(?:sections?|secs?|s)\.?\s*(\d+[a-z]?(?:\s*(?:,|and|&)\s*\d+[a-z]?)*)",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"\d+[a-z]?", re.IGNORECASE)


@dataclass
class ExpandedQuery:
    original: str
    extra_terms: list[str] = field(default_factory=list)
    section_refs: list[str] = field(default_factory=list)  # lowercase, e.g. ["27", "43a"]
    act_hints: list[str] = field(default_factory=list)     # title keywords, e.g. ["contract"]

    @property
    def dense_text(self) -> str:
        """Text to embed: the original query plus expansion terms."""
        return " ".join([self.original, *self.extra_terms]).strip()


def extract_section_refs(query: str) -> list[str]:
    """'section 27', 's.27', 'sec 43A', 'sections 73 and 74' -> ['27'] / ['43a'] / ['73','74']."""
    refs: list[str] = []
    for m in _SECTION_GROUP_RE.finditer(query):
        for num in _NUM_RE.findall(m.group(1)):
            n = num.lower()
            if n not in refs:
                refs.append(n)
    return refs


def detect_act_hints(query: str) -> list[str]:
    q = query.lower()
    hints: list[str] = []
    for alias, keyword in ACT_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q) and keyword not in hints:
            hints.append(keyword)
    return hints


def expand_query(query: str) -> ExpandedQuery:
    q = query.lower()
    extra: list[str] = []
    for phrase, terms in TERM_MAP.items():
        if phrase in q:
            for t in terms:
                if t not in extra and t not in q:
                    extra.append(t)
    return ExpandedQuery(
        original=query.strip(),
        extra_terms=extra,
        section_refs=extract_section_refs(query),
        act_hints=detect_act_hints(query),
    )
