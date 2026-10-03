"""Save an agent trace to the agent_runs table (used by the API in Prompt 6)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import AgentRun

_STATUS = {"completed": "completed", "warning": "completed", "failed": "failed"}


async def persist_trace(session: AsyncSession, state: dict[str, Any], user_id: Optional[int] = None) -> int:
    """Insert one agent_runs row per trace step. Returns the number of rows."""
    rows = 0
    for entry in state.get("trace", []):
        session.add(AgentRun(
            contract_id=state.get("contract_id"), user_id=user_id,
            query=(state.get("query") or "")[:2000],
            step=entry["step"][:40], status=_STATUS.get(entry["status"], "completed"),
            detail=entry.get("detail"),
        ))
        rows += 1
    await session.commit()
    return rows
