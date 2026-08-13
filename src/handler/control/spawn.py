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
    claude_gen,
    credentials,
    forge,
    gitops,
    headless,
    mise,
    models,
    pi_harness,
    reposync,
    settings_gen,
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
    model_id: int | None = None,
    require_tests: bool = True,
    mise_init: bool = False,
    worker_id: str | None = None,
    auto_worktree: bool = True,
) -> dict:
    """Create and launch an agent. Returns the agent row.

    ``require_tests`` is the ``[tasks.test]`` gate; the mise-init bootstrap agent runs with
    it off, because a project with no ``.mise.toml`` yet is exactly what it exists to fix.
    ``mise_init`` marks the launched agent (via ``HANDLER_MISE_INIT``) so its hooks enforce
    the bootstrap contract — create the test task, commit, and push — instead of the normal
    test gate. ``model_id`` pins the agent to a registered model backend (``claude_models``)
    instead of the worker's Claude subscription — same binary, same hooks/skills/gates,
    different ``ANTHROPIC_*`` env. ``worker_id`` identifies the calling worker container
    (headless runs record it on the run row; the CLI defaults to a pid-scoped id).

    ``auto_worktree``: when no placement is given and the root is a git repo, default to
    a fresh worktree on ``agent/<name>`` instead of the shared root checkout. The root
    only fast-forwards while parked on the default branch, so agents sharing it saw
    stale trees the moment one of them left it on a feature branch — a worktree cut
    from ``origin/HEAD`` always starts at the remote's latest push (README's "one
    working directory or git worktree per agent"). Schedule firings pass False: their
    continuity convention is a state file living in the root tree across runs.
    """
    if not task:
        # ``claude -p`` has no idle-REPL mode — an empty prompt would exit immediately
        # having done nothing, so a task is a hard requirement.
        raise SpawnError("an agent requires a task (headless claude has no idle mode)")
    sync_note = None
    with connection() as conn:
        project = repo.get_project(conn, project_id)
        if project is None:
            raise SpawnError(f"project '{project_id}' not registered")
        if repo.get_agent_by_name(conn, project_id, name) is not None:
            raise SpawnError(f"agent '{name}' already exists in project '{project_id}'")

        # Stateless workflows: start every run from the remote's latest state. An
        # existing clone is fetched — refreshing origin/* even when the root checkout is
        # parked on an agent's branch — and fast-forwarded when it sits on the default
        # branch (failure degrades to a note — a stale tree is usable, an offline forge
        # shouldn't brick spawning); a missing/empty root is cloned, and that failing is
        # fatal (there is nothing to run against). A non-empty root that isn't a git
        # repo is left alone — it's manually managed.
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

        if (
            auto_worktree
            and worktree_branch is None
            and subdir is None
            and not mise_init  # the bootstrap commits .mise.toml to the default branch
            and gitops.is_repo(root)
        ):
            # Isolation by default: without this, every no-placement spawn shares the
            # root checkout, whose tree goes stale as soon as an agent parks it off the
            # default branch. (Name reuse after a deleted agent can leave a stale
            # agent/<name> branch behind; it is then checked out as-is, same as any
            # explicitly named existing branch.)
            worktree_branch = f"agent/{name}"

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
        # Same fail-fast contract as credentials: a selected model backend that is
        # missing, disabled, or undecryptable refuses the spawn before any row exists.
        try:
            models.resolve_model(conn, model_id, require_enabled=True)
        except models.ModelError as exc:
            raise SpawnError(str(exc)) from exc

        agent = repo.create_agent(
            conn,
            project_id=project_id,
            name=name,
            working_dir=working_dir,
            status="working",
            role=role,
            model_id=model_id,
        )

    settings_path = settings_gen.write_settings(working_dir)
    # Materialize the web-managed Claude config (MCP connectors + user-level skills)
    # so this launch picks up what the operator configured in the dashboard. The skills
    # half also feeds pi-harness agents (their settings.json points at the same dir).
    # Scoped to the project's owner: shared rows plus theirs, nobody else's.
    claude_gen.apply(working_dir, visible_to=project.get("owner_user_id"))
    # Mark onboarding complete and trust this working dir in ~/.claude.json before
    # claude boots: a fresh worktree is a brand-new path, and an untrusted workspace
    # wedges/refuses a headless run with nobody at a TTY to accept the dialog. (The
    # old tmux launch path did this; it was lost when phase 4 deleted that path.)
    claude_config.ensure_onboarded(working_dir)
    env, harness = _agent_env(project, agent, token, role=role, mise_init=mise_init)

    # Verify the pinned forge version, if one is configured. Non-fatal: a version drift
    # is recorded as a warning rather than blocking the spawn, since not every agent
    # touches forge and the base image is the real pin (README 3.6, Phase 2).
    forge_note = _check_forge_version(working_dir)

    headless.launch(
        agent,
        kind="spawn",
        prompt=task,
        settings_path=settings_path,
        env=env,
        worker_id=worker_id or f"cli-{os.getpid()}",
        harness=harness,
    )
    agent = {**agent, "forge_note": forge_note, "sync_note": sync_note}
    return agent


