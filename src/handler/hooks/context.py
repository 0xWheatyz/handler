"""Hook input parsing + identity resolution.

Claude Code hook stdin carries the session context (``session_id``, ``cwd``,
``hook_event_name``, per-event extras) but *not* our agent identity — that arrives via
the environment injected at spawn (``HANDLER_AGENT_ID`` etc.). A ``cwd``->working_dir
fallback resolves the agent if the env is somehow missing.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection, select

from ..db.tables import agents


@dataclass
class HookInput:
    raw: dict[str, Any]
    event: str

    @property
    def session_id(self) -> str | None:
        return self.raw.get("session_id")

    @property
    def cwd(self) -> str | None:
        return self.raw.get("cwd")

    @property
    def tool_name(self) -> str | None:
        return self.raw.get("tool_name")

    @property
    def tool_input(self) -> dict[str, Any]:
        return self.raw.get("tool_input") or {}

    @property
    def message(self) -> str | None:
        return self.raw.get("message")

    @property
    def stop_hook_active(self) -> bool:
        return bool(self.raw.get("stop_hook_active"))

    @property
    def reason(self) -> str | None:
        return self.raw.get("reason")


@dataclass
class Identity:
    agent_id: int
    project_id: str
    agent_name: str
    working_dir: str | None = None
    # True for the mise-init bootstrap agent (env ``HANDLER_MISE_INIT``): its Stop and
    # git-push hooks enforce the "write .mise.toml, commit, push" contract rather than the
    # normal test gate.
    mise_init: bool = False
    extra: dict = field(default_factory=dict)


def read_input(event: str) -> HookInput:
    data = sys.stdin.read()
    parsed = json.loads(data) if data.strip() else {}
    return HookInput(raw=parsed, event=event)


def resolve_identity(conn: Connection, hook_input: HookInput) -> Identity | None:
    """Resolve the acting agent from env, falling back to cwd->working_dir lookup."""
    agent_id = os.environ.get("HANDLER_AGENT_ID")
    project_id = os.environ.get("HANDLER_PROJECT_ID")
    agent_name = os.environ.get("HANDLER_AGENT_NAME")

    mise_init = bool(os.environ.get("HANDLER_MISE_INIT"))
    if agent_id and project_id and agent_name:
        row = conn.execute(select(agents).where(agents.c.id == int(agent_id))).first()
        working_dir = row._mapping["working_dir"] if row else None
        return Identity(int(agent_id), project_id, agent_name, working_dir, mise_init=mise_init)

    # Fallback: match by working_dir == cwd.
    if hook_input.cwd:
        row = conn.execute(
            select(agents).where(agents.c.working_dir == hook_input.cwd)
        ).first()
        if row is not None:
            m = row._mapping
            return Identity(m["id"], m["project_id"], m["name"], m["working_dir"])

    return None


def emit(payload: dict) -> None:
    """Write a JSON hook response to stdout."""
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
