"""Check stored statute sections against the official source (no database needed here)."""
from __future__ import annotations

from typing import Any, Callable, Optional

from backend.legal_sync.compare import verify_act
from backend.legal_sync.fetch import FetchResult, fetch_text


def check_source(
    url: Optional[str],
    sections: list[tuple[str, str]],
    fetcher: Callable[..., FetchResult] = fetch_text,
    force: bool = False,
) -> dict[str, Any]:
    """Return {outcome, counts, sections, fingerprint, ...}.

    outcome: verified | needs_review | unreachable | no_source_url
    The stored text is never changed here; the result only reports what the official text says.
    """
    if not url:
        return {"outcome": "no_source_url", "error": "This Act has no source URL."}
    res = fetcher(url, force=force)
    if not res.ok:
        return {"outcome": "unreachable", "error": res.error, "http_status": res.status_code}
    out = verify_act(sections, res.text)
    out.update(http_status=res.status_code, from_cache=res.from_cache)
    return out
