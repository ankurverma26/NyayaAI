"""Save an agent trace to the agent_runs table (one row per step, grouped by run_id)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import AgentRun

_STATUS = {"completed": "completed", "warning": "completed", "failed": "failed"}


async def persist_trace(session: AsyncSession, state: dict[str, Any], user_id: Optional[int] = None) -> Optional[int]:
    """Insert one agent_runs row per trace step. Returns the run_id (id of the first row)."""
    trace = state.get("trace", [])
    if not trace:
        return None
    first: Optional[AgentRun] = None
    for entry in trace:
        detail = dict(entry.get("detail") or {})
        detail["timestamp"] = entry.get("timestamp")
        row = AgentRun(
            contract_id=state.get("contract_id"), user_id=user_id,
            query=(state.get("query") or "")[:2000],
            step=entry["step"][:40], status=_STATUS.get(entry["status"], "completed"),
            detail=detail,
        )
        session.add(row)
        if first is None:
            await session.flush()
            row.run_id = row.id
            first = row
        else:
            row.run_id = first.id
    await session.commit()
    return first.id if first else None
