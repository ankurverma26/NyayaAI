"""
scripts/load_laws.py
─────────────────────
Seed script — reads every *.json file from data/laws/ and upserts
LegalSource + Section rows into the database.

JSON schema expected (see data/laws/sample_format.json):
{
  "act":            str,           # full official title (required)
  "short_name":     str | null,    # UPPERCASE with year, e.g. ICA1872
  "year":           int,           # Enactment year
  "citation":       str | null,
  "url":            str | null,
  "retrieved_on":   str | null,    # YYYY-MM-DD
  "status":         str,           # in_force | amended | repealed | draft | verify_current_status
  "jurisdiction":   str,           # india | uk | us | …
  "source_type":    str,           # act | regulation | judgment | notification | circular
  "authority":      str | null,
  "sections": [
    {
      "section_number": str,       # "27", "43A", "Schedule II" (required)
      "heading":        str | null,
      "text":           str,       # VERBATIM statutory text (required)
      "notes":          str | null # Optional editorial notes / comments
    },
    ...
  ]
}

Safety & Ingestion rules
─────────────────────────
- Any top-level key that starts with an underscore (e.g. _schema_notes) is ignored.
- Files whose name contains "sample_format" are skipped automatically.
- Files whose sections contain the literal string "PLACEHOLDER" are skipped.
- Re-running the script is strictly idempotent:
  - Existing sources are preserved and updated if fields changed.
  - Existing sections are updated only if their text hash changed.
  - New sections are appended without duplicates.
- Prints summary: files loaded, sections loaded, sections skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Allow running as `python scripts/load_laws.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.models import Base, LegalSource, Section

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = {
    "in_force",
    "amended",
    "repealed",
    "draft",
    "verify_current_status",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _text_hash(text: str) -> str:
    """Return SHA-256 hex digest of stripped text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _is_placeholder(data: dict) -> bool:
    """Return True if any section text contains the literal word PLACEHOLDER."""
    for sec in data.get("sections", []):
        if "PLACEHOLDER" in sec.get("text", ""):
            return True
    return False


def _validate(data: dict, path: Path) -> list[str]:
    """Return a list of validation error strings (empty = valid)."""
    errors: list[str] = []
    if not data.get("act"):
        errors.append("Missing required field: 'act'")

    status_val = data.get("status")
    if status_val and status_val not in ALLOWED_STATUSES:
        errors.append(
            f"Invalid status '{status_val}'. Allowed: {', '.join(sorted(ALLOWED_STATUSES))}"
        )

    if not isinstance(data.get("sections"), list) or not data["sections"]:
        errors.append("Missing or empty 'sections' array")
    else:
        for i, sec in enumerate(data["sections"]):
            sec_num = sec.get("section_number") or sec.get("number")
            if not sec_num:
                errors.append(f"sections[{i}] missing 'section_number' or 'number'")
            if not sec.get("text"):
                errors.append(f"sections[{i}] missing 'text'")
    return errors


# ── Core loader ────────────────────────────────────────────────────────────────

