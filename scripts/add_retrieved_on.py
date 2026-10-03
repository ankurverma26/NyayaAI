"""Add a "retrieved_on" date to statute JSON files that do not have one.

  python scripts/add_retrieved_on.py              # uses today's date
  python scripts/add_retrieved_on.py 2026-10-02   # use the date you copied / last verified the text

Use the real date you copied or last checked the text against India Code (traceability).
Files that already have retrieved_on are left untouched.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    when = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", when):
        print("Date must look like 2026-10-02")
        return 1
    changed = 0
    for path in sorted((ROOT / "data" / "laws").glob("*.json")):
        if "sample_format" in path.name:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("retrieved_on"):
            print(f"skip   {path.name} (already {data['retrieved_on']})")
            continue
        data["retrieved_on"] = when
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"added  {path.name} -> {when}")
        changed += 1
    print(f"\n{changed} file(s) updated. Now run: python scripts/validate_laws.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
