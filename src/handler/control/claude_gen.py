"""Materialize the web-managed Claude config for a launch: MCP connectors and skills.

The dashboard's Claude page edits database rows; this module is where those rows become
real files the ``claude`` process reads, applied by ``control.spawn`` before every
launch (spawn and resume both), so a change in the web UI reaches the next run of every
agent:

- **Connectors** become ``<working_dir>/.claude/mcp-servers.json`` — passed to claude as
  ``--mcp-config`` (see ``control.headless``), so nothing lands in the managed repo's
  tracked tree and a repo's own committed ``.mcp.json`` is never touched.
- **Skills** sync to the user-level ``~/.claude/skills/`` of the worker container that
  runs the agent. Each managed skill dir carries a ``.handler-managed`` marker so the
  sync can delete skills removed in the UI without ever touching skills someone
  installed by hand (or the forge role skills committed into repos by ``skills_gen``).
"""

from __future__ import annotations

import json
import os
import shutil

from sqlalchemy import Connection

from ..db import repository as repo
from ..db.engine import connection

MCP_CONFIG_RELPATH = os.path.join(".claude", "mcp-servers.json")
_MANAGED_MARKER = ".handler-managed"


def mcp_config_path(working_dir: str) -> str:
    return os.path.join(working_dir, MCP_CONFIG_RELPATH)


def _server_entry(connector: dict) -> dict:
    """One ``mcpServers`` value in claude's mcp-config shape."""
    if connector["transport"] == "stdio":
        entry: dict = {"command": connector["command"]}
        if connector.get("args"):
            entry["args"] = list(connector["args"])
        if connector.get("env"):
            entry["env"] = dict(connector["env"])
        return entry
    entry = {"type": connector["transport"], "url": connector["url"]}
    if connector.get("headers"):
        entry["headers"] = dict(connector["headers"])
    return entry


def write_mcp_config(working_dir: str, connectors: list[dict]) -> str | None:
    """Write the launch's ``--mcp-config`` file from the enabled connectors; return its
    path, or None (removing any previous one) when no connectors are enabled. The file
    lives under ``.claude/`` next to the generated ``settings.json``, and is regenerated
    every launch — deleting a connector in the UI deletes it here too."""
    path = mcp_config_path(working_dir)
    if not connectors:
        if os.path.exists(path):
            os.remove(path)
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    config = {"mcpServers": {c["name"]: _server_entry(c) for c in connectors}}
    with open(path, "w") as fh:
        json.dump(config, fh, indent=2)
    return path


def _skills_root(home: str | None = None) -> str:
    return os.path.join(home or os.path.expanduser("~"), ".claude", "skills")


def sync_user_skills(skills: list[dict], home: str | None = None) -> list[str]:
    """Sync the enabled web-managed skills into the user-level skills dir; return the
    written SKILL.md paths.

    Only dirs carrying the ``.handler-managed`` marker are ever deleted, so hand-installed
    skills survive; a managed skill disabled or deleted in the UI disappears on the next
    sync. Front-matter ``name``/``description`` come from the row; the body is the
    operator's markdown verbatim."""
    root = _skills_root(home)
    os.makedirs(root, exist_ok=True)

    keep = {s["name"] for s in skills}
    for entry in os.listdir(root):
        dir_path = os.path.join(root, entry)
        if entry not in keep and os.path.isfile(os.path.join(dir_path, _MANAGED_MARKER)):
            shutil.rmtree(dir_path, ignore_errors=True)

    written: list[str] = []
    for skill in skills:
        skill_dir = os.path.join(root, skill["name"])
        os.makedirs(skill_dir, exist_ok=True)
        description = (skill.get("description") or skill["name"]).replace("\n", " ")
        front = f"---\nname: {skill['name']}\ndescription: {description}\n---\n\n"
        body = skill["content"]
        if not body.endswith("\n"):
            body += "\n"
        path = os.path.join(skill_dir, "SKILL.md")
        with open(path, "w") as fh:
            fh.write(front + body)
        with open(os.path.join(skill_dir, _MANAGED_MARKER), "w") as fh:
            fh.write("managed by handler — edits here are overwritten at every launch\n")
        written.append(path)
    return written


def apply(working_dir: str, conn: Connection | None = None) -> dict:
    """Apply the whole web-managed config for one launch; returns a small summary."""
    if conn is None:
        with connection() as c:
            connectors = repo.list_claude_connectors(c, enabled_only=True)
            skills = repo.list_claude_skills(c, enabled_only=True)
    else:
        connectors = repo.list_claude_connectors(conn, enabled_only=True)
        skills = repo.list_claude_skills(conn, enabled_only=True)
    mcp_path = write_mcp_config(working_dir, connectors)
    written = sync_user_skills(skills)
    return {"mcp_config": mcp_path, "skills_written": len(written)}
