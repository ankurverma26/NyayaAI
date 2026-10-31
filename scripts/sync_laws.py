"""Check the stored statutes against the official Acts on India Code (live).

  python scripts/sync_laws.py              # check every Act (uses a 6-hour download cache)
  python scripts/sync_laws.py --force      # re-download
  python scripts/sync_laws.py --no-alerts  # do not create Legal Change alerts

Needs internet. Each Act's "url" in data/laws/*.json must be the Act's PDF link on indiacode.nic.in.
The stored text is never modified; the report says what to review.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from backend.config import get_settings  # noqa: E402
from backend.database.models import Base  # noqa: E402
from backend.legal_sync.persist import run_checks  # noqa: E402


async def main_async(force: bool, alerts: bool) -> int:
    engine = create_async_engine(get_settings().db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # creates the source_checks table if missing
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        out = await run_checks(session, force=force, create_alerts=alerts)
        await session.commit()
    await engine.dispose()

    for r in out["results"]:
        print(f"\n{r['short_name'] or r['title']}: {r['outcome'].upper()}"
              f"{' (from cache)' if r['from_cache'] else ''}  {r['counts']}")
        if r["error"]:
            print(f"   {r['error']}")
        for num, info in r["sections"].items():
            if info["status"] != "verified":
                print(f"   s.{num}: {info['status']} (score {info['score']})")
                for ex in info.get("missing_examples", [])[:2]:
                    print(f"       not found in official text: ...{ex}...")
    if out["new_changes"]:
        print(f"\n{len(out['new_changes'])} Legal Change alert(s) created.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-alerts", action="store_true")
    a = ap.parse_args()
    return asyncio.run(main_async(a.force, not a.no_alerts))


if __name__ == "__main__":
    sys.exit(main())