def _agent_env(
    project: dict,
    agent: dict,
    token: str | None,
    *,
    role: str | None = None,
    mise_init: bool = False,
) -> tuple[dict[str, str], str]:
    """The environment an agent process (and therefore its hooks) runs with — identity,
    ``DATABASE_URL``, and resolved forge/git credentials — plus which harness launches
    it. Shared by spawn and the headless resume path (a resume is a brand-new process
    needing the same env)."""
    env = {
        "HANDLER_PROJECT_ID": project["id"],
        "HANDLER_AGENT_NAME": agent["name"],
        "HANDLER_AGENT_ID": str(agent["id"]),
        "DATABASE_URL": get_settings().database_url,
    }
    role = role or agent.get("role")
    if role:
        env["HANDLER_AGENT_ROLE"] = role
    if mise_init:
        # Read by the Stop / git-push hooks to enforce the bootstrap contract.
        env["HANDLER_MISE_INIT"] = "1"
    # A short read connection lets credential/host resolution consult the forge_hosts
    # registry (falling back to the built-in host map when a host has no row).
    with connection() as conn:
        # Agent pinned to a model backend: point its harness at it. Resumes are a
        # brand-new process, so this is what keeps an agent on the backend it started on
        # (a since-disabled backend may still finish; a deleted one fails loudly).
        try:
            resolved = models.resolve_model(conn, agent.get("model_id"))
        except models.ModelError as exc:
            raise SpawnError(str(exc)) from exc
        harness = models.harness_of(resolved)
        if harness == "pi":
            row, key = resolved
            # The pi config dir is regenerated per launch, same contract as the claude
            # settings/skills materialization — a row edit reaches the next run.
            pi_harness.write_config(agent["working_dir"], row, key)
            env.update(pi_harness.agent_env(agent["working_dir"], row))
        else:
            env.update(models.claude_env(resolved))
        env.update(credentials.credential_env(token, project.get("git_remote"), conn))
        if token:
            _install_git_credentials(agent["working_dir"], project.get("git_remote"), conn)
        # SSH remotes: pin the agent's git to the server's deploy key, when one is stored.
        try:
            env.update(reposync.ssh_env(project.get("git_remote"), conn))
        except reposync.SyncError as exc:
            raise SpawnError(str(exc)) from exc
    return env, harness


def _check_forge_version(working_dir: str) -> str | None:
    pin = get_settings().forge_version
    if not pin:
        return None
    ok, reported = forge.check_version(working_dir)
    if ok:
        return None
    return f"forge version pin '{pin}' not satisfied: {reported}"


def kill(project_id: str, name: str) -> None:
    """Stop an agent: flag its running run for cancel and mark the row done.

    The owning worker's supervisor polls the cancel flag and SIGTERMs its own child
    (cross-worker safe — nobody signals a process they don't own). No running run means
    the process is already gone; the status update is all that's left to do.
    """
    with connection() as conn:
        agent = repo.get_agent_by_name(conn, project_id, name)
        if agent is None:
            raise SpawnError(f"agent '{name}' not found in project '{project_id}'")
        run = repo.get_latest_run(conn, agent["id"])
        if run is not None and run["status"] == "running":
            repo.request_run_cancel(conn, run["id"])
        repo.set_agent_status(conn, agent["id"], "done")


