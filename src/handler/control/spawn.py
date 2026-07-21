"""Spawn orchestration: the ``.mise.toml`` gate, the agent row, the generated
settings, identity/env injection, and the tmux launch — plus the resume seam the API
calls.

Order matters: the hard ``test``-task gate is checked *before* any row is written or
process launched, so a project without a canonical test task never gets an agent
(README 3.5, resolved as a hard requirement).
"""

from __future__ import annotations

import os

from ..config import get_settings
from ..db import repository as repo
from ..db.engine import connection
from . import (
    claude_config,
    credentials,
    forge,
    gitops,
    mise,
    reposync,
    settings_gen,
    tmux,
    worktree,
)


class SpawnError(Exception):
    """Raised when an agent cannot be spawned (missing project, no test task, ...)."""


def require_test_task(working_dir: str) -> None:
    """Hard gate: refuse to spawn unless a mise config defines ``[tasks.test]``."""
    if not mise.has_config(working_dir):
        raise SpawnError(
            f"no mise config (mise.toml / .mise.toml) in {working_dir}: a project must "
            "define a [tasks.test] task before an agent can run against it"
        )
    if not mise.has_test_task(working_dir):
        raise SpawnError(
            f"mise config in {working_dir} has no [tasks.test]: the verification gate "
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


def _install_git_credentials(
    working_dir: str, git_remote: str | None, conn=None
) -> None:
    """Install a repo-local git credential helper that reads the injected token.

    The helper hands back ``$FORGE_TOKEN`` from the environment, so the raw value is never
    written to disk (README 3.7: one secret servicing both forge and git), and it is
    *scoped to the forge host* so the token is never offered to an arbitrary HTTPS URL.
    A no-op for ssh/unknown remotes (deploy keys handle those). Best-effort — a
    working_dir that isn't a git repo yet shouldn't block the spawn.
    """
    cfg = credentials.git_credential_config(git_remote, conn)
    if cfg is not None:
        key, value = cfg
        gitops.config_local(working_dir, key, value)


def spawn(
    project_id: str,
    name: str,
    *,
    subdir: str | None = None,
    worktree_branch: str | None = None,
    task: str | None = None,
    role: str | None = None,
    require_tests: bool = True,
    mise_init: bool = False,
) -> dict:
    """Create and launch an agent. Returns the agent row.

    ``require_tests`` is the ``[tasks.test]`` gate; the mise-init bootstrap agent runs with
    it off, because a project with no ``.mise.toml`` yet is exactly what it exists to fix.
    ``mise_init`` marks the launched agent (via ``HANDLER_MISE_INIT``) so its hooks enforce
    the bootstrap contract — create the test task, commit, and push — instead of the normal
    test gate.
    """
    sync_note = None
    with connection() as conn:
        project = repo.get_project(conn, project_id)
        if project is None:
            raise SpawnError(f"project '{project_id}' not registered")
        if repo.get_agent_by_name(conn, project_id, name) is not None:
            raise SpawnError(f"agent '{name}' already exists in project '{project_id}'")

        # Stateless workflows: start every run from the remote's latest state. An
        # existing clone is fast-forwarded (failure degrades to a note — a stale tree is
        # usable, an offline forge shouldn't brick spawning); a missing/empty root is
        # cloned, and that failing is fatal (there is nothing to run against). A
        # non-empty root that isn't a git repo is left alone — it's manually managed.
        root = project["root_dir"]
        if project.get("git_remote"):
            if gitops.is_repo(root):
                try:
                    reposync.sync_project(project, conn)
                except reposync.SyncError as exc:
                    sync_note = str(exc)
            elif not os.path.isdir(root) or not os.listdir(root):
                try:
                    reposync.sync_project(project, conn)
                except reposync.SyncError as exc:
                    raise SpawnError(str(exc)) from exc

        try:
            working_dir = worktree.resolve_working_dir(
                project["root_dir"], name, subdir=subdir, worktree_branch=worktree_branch
            )
        except (worktree.WorktreeError, worktree.IsolationError) as exc:
            raise SpawnError(str(exc)) from exc

        # Hard gates before any state is written or process launched: the test task must
        # exist, and configured credentials must actually resolve — a broken pointer
        # should fail fast, not leave an orphaned agent row behind. The mise-init agent
        # skips the test-task gate (it's here to create that very task).
        if require_tests:
            require_test_task(working_dir)
        try:
            token = credentials.resolve_for_project(project, conn)
        except credentials.CredentialError as exc:
            raise SpawnError(str(exc)) from exc

        agent = repo.create_agent(
            conn,
            project_id=project_id,
            name=name,
            working_dir=working_dir,
            status="working",
            role=role,
        )

    settings_path = settings_gen.write_settings(working_dir)

    env = {
        "HANDLER_PROJECT_ID": project_id,
        "HANDLER_AGENT_NAME": name,
        "HANDLER_AGENT_ID": str(agent["id"]),
        "DATABASE_URL": get_settings().database_url,
    }
    if role:
        env["HANDLER_AGENT_ROLE"] = role
    if mise_init:
        # Read by the Stop / git-push hooks to enforce the bootstrap contract.
        env["HANDLER_MISE_INIT"] = "1"
    # A short read connection lets credential/host resolution consult the forge_hosts
    # registry (falling back to the built-in host map when a host has no row).
    with connection() as conn:
        env.update(credentials.credential_env(token, project.get("git_remote"), conn))
        if token:
            _install_git_credentials(working_dir, project.get("git_remote"), conn)
        # SSH remotes: pin the agent's git to the server's deploy key, when one is stored.
        try:
            env.update(reposync.ssh_env(project.get("git_remote"), conn))
        except reposync.SyncError as exc:
            raise SpawnError(str(exc)) from exc

    # Verify the pinned forge version, if one is configured. Non-fatal: a version drift
    # is recorded as a warning rather than blocking the spawn, since not every agent
    # touches forge and the base image is the real pin (README 3.6, Phase 2).
    forge_note = _check_forge_version(working_dir)

    # Mark Claude Code onboarding complete + trust the working dir before launching, so the
    # detached agent boots straight to the REPL instead of wedging on the first-run theme
    # picker / trust prompt with no human at the tmux TTY to answer it.
    claude_config.ensure_onboarded(working_dir)

    session = tmux.session_name(project_id, name)
    command = _claude_command(task, settings_path)
    tmux.new_session(session, cwd=working_dir, command=command, env=env)
    agent = {**agent, "forge_note": forge_note, "sync_note": sync_note}
    return agent


def _check_forge_version(working_dir: str) -> str | None:
    pin = get_settings().forge_version
    if not pin:
        return None
    ok, reported = forge.check_version(working_dir)
    if ok:
        return None
    return f"forge version pin '{pin}' not satisfied: {reported}"


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
