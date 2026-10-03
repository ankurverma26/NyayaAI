"""Print a Markdown table of the statutes in data/laws/ (use it to keep the README accurate).

  python scripts/list_corpus.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LAWS = Path(__file__).resolve().parent.parent / "data" / "laws"


def key(n: str) -> tuple[int, str]:
    m = re.match(r"\d+", n)
    return (int(m.group()) if m else 10**6, n)


def main() -> None:
    rows, total = [], 0
    for path in sorted(LAWS.glob("*.json")):
        if "sample_format" in path.name:
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        nums = sorted((str(s.get("section_number") or s.get("number")) for s in d.get("sections", [])), key=key)
        total += len(nums)
        rows.append(f"| {d.get('act')} | {d.get('short_name', '')} | {', '.join('s.' + n for n in nums)} | "
                    f"{d.get('status', '')} | {d.get('retrieved_on', '')} |")
    print("| Act | Short name | Sections | Status | Retrieved on |")
    print("|---|---|---|---|---|")
    print("\n".join(rows))
    print(f"\nTotal: {len(rows)} Acts, {total} sections")


if __name__ == "__main__":
    main()
