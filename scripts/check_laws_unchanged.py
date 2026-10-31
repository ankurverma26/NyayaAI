"""Check that statute text in data/laws/*.json has NOT changed compared with the last commit.

  python scripts/check_laws_unchanged.py

Section number, heading and text must be identical. Changes to "url", "status", "notes" and
other metadata are allowed and are listed so you can review them.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LAWS = Path("data/laws")


def sections(data: dict) -> dict[str, tuple[str, str]]:
    out = {}
    for s in data.get("sections", []):
        num = str(s.get("section_number") or s.get("number"))
        out[num] = (s.get("heading") or "", s.get("text") or "")
    return out


def main() -> int:
    bad = 0
    for path in sorted(LAWS.glob("*.json")):
        rel = path.as_posix()
        old_raw = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True, text=True, encoding="utf-8")
        if old_raw.returncode != 0:
            print(f"NEW      {rel} (not in the last commit)")
            continue
        old, new = json.loads(old_raw.stdout), json.loads(path.read_text(encoding="utf-8"))
        so, sn = sections(old), sections(new)
        problems = []
        for num in sorted(set(so) | set(sn)):
            if num not in sn:
                problems.append(f"s.{num} was REMOVED")
            elif num not in so:
                problems.append(f"s.{num} was ADDED")
            elif so[num][0] != sn[num][0]:
                problems.append(f"s.{num} heading CHANGED")
            elif so[num][1] != sn[num][1]:
                problems.append(f"s.{num} text CHANGED")
        meta = [k for k in sorted(set(old) | set(new)) if k != "sections" and old.get(k) != new.get(k)]
        if problems:
            bad += 1
            print(f"PROBLEM  {rel}: " + "; ".join(problems))
        else:
            print(f"OK       {rel}: statute text unchanged; metadata changed: {meta or 'none'}")
    print("\nAll statute text is unchanged." if not bad else "\nSome statute text changed. Do NOT commit these files until you know why.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
