"""Prompt-injection guard.

Anything coming from a user or from a contract is UNTRUSTED DATA. We never place
it in system instructions; here we also neutralise instruction-like phrases so
they cannot pollute retrieval queries or LLM prompts.
"""
from __future__ import annotations

import re

_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?)",
    r"(reveal|show|print|display|leak)\s+(me\s+)?(the\s+|your\s+)?(system|hidden|initial)\s+(prompt|instructions?)",
    r"forget\s+(everything|all|your)\s+(you\s+)?(know|instructions?|rules?)",
    r"new\s+instructions?\s*:",
    r"\byou\s+are\s+now\b",
    r"\bdeveloper\s+mode\b",
    r"\bjailbreak\b",
    r"\bsystem\s*prompt\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
REPLACEMENT = "[instruction-like text removed]"


def sanitize_user_text(text: str, max_len: int = 2000) -> tuple[str, list[str]]:
    """Return (clean_text, flags). Flags name the patterns that were neutralised."""
    text = _CONTROL.sub(" ", text or "")[:max_len]
    flags: list[str] = []
    for pat in _COMPILED:
        if pat.search(text):
            flags.append(pat.pattern[:40])
            text = pat.sub(REPLACEMENT, text)
    return " ".join(text.split()), flags
