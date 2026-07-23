"""Single source of env-driven configuration.

Every entrypoint — the API app, the control CLI, and each hook subprocess — reads
the same :class:`Settings`. A spawned agent's hooks reach the same database purely
by inheriting ``DATABASE_URL`` in their environment (see ``control.spawn``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Datastore. Drives dialect selection everywhere; nothing else branches on
    # "is it sqlite" except db.upsert.
    database_url: str = "sqlite:///./handler.db"

    # The single global bearer token gating every API route (README 3.3).
    auth_token: str = ""

    # Optional higher-trust token for PUT /shared/context/:key. Falls back to
    # auth_token when unset (README 3.4 open question, resolved to "gate it").
    shared_context_write_token: str | None = None

    # Optional admin token gating the state-changing control surface exposed to the web:
    # enqueuing control commands (spawn/kill/resume/approve/…), project CRUD, host CRUD,
    # and credential-pointer edits. Falls back to auth_token when unset. A single global
    # token, like auth_token — per-user RBAC is future work.
    admin_token: str | None = None

    # Optional generic webhook target for the Notification hook. No-op when unset.
    webhook_url: str | None = None

    # Symmetric key (Fernet, urlsafe-base64) for the DB-backed secret store: git-server
    # tokens and SSH private keys are encrypted with it at rest. Generate one with
    # ``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``.
    # Unset => storing/decrypting secrets in the database is refused with a clear error.
    handler_secret_key: str = ""

    # Base directory under which per-project roots / agent worktrees live.
    projects_root: str = "./projects"

    # Binary overrides so tests/CI can point at fakes.
    claude_bin: str = "claude"
    mise_bin: str = "mise"
    tmux_bin: str = "tmux"
    forge_bin: str = "forge"
    git_bin: str = "git"

    # ---- Headless runner (claude -p --output-format stream-json): worker-owned
    # subprocesses streaming events to the DB. Agent runs are always headless; tmux
    # remains only for the interactive /login flow.
    # How many concurrent claude runs one worker container supervises; commands that would
    # start a run are left queued (for another worker) while all slots are busy.
    max_concurrent_runs: int = 4
    # Heartbeats older than this many seconds mark a worker dead; the reaper flips its
    # running runs (and their agents) to ``crashed``. Generous by design: one slow
    # synchronous command (a large clone, the interactive login flow) can hold a worker
    # between heartbeats for a minute or more, and a false reap is worse than a slow one.
    worker_stale_after: float = 300.0
    # Per-run spend cap passed as ``--max-budget-usd``. 0 disables the flag.
    run_budget_usd: float = 0.0
    # Refuse to upload a claude session archive larger than this (a runaway sidecar dir
    # shouldn't balloon the DB); the run still works, only cross-worker resume degrades.
    session_archive_max_bytes: int = 32 * 1024 * 1024
    # settings.json ``permissions.defaultMode`` for headless runs. ``-p`` auto-denies
    # anything that would prompt interactively, so this plus the allowlist below is what
    # lets normal work proceed; the PreToolUse/Stop hooks stay the hard gate.
    headless_permission_mode: str = "acceptEdits"
    # Comma-separated permission allow rules added to generated settings for headless runs.
    headless_allowed_tools: str = "Bash(git *),Bash(mise *)"

    # The pinned `forge` version (README 3.6 / Phase 2: pin, never float on @latest).
    # When set, spawn verifies the injected forge matches and records a mismatch; when
    # empty the check is skipped. Operators align this with what their base image installs.
    forge_version: str = ""

    # Branches a direct `git push` may not reach without a standing approval — this closes
    # the "merge locally, push to main" path around the forge-merge approval gate.
    protected_branches: str = "main,master"

    # Serve the bundled web UI (Phase 3) from "/" and "/static". Off => headless, API-only
    # deployment (the API contract is identical either way).
    ui_enabled: bool = True

    # Optional extra origins allowed to call the API cross-origin, for operators who host the
    # UI on a different origin than the API. Empty => no CORS middleware, same-origin only
    # (the shipped UI is same-origin and needs none). Comma-separated.
    cors_origins: str = ""

    @property
    def protected_branch_set(self) -> set[str]:
        return {b.strip() for b in self.protected_branches.split(",") if b.strip()}

    @property
    def headless_allowed_tools_list(self) -> list[str]:
        return [t.strip() for t in self.headless_allowed_tools.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_shared_write_token(self) -> str:
        """Token required to write shared_context; defaults to the global token."""
        return self.shared_context_write_token or self.auth_token

    @property
    def effective_admin_token(self) -> str:
        """Token required for the web control surface; defaults to the global token."""
        return self.admin_token or self.auth_token


@lru_cache
def get_settings() -> Settings:
    return Settings()
