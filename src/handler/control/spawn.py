"""Spawn orchestration: the ``.mise.toml`` gate, the agent row, the generated
settings, identity/env injection, and the tmux launch — plus the resume seam the API
calls.

Order matters: the hard ``test``-task gate is checked *before* any row is written or
process launched, so a project without a canonical test task never gets an agent
(README 3.5, resolved as a hard requirement).
"""

from __future__ import annotations

import os
import tomllib

from ..config import get_settings
from ..db import repository as repo
from ..db.engine import connection
from . import settings_gen, tmux, worktree


class SpawnError(Exception):
    """Raised when an agent cannot be spawned (missing project, no test task, ...)."""


def require_test_task(working_dir: str) -> None:
    """Hard gate: refuse to spawn unless ``.mise.toml`` defines ``[tasks.test]``."""
    mise_path = os.path.join(working_dir, ".mise.toml")
    if not os.path.exists(mise_path):
        raise SpawnError(
            f"no .mise.toml in {working_dir}: a project must define a [tasks.test] task "
            "before an agent can run against it"
        )
    with open(mise_path, "rb") as fh:
        data = tomllib.load(fh)
    tasks = data.get("tasks", {})
    if "test" not in tasks:
        raise SpawnError(
            f".mise.toml in {working_dir} has no [tasks.test]: the verification gate "
            "requires a canonical test task"
        )


def _claude_command(task: str | None, settings_path: str) -> str:
    claude = get_settings().claude_bin
    argv = [claude, "--settings", settings_path]
    if task:
        argv.append(_shell_quote(task))
    return " ".join(argv)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def spawn(
    project_id: str,
    name: str,
    *,
    subdir: str | None = None,
    worktree_branch: str | None = None,
    task: str | None = None,
) -> dict:
    """Create and launch an agent. Returns the agent row."""
    with connection() as conn:
        project = repo.get_project(conn, project_id)
        if project is None:
            raise SpawnError(f"project '{project_id}' not registered")
        if repo.get_agent_by_name(conn, project_id, name) is not None:
            raise SpawnError(f"agent '{name}' already exists in project '{project_id}'")

        working_dir = worktree.resolve_working_dir(
            project["root_dir"], name, subdir=subdir, worktree_branch=worktree_branch
        )

        # Hard gate before any state is written or process launched.
        require_test_task(working_dir)

        agent = repo.create_agent(
            conn, project_id=project_id, name=name, working_dir=working_dir, status="working"
        )

    settings_path = settings_gen.write_settings(working_dir)

    env = {
        "HANDLER_PROJECT_ID": project_id,
        "HANDLER_AGENT_NAME": name,
        "HANDLER_AGENT_ID": str(agent["id"]),
        "DATABASE_URL": get_settings().database_url,
    }
    session = tmux.session_name(project_id, name)
    command = _claude_command(task, settings_path)
    tmux.new_session(session, cwd=working_dir, command=command, env=env)
    return agent


def kill(project_id: str, name: str) -> None:
    with connection() as conn:
        agent = repo.get_agent_by_name(conn, project_id, name)
        if agent is None:
            raise SpawnError(f"agent '{name}' not found in project '{project_id}'")
        session = tmux.session_name(project_id, name)
        if tmux.has_session(session):
            tmux.kill_session(session)
        repo.set_agent_status(conn, agent["id"], "done")


def resume(agent: dict, answer: str) -> tuple[bool, str]:
    """Feed an operator's answer back to a live agent.

    The seam the API's ``/resume`` route calls (and the one tests mock). Sends the
    answer into the agent's tmux session so the waiting ``claude`` process receives it.
    """
    session = tmux.session_name(agent["project_id"], agent["name"])
    if not tmux.has_session(session):
        return False, f"no live session '{session}' to resume"
    tmux.send_keys(session, answer)
    return True, f"answer delivered to session '{session}'"
