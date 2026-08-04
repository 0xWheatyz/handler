"""SessionStart — memory recall.

Injects the most recent memory notes in the agent's scope (its project + global) as
additional context, so knowledge distilled by earlier runs arrives without the agent
having to ask. Deterministic and cheap: titles + truncated bodies of the newest few
notes, plus a pointer at the handler-memory MCP tools for deeper search and for
writing new notes. Never blocks the session — a memory failure must not stop work.
"""

from __future__ import annotations

from sqlalchemy import Connection

from ..db import repository as repo
from .context import HookInput, Identity, emit

_NOTE_LIMIT = 8
_BODY_CHARS = 400


def _render(notes: list[dict]) -> str:
    lines = [
        "## Team memory",
        "Knowledge left by earlier agent runs and the operator. Search it with the "
        "`memory_search` tool before re-deriving how something works; save durable "
        "findings (facts, decisions, gotchas, runbooks) with `memory_save`, and "
        "connect related notes with `memory_link`.",
    ]
    if notes:
        lines.append("")
        lines.append("Most recent notes in scope (of the ones you can search):")
        for n in notes:
            scope = n["project_id"] or "global"
            body = " ".join(n["body"].split())
            if len(body) > _BODY_CHARS:
                body = body[:_BODY_CHARS] + "…"
            lines.append(f"- [#{n['id']} · {n['kind']} · {scope}] {n['title']}: {body}")
    return "\n".join(lines)


def handle(conn: Connection, ident: Identity, hook_input: HookInput) -> dict:
    try:
        notes = repo.list_memory_notes(conn, project_id=ident.project_id, limit=_NOTE_LIMIT)
    except Exception:
        notes = []  # recall is best-effort; the session must start regardless
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _render(notes),
        }
    }
    emit(result)
    return result
