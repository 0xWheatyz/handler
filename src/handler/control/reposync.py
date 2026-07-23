"""Clone-or-fetch a project's repository — the stateless "always pull" step.

Where a clone lands on disk is Handler's concern, not the operator's: the API computes
``root_dir`` under ``PROJECTS_ROOT`` at registration, and this module makes the checkout
real. Auth comes from the project's git server: an HTTPS remote uses the stored token
through the scoped credential helper (token only ever in the process environment); an
SSH remote uses the server's deploy key, materialized to a 0600 file and pinned via
``GIT_SSH_COMMAND`` / repo-local ``core.sshCommand``.
"""

from __future__ import annotations

import os

from sqlalchemy import Connection

from .. import sshkeys
from ..db.engine import connection
from . import credentials, gitops


class SyncError(Exception):
    """Raised when a project's repo cannot be cloned or pulled."""


def _auth_context(
    project: dict, conn: Connection
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """(env, one-shot git config) that authenticates git against the project's remote."""
    remote = project["git_remote"]
    try:
        token = credentials.resolve_for_project(project, conn)
    except credentials.CredentialError as exc:
        raise SyncError(str(exc)) from exc

    env: dict[str, str] = credentials.credential_env(token, remote, conn)
    config: list[tuple[str, str]] = []
    if token:
        helper = credentials.git_credential_config(remote, conn)
        if helper is not None:
            config.append(helper)

    env.update(ssh_env(remote, conn))
    return env, config


def ssh_env(git_remote: str | None, conn: Connection) -> dict[str, str]:
    """``GIT_SSH_COMMAND`` pinned to the server's deploy key, when one is stored.

    Empty for hosts without a stored key (ambient ssh config still applies). Raises
    :class:`SyncError` when a stored key exists but cannot be decrypted — a broken
    secret should fail loudly, not silently fall back to unauthenticated ssh.
    """
    host = credentials.remote_host(git_remote)
    if not host:
        return {}
    from ..db import repository as repo

    host_row = repo.get_host(conn, host)
    if not host_row or not host_row.get("ssh_private_key_enc"):
        return {}
    from .. import secretstore

    try:
        private_key = secretstore.decrypt(host_row["ssh_private_key_enc"])
    except secretstore.SecretStoreError as exc:
        raise SyncError(f"SSH key for git server '{host}': {exc}") from exc
    key_path = sshkeys.materialize_private_key(host, private_key)
    return {"GIT_SSH_COMMAND": sshkeys.git_ssh_command(key_path)}


def sync_project(project: dict, conn: Connection | None = None) -> dict:
    """Clone the project's remote into ``root_dir``, or refresh an existing clone.

    Idempotent by design — scheduled/stateless runs call this before every spawn so the
    working tree always starts from the remote's latest state. An existing clone is
    ``git fetch``\\ ed rather than pulled: a pull only moves the branch the root happens
    to have checked out, and an agent parked on a feature branch used to leave
    ``origin/*`` (and therefore every branch cut for a new agent) hours stale. After
    the fetch, ``origin/HEAD`` is re-pinned and the checkout is fast-forwarded only
    when it is sitting on the default branch. Raises :class:`SyncError` when the
    project has no remote or git fails.
    """
    remote = project.get("git_remote")
    root = project["root_dir"]
    if not remote:
        raise SyncError(f"project '{project['id']}' has no git_remote to sync from")

    if conn is None:
        with connection() as fresh:
            env, config = _auth_context(project, fresh)
    else:
        env, config = _auth_context(project, conn)

    if gitops.is_repo(root):
        ok, out = gitops.fetch(root, env=env)
        if not ok:
            raise SyncError(f"fetch failed in {root}: {out}")
        # Best-effort: worktree spawns cut new branches from origin/HEAD, so keep it
        # pinned even for clones that predate it (or whose remote default changed).
        gitops.set_default_head(root, env=env)
        detail = out
        default_ref = gitops.default_branch_ref(root)
        if default_ref and gitops.current_branch(root) == default_ref.split("/", 1)[1]:
            ok, ff_out = gitops.merge_ff(root, default_ref)
            if not ok:
                raise SyncError(
                    f"fast-forward of {default_ref} failed in {root}: {ff_out}"
                )
            detail = ff_out or detail
        return {"action": "pulled", "root_dir": root, "detail": detail}

    os.makedirs(os.path.dirname(root) or ".", exist_ok=True)
    ok, out = gitops.clone(remote, root, env=env, config=config)
    if not ok:
        raise SyncError(f"clone of {remote} failed: {out}")
    # Persist auth into the fresh clone so later pulls — and the agents working in it —
    # authenticate without re-deriving anything: the scoped credential helper for HTTPS,
    # the pinned deploy key for SSH.
    for key, value in config:
        gitops.config_local(root, key, value)
    if "GIT_SSH_COMMAND" in env:
        gitops.config_local(root, "core.sshCommand", env["GIT_SSH_COMMAND"])
    return {"action": "cloned", "root_dir": root, "detail": out}
