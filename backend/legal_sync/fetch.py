"""Download the official Act (PDF) and turn it into text. Cached on disk to be polite to the server."""
from __future__ import annotations

import hashlib
import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "laws"
RETRY_STATUSES = {500, 502, 503, 504}   # temporary server problems worth retrying
MAX_BYTES = 80 * 1024 * 1024
HEADERS = {"User-Agent": "NyayaAI-academic-verifier/1.0 (student project; on-demand checks, one request per Act)"}


@dataclass
class FetchResult:
    ok: bool
    text: str = ""
    status_code: Optional[int] = None
    error: Optional[str] = None
    from_cache: bool = False


def pdf_bytes_to_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def fetch_text(
    url: str,
    force: bool = False,
    max_age_hours: float = 6.0,
    cache_dir: Optional[Path] = None,
    timeout: int = 90,
    http_get: Optional[Callable] = None,
    retries: int = 2,
    backoff: float = 4.0,
    sleep: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """Fetch `url` (must be a PDF) and return its text. Uses a cache younger than `max_age_hours`."""
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.txt"
    if not force and path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600:
        return FetchResult(True, path.read_text(encoding="utf-8"), from_cache=True)

    get = http_get or requests.get
    attempt = 0
    while True:
        status: Optional[int] = None
        try:
            resp = get(url, headers=HEADERS, timeout=timeout)
        except Exception as exc:  # network down, DNS, timeout, TLS...
            error = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                break
            status, error = resp.status_code, f"HTTP {resp.status_code}"
            if status not in RETRY_STATUSES:
                return FetchResult(False, status_code=status, error=error)
        if attempt >= retries:  # the official site is busy or down: give up politely
            return FetchResult(False, status_code=status, error=f"{error} (after {attempt + 1} attempts; try again later)")
        attempt += 1
        sleep(backoff * attempt)
    data = resp.content
    if len(data) > MAX_BYTES:
        return FetchResult(False, status_code=200, error="File is too large")
    if data[:4] != b"%PDF":
        return FetchResult(False, status_code=200, error="URL did not return a PDF. Put the Act's PDF link in the 'url' field of its JSON file.")
    try:
        text = pdf_bytes_to_text(data)
    except Exception as exc:
        return FetchResult(False, status_code=200, error=f"Could not read the PDF: {type(exc).__name__}: {exc}")
    if len(text.split()) < 200:
        return FetchResult(False, status_code=200, error="The PDF has no extractable text (scanned?)")
    path.write_text(text, encoding="utf-8")
    return FetchResult(True, text, status_code=200)
