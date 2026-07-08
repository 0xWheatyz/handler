"""Notification -> generic webhook (README 3.2).

Fully bring-your-own: if ``WEBHOOK_URL`` is unset the hook is a no-op. The webhook is
never allowed to block the agent — failures are swallowed. A log row is written either
way so the "big log" stays complete.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import Connection

from ..config import get_settings
from ..db import repository as repo
from .context import HookInput, Identity


def handle(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    message = hook_input.message or ""
    repo.insert_log_entry(
        conn,
        agent_id=ident.agent_id,
        status="working",
        session_id=hook_input.session_id,
        summary=f"notification: {message}"[:2000],
    )

    url = get_settings().webhook_url
    if not url:
        return {}

    payload = {
        "project": ident.project_id,
        "agent": ident.agent_name,
        "message": message,
        "session_id": hook_input.session_id,
        "ts": datetime.now(UTC).isoformat(),
    }
    try:
        httpx.post(url, json=payload, timeout=5.0)
    except httpx.HTTPError:
        # Bring-your-own target; never block the agent on delivery failure.
        pass
    return {}