def resume(agent: dict, answer: str, worker_id: str | None = None) -> tuple[bool, str]:
    """Feed an operator's answer back to an agent as a new ``claude -p --resume`` run.

    The seam the API's ``/resume`` route calls (and the one tests mock). The session
    transcript is materialized from the DB archive first, so ANY worker can serve the
    resume. Refuses while a run is still live (two concurrent processes on one session
    would corrupt it). When no transcript survives anywhere — the owning worker died
    before its first archive, or the row predates the headless runner — falls back to a
    *fresh* session whose prompt re-injects context from the DB (checkmark + open
    question + answer), recorded as a ``worker`` event so the UI shows the degraded
    continuity.
    """
    worker_id = worker_id or f"cli-{os.getpid()}"
    with connection() as conn:
        run = repo.get_latest_run(conn, agent["id"])
        if run is not None and run["status"] == "running":
            return False, "agent already has a live run; wait for it to finish or kill it"
        project = repo.get_project(conn, agent["project_id"])
        archive = repo.get_session_archive(conn, agent["id"])
    if project is None:
        return False, f"project '{agent['project_id']}' not registered"

    working_dir = agent["working_dir"]
    settings_path = settings_gen.write_settings(working_dir)
    claude_gen.apply(working_dir, visible_to=project.get("owner_user_id"))
    # Cross-worker resume may land in a container whose ~/.claude.json has never seen
    # this working dir — re-seed trust exactly as spawn does.
    claude_config.ensure_onboarded(working_dir)
    try:
        token = None
        with connection() as conn:
            token = credentials.resolve_for_project(project, conn)
    except credentials.CredentialError as exc:
        return False, str(exc)
    env, harness = _agent_env(project, agent, token)

    if not agent.get("session_id"):
        # Pre-headless agent row (or a spawn that never launched): nothing to --resume.
        return _resume_reinjected(agent, answer, settings_path, env, worker_id, harness)

    if harness == "pi":
        transcript = pi_harness.session_file(working_dir, agent["session_id"])
    else:
        transcript = headless.session_dir(working_dir) / f"{agent['session_id']}.jsonl"
    if archive is not None:
        try:
            headless.materialize_session(working_dir, bytes(archive["archive"]), harness=harness)
        except (OSError, ValueError) as exc:
            return False, f"could not materialize session archive: {exc}"
    elif not transcript.exists():
        return _resume_reinjected(agent, answer, settings_path, env, worker_id, harness)

    try:
        run = headless.launch(
            agent,
            kind="resume",
            prompt=answer,
            settings_path=settings_path,
            env=env,
            worker_id=worker_id,
            harness=harness,
        )
    except repo.RunConflictError:
        # Another worker won the race for this resume (two queued resume commands, or a
        # concurrent spawn) — losing loudly here beats two claude processes corrupting
        # one session transcript.
        return False, "another worker is already running this agent's session"
    return True, f"headless resume run {run['id']} started for session {agent['session_id']}"


def _resume_reinjected(
    agent: dict,
    answer: str,
    settings_path: str,
    env: dict,
    worker_id: str,
    harness: str = "claude",
) -> tuple[bool, str]:
    """Degraded resume: no transcript anywhere, so start a fresh session with the
    context rebuilt from the DB. Continuity is approximate — say so in the event log."""
    with connection() as conn:
        checkmark = repo.get_checkmark(conn, agent["id"])
        recent = repo.get_log(conn, agent["id"], limit=5)
    parts = [
        "You are resuming work you started in an earlier session whose transcript is "
        "unavailable. Reconstruct context from your checkpoint below, then continue.",
    ]
    if checkmark:
        if checkmark.get("where_it_stopped"):
            parts.append(f"Where you stopped: {checkmark['where_it_stopped']}")
        if checkmark.get("next_steps"):
            parts.append(f"Planned next steps: {checkmark['next_steps']}")
        if checkmark.get("open_question"):
            parts.append(f"You had asked: {checkmark['open_question']}")
    for entry in reversed(recent):
        if entry.get("summary"):
            parts.append(f"Earlier log: {entry['summary']}")
    parts.append(f"The operator's answer/instruction: {answer}")
    try:
        run = headless.launch(
            agent,
            kind="spawn",  # a genuinely new session (new UUID) — --resume has nothing to load
            prompt="\n\n".join(parts),
            settings_path=settings_path,
            env=env,
            worker_id=worker_id,
            harness=harness,
        )
    except repo.RunConflictError:
        return False, "another worker is already running this agent's session"
    with connection() as conn:
        repo.insert_agent_event(
            conn,
            agent["id"],
            run["id"],
            seq=0,
            type="worker",
            payload={
                "notice": "resume without transcript — context re-injected from DB",
                "previous_session_id": agent["session_id"],
            },
            session_id=run["session_id"],
        )
    return True, f"transcript unavailable; started fresh run {run['id']} with re-injected context"