async def load_file(
    session: AsyncSession, path: Path, dry_run: bool = False
) -> dict[str, Any]:
    """
    Parse one JSON law file and upsert into the database.

    Returns dict with keys:
      file: filename
      status: "ok" | "skipped" | "error"
      sections_loaded: int (count of inserted or updated sections)
      sections_skipped: int (count of unchanged sections)
      message: str
    """
    result: dict[str, Any] = {
        "file": path.name,
        "status": "ok",
        "sections_loaded": 0,
        "sections_skipped": 0,
        "message": "",
    }

    # Rule 5: Skip any file whose name contains "sample_format"
    if "sample_format" in path.name.lower():
        result.update(
            status="skipped",
            message="File name contains 'sample_format' — skipped",
        )
        return result

    # Parse JSON
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.update(status="error", message=f"JSON parse error: {exc}")
        return result

    # Rule 1: Ignore any top-level key that starts with an underscore (e.g. _schema_notes)
    data = {k: v for k, v in raw_data.items() if not k.startswith("_")}

    # Skip placeholder files
    if _is_placeholder(data):
        result.update(
            status="skipped",
            message="File contains PLACEHOLDER text — skipped",
        )
        return result

    # Validate structure
    errors = _validate(data, path)
    if errors:
        result.update(status="error", message="; ".join(errors))
        return result

    file_hash = _sha256(path)
    status_str = data.get("status", "in_force")

    # Check if this source already exists
    stmt = select(LegalSource).where(LegalSource.title == data["act"])
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        # Load existing sections for this source mapped by section_number
        sec_stmt = select(Section).where(Section.source_id == existing.id)
        existing_secs = {
            s.section_number: s
            for s in (await session.execute(sec_stmt)).scalars().all()
        }

        sections_loaded = 0
        sections_skipped = 0

        for sec in data["sections"]:
            sec_num = str(sec.get("section_number") or sec.get("number"))
            sec_text = sec["text"]
            sec_heading = sec.get("heading")
            sec_notes = sec.get("notes")

            if sec_num in existing_secs:
                existing_sec = existing_secs[sec_num]
                # Check if section text hash changed
                if _text_hash(sec_text) != _text_hash(existing_sec.text):
                    if not dry_run:
                        existing_sec.text = sec_text
                        existing_sec.heading = sec_heading
                        existing_sec.notes = sec_notes
                    sections_loaded += 1
                else:
                    # Text unchanged; sync notes/heading if modified without treating as new text
                    if not dry_run:
                        if existing_sec.notes != sec_notes:
                            existing_sec.notes = sec_notes
                        if existing_sec.heading != sec_heading:
                            existing_sec.heading = sec_heading
                    sections_skipped += 1
            else:
                # New section to append
                if not dry_run:
                    new_sec = Section(
                        source_id=existing.id,
                        section_number=sec_num,
                        heading=sec_heading,
                        text=sec_text,
                        notes=sec_notes,
                    )
                    session.add(new_sec)
                sections_loaded += 1

        result["sections_loaded"] = sections_loaded
        result["sections_added"] = sections_loaded
        result["sections_skipped"] = sections_skipped

        if not dry_run:
            existing.file_hash = file_hash
            existing.retrieved_on = data.get("retrieved_on", existing.retrieved_on)
            existing.status = status_str
            existing.short_name = data.get("short_name", existing.short_name)
            existing.citation = data.get("citation", existing.citation)
            existing.url = data.get("url", existing.url)
            await session.commit()

        action_desc = "DRY-RUN would update" if dry_run else "Updated"
        if sections_loaded == 0:
            result.update(
                status="skipped",
                message=f"Already loaded (id={existing.id}, {sections_skipped} sections unchanged)",
            )
        else:
            result.update(
                status="ok",
                message=f"{action_desc} source id={existing.id} ({sections_loaded} sections updated/added, {sections_skipped} unchanged)",
            )
        return result

    # New source creation
    source = LegalSource(
        title=data["act"],
        short_name=data.get("short_name"),
        source_type=data.get("source_type", "act"),
        authority=data.get("authority"),
        jurisdiction=data.get("jurisdiction", "india"),
        status=status_str,
        citation=data.get("citation"),
        url=data.get("url"),
        retrieved_on=data.get("retrieved_on"),
        version=str(data.get("year", "")),
        file_hash=file_hash,
    )

    sections: list[Section] = []
    for sec in data["sections"]:
        sec_num = str(sec.get("section_number") or sec.get("number"))
        sections.append(
            Section(
                section_number=sec_num,
                heading=sec.get("heading"),
                text=sec["text"],
                notes=sec.get("notes"),
                source=source,
            )
        )

    result["sections_loaded"] = len(sections)
    result["sections_added"] = len(sections)
    result["sections_skipped"] = 0

    if not dry_run:
        session.add(source)
        for s in sections:
            session.add(s)
        await session.commit()
        result["message"] = f"Inserted source id={source.id} with {len(sections)} sections"
    else:
        result["message"] = f"DRY-RUN: would insert source with {len(sections)} sections"

    return result


async def load_all(
    laws_dir: Path, db_url: str, dry_run: bool = False
) -> dict[str, int]:
    """
    Load every *.json file in laws_dir into the database.
    Prints summary: files loaded, sections loaded, sections skipped.
    """
    engine = create_async_engine(
        db_url,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            from sqlalchemy import text
            res = await conn.execute(text("PRAGMA table_info(legal_sources)"))
            cols = {row[1] for row in res.fetchall()}
            if cols and "retrieved_on" not in cols:
                await conn.execute(text("ALTER TABLE legal_sources ADD COLUMN retrieved_on VARCHAR(20)"))

            res = await conn.execute(text("PRAGMA table_info(sections)"))
            cols = {row[1] for row in res.fetchall()}
            if cols and "notes" not in cols:
                await conn.execute(text("ALTER TABLE sections ADD COLUMN notes TEXT"))
        except Exception:
            pass

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    json_files = sorted(laws_dir.glob("*.json"))
    if not json_files:
        logger.warning("No *.json files found in %s", laws_dir)
        await engine.dispose()
        return {"files_loaded": 0, "sections_loaded": 0, "sections_skipped": 0}

    logger.info("Found %d JSON files in %s", len(json_files), laws_dir)

    files_loaded = 0
    sections_loaded = 0
    sections_skipped = 0

    async with session_factory() as session:
        for path in json_files:
            res = await load_file(session, path, dry_run=dry_run)
            level = logging.WARNING if res["status"] == "error" else logging.INFO
            logger.log(
                level,
                "[%-8s] %s — %s",
                res["status"].upper(),
                res["file"],
                res["message"],
            )
            if res["status"] == "ok":
                files_loaded += 1
            sections_loaded += res.get("sections_loaded", 0)
            sections_skipped += res.get("sections_skipped", 0)

    await engine.dispose()

    # Rule 6: Print a summary
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Files loaded:     {files_loaded}")
    print(f"  Sections loaded:  {sections_loaded}")
    print(f"  Sections skipped: {sections_skipped}")
    print("=" * 50 + "\n")

    return {
        "files_loaded": files_loaded,
        "sections_loaded": sections_loaded,
        "sections_skipped": sections_skipped,
    }


# ── CLI entry point ────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Indian law JSON files into the NyayaAI database."
    )
    parser.add_argument(
        "--laws-dir",
        default=str(Path(__file__).resolve().parent.parent / "data" / "laws"),
        help="Path to the directory containing *.json law files (default: data/laws/)",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="SQLAlchemy async DB URL (default: value from .env / DB_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate files without writing to the database",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )
    args = _parse_args()

    if args.db_url:
        db_url = args.db_url
    else:
        from backend.config import get_settings
        db_url = get_settings().db_url

    asyncio.run(
        load_all(
            laws_dir=Path(args.laws_dir),
            db_url=db_url,
            dry_run=args.dry_run,
        )
    )
