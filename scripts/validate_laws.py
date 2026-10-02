"""Validate statute JSON files in data/laws/ before loading them into NyayaAI.

Usage:  python scripts/validate_laws.py            (checks data/laws/*.json)
        python scripts/validate_laws.py path.json  (checks one file)

Exit code 0 = all good, 1 = errors found.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

REQUIRED_TOP = ["act", "short_name", "year", "citation", "url", "status", "retrieved_on", "sections"]
REQUIRED_SECTION = ["heading", "text"]  # plus "section_number" or "number"
VALID_STATUS = {"in_force", "amended", "repealed", "draft", "verify_current_status"}
PLACEHOLDER_PATTERNS = re.compile(r"PASTE|PLACEHOLDER|TODO|LOREM|\.\.\.paste|XXX", re.IGNORECASE)
MIN_TEXT_LEN = 40
OFFICIAL_HOSTS = ("indiacode.nic.in", "legislative.gov.in", "egazette.gov.in", "egazette.nic.in")


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"], []
    if not isinstance(data, dict):
        return ["Top level must be a JSON object"], []

    for key in REQUIRED_TOP:
        if key not in data or data[key] in ("", None, []):
            errors.append(f"Missing or empty top-level field: '{key}'")

    for key in ("act", "short_name", "citation", "url"):
        if isinstance(data.get(key), str) and PLACEHOLDER_PATTERNS.search(data[key]):
            errors.append(f"Placeholder text still in '{key}'")

    if data.get("status") and data["status"] not in VALID_STATUS:
        errors.append(f"status '{data['status']}' not in {sorted(VALID_STATUS)}")
    if data.get("status") == "verify_current_status":
        warnings.append("status is 'verify_current_status' - confirm on India Code before demo")

    if not isinstance(data.get("year"), int):
        errors.append("'year' must be an integer")

    url = data.get("url", "")
    if isinstance(url, str) and url and not any(h in url for h in OFFICIAL_HOSTS):
        warnings.append(f"URL host is not a known official source: {url}")

    try:
        datetime.strptime(str(data.get("retrieved_on", "")), "%Y-%m-%d")
    except ValueError:
        errors.append("'retrieved_on' must be YYYY-MM-DD")

    sections = data.get("sections", [])
    if not isinstance(sections, list):
        return errors + ["'sections' must be a list"], warnings

    seen: set[str] = set()
    for i, sec in enumerate(sections):
        label = f"sections[{i}]"
        if not isinstance(sec, dict):
            errors.append(f"{label}: must be an object")
            continue
        num = str(sec.get("section_number") or sec.get("number") or "").strip()
        label = f"s.{num or '?'} (index {i})"
        if not num:
            errors.append(f"{label}: missing 'section_number' (or 'number')")
        for key in REQUIRED_SECTION:
            if not str(sec.get(key, "")).strip():
                errors.append(f"{label}: missing/empty '{key}'")
        if num in seen:
            errors.append(f"{label}: duplicate section number")
        seen.add(num)
        text = str(sec.get("text", ""))
        heading = str(sec.get("heading", ""))
        if PLACEHOLDER_PATTERNS.search(text) or PLACEHOLDER_PATTERNS.search(heading):
            errors.append(f"{label}: placeholder text still present")
        elif text and len(text.strip()) < MIN_TEXT_LEN:
            warnings.append(f"{label}: text is very short ({len(text.strip())} chars) - truncated paste?")
        if re.search(r"\[\d+\]|\bSubs\. by\b|\bIns\. by\b", text):
            warnings.append(f"{label}: looks like footnote/amendment markers inside 'text' - move to a 'notes' field")
        if "\ufffd" in text:
            warnings.append(f"{label}: contains broken characters (PDF copy issue)")

    if not sections:
        errors.append("No sections found")
    return errors, warnings


def main() -> int:
    if len(sys.argv) > 1:
        files = [Path(a) for a in sys.argv[1:]]
    else:
        files = sorted(Path("data/laws").glob("*.json"))
    files = [f for f in files if "sample_format" not in f.name]
    if not files:
        print("No JSON files found in data/laws/")
        return 1

    total_err = 0
    total_sec = 0
    for f in files:
        errs, warns = validate_file(f)
        try:
            n = len(json.loads(f.read_text(encoding="utf-8")).get("sections", []))
        except Exception:
            n = 0
        total_sec += n
        status = "OK  " if not errs else "FAIL"
        print(f"[{status}] {f.name}  ({n} sections)")
        for e in errs:
            print(f"   ERROR: {e}")
        for w in warns:
            print(f"   warn : {w}")
        total_err += len(errs)

    print(f"\n{len(files)} file(s), {total_sec} sections, {total_err} error(s)")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
