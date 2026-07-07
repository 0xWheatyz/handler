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

    # Optional generic webhook target for the Notification hook. No-op when unset.
    webhook_url: str | None = None

    # Base directory under which per-project roots / agent worktrees live.
    projects_root: str = "./projects"

    # Binary overrides so tests/CI can point at fakes.
    claude_bin: str = "claude"
    mise_bin: str = "mise"
    tmux_bin: str = "tmux"

    @property
    def effective_shared_write_token(self) -> str:
        """Token required to write shared_context; defaults to the global token."""
        return self.shared_context_write_token or self.auth_token


@lru_cache
def get_settings() -> Settings:
    return Settings()
