"""Tokenizer for legal text.

Keeps numeric tokens ("27") and alphanumeric section ids ("43a") because exact
section matching matters in statutes. Uses a light, conservative stemmer so that
"restrained"/"restraint"-style variants and plurals match, without needing NLTK.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """a an and any are as at be been by for from has have in is it its of on or
    such that the their this to was were which who with shall may not no per
    thereof therein hereby herein whereas""".split()
)


def stem(token: str) -> str:
    """Very light suffix stripping (plural, -ing, -ed, trailing -e)."""
    if token.isdigit() or len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        token = token[:-3] + "y"
    elif token.endswith("ing") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ed") and len(token) > 4:
        token = token[:-2]
    elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        token = token[:-1]
    if token.endswith("e") and len(token) > 4:
        token = token[:-1]
    return token


def tokenize(text: str, use_stemming: bool = True) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and 1-letter words."""
    tokens: list[str] = []
    for tok in _TOKEN_RE.findall(text.lower()):
        if tok in STOPWORDS:
            continue
        if len(tok) == 1 and not tok.isdigit():
            continue
        tokens.append(stem(tok) if use_stemming else tok)
    return tokens
