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

    # Legacy/machine bearer token gating every API route (README 3.3). Human operators
    # now sign in with email + password (user accounts, ``/auth``); this token remains
    # for scripts/CI and as a break-glass credential, and may be left unset once
    # accounts exist.
    auth_token: str = ""

    # Optional higher-trust token for PUT /shared/context/:key. Falls back to
    # auth_token when unset (README 3.4 open question, resolved to "gate it").
    shared_context_write_token: str | None = None

    # Optional admin token gating the state-changing control surface exposed to the web:
    # enqueuing control commands (spawn/kill/resume/approve/…), project CRUD, host CRUD,
    # and credential-pointer edits. Falls back to auth_token when unset. A single global
    # token, like auth_token — per-user RBAC is future work.
    admin_token: str | None = None

    # ---- User accounts (email + password sign-in for the dashboard/API).
    # Browser session lifetime, and the validity windows for the one-shot links: a
    # password reset is short-lived; an invite (set your first password) gets a week.
    session_ttl_days: int = 30
    reset_token_ttl_hours: int = 2
    invite_token_ttl_hours: int = 168

    # ---- Outbound email (invites + password resets). Unset SMTP_HOST => email off:
    # admin flows return the invite/reset link in the response instead of mailing it.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True  # STARTTLS on a plain connection (the common 587 setup)
    smtp_ssl: bool = False  # implicit TLS from byte one (the 465 setup)

    # Base URL the emailed links point at, e.g. "https://handler.example.com". Falls
    # back to the request's own origin when unset (right for the same-origin UI).
    public_base_url: str = ""

    # Optional generic webhook target for the Notification hook. No-op when unset.
    webhook_url: str | None = None

    # ---- Web tools (handler.webtool): the agents' web_search/web_fetch, exposed to
    # pi-harness agents via the bridge extension. Search provider resolution order:
    # SEARXNG_URL (self-hosted metasearch, format=json enabled) -> BRAVE_SEARCH_API_KEY
    # (Brave Search API) -> neither = DuckDuckGo's HTML endpoint (zero-config fallback,
    # rate-limited and markup-brittle; fine for occasional lookups).
    searxng_url: str | None = None
    brave_search_api_key: str | None = None

    # Symmetric key (Fernet, urlsafe-base64) for the DB-backed secret store: git-server
    # tokens and SSH private keys are encrypted with it at rest. Generate one with
    # ``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``.
    # Unset => storing/decrypting secrets in the database is refused with a clear error.
    handler_secret_key: str = ""

    # Base directory under which per-project roots / agent worktrees live.
    projects_root: str = "./projects"

    # Binary overrides so tests/CI can point at fakes.
    claude_bin: str = "claude"
    pi_bin: str = "pi"
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

    # Wall-clock budget for the install-from-prompt one-off claude run (Claude page,
    # Skills tab). Kept under worker_stale_after by default: the run blocks the worker's
    # drain loop synchronously, and outliving the heartbeat window would get its live
    # runs falsely reaped.
    skill_install_timeout: float = 240.0

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
