"""Pydantic request/response models. ``from_attributes`` lets us hand a DB row
mapping straight in; timestamps serialize as ISO-8601.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Roles + forge families mirrored from db.tables; Literal gives clean 422s on bad input.
Role = Literal["junior", "senior", "deploy"]
ForgeType = Literal["github", "gitlab", "gitea", "forgejo", "bitbucket"]

# credential_ref schemes an operator may set over the web. ``cmd:`` is intentionally
# excluded — it would run an arbitrary command in the control container at spawn — so the
# API rejects it even though the CLI/DB path still allows it.
_WEB_CREDENTIAL_SCHEMES = {"env", "file", "db"}


def _validate_web_credential_ref(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    scheme = value.split(":", 1)[0]
    if scheme not in _WEB_CREDENTIAL_SCHEMES:
        raise ValueError(
            f"credential_ref scheme '{scheme}' is not allowed from the API; "
            "use env:, file:, or db: (cmd: is CLI-only for safety)"
        )
    return value


# "owner/name" — the only thing an operator types when adding a project from a
# configured git server.
_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


class ProjectIn(BaseModel):
    """Register a project, in one of two modes.

    **Git-server mode** (preferred): pass ``git_server`` (a registered host) and
    ``repo`` (``owner/name``). The API derives the remote URL from the server's config
    (ssh when the server has a deploy key, https otherwise), computes ``root_dir``
    under ``PROJECTS_ROOT``, and enqueues a ``sync`` command so the worker clones it —
    where the clone lands on disk is Handler's concern, not the operator's.

    **Manual mode**: pass ``root_dir`` (an existing checkout) as before.
    """

    id: str | None = None  # defaults to a slug of the repo name in git-server mode
    root_dir: str | None = None
    git_remote: str | None = None
    credential_ref: str | None = None
    git_server: str | None = None
    repo: str | None = None

    @field_validator("credential_ref")
    @classmethod
    def _check_credential_ref(cls, v: str | None) -> str | None:
        return _validate_web_credential_ref(v)

    @model_validator(mode="after")
    def _check_mode(self) -> ProjectIn:
        if self.git_server:
            if not self.repo or not _REPO_RE.match(self.repo.strip()):
                raise ValueError("git-server mode needs 'repo' as owner/name")
            self.repo = self.repo.strip()
        elif not self.root_dir or not self.root_dir.strip():
            raise ValueError("pass either root_dir, or git_server + repo (owner/name)")
        if not self.git_server and not self.id:
            raise ValueError("id is required when registering by root_dir")
        return self


class ProjectUpdateIn(BaseModel):
    """Editable project columns; omit a field to leave it unchanged."""

    root_dir: str | None = None
    git_remote: str | None = None
    credential_ref: str | None = None

    @field_validator("credential_ref")
    @classmethod
    def _check_credential_ref(cls, v: str | None) -> str | None:
        return _validate_web_credential_ref(v)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    root_dir: str
    git_remote: str | None = None
    credential_ref: str | None = None
    created_at: datetime


class ProjectCreatedOut(ProjectOut):
    """Registration response; carries the enqueued clone command in git-server mode."""

    sync_command_id: int | None = None


class AgentIn(BaseModel):
    name: str
    working_dir: str
    status: str = "working"
    role: Role | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    name: str
    working_dir: str
    status: str
    role: Role | None = None
    created_at: datetime


class SpawnIn(BaseModel):
    """Enqueue a spawn: the worker creates the agent row + tmux process in the control
    container. ``worktree`` and ``subdir`` are mutually exclusive (worktree wins if both)."""

    name: str
    role: Role | None = None
    worktree: str | None = None
    subdir: str | None = None
    task: str | None = None


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str | None = None
    agent_name: str | None = None
    type: str
    payload: dict | None = None
    status: str
    result: dict | None = None
    error: str | None = None
    requested_by: str | None = None
    claimed_by: str | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    finished_at: datetime | None = None


class LoginSubmitIn(BaseModel):
    """The authorization code the operator pastes back after logging in at claude.com."""

    code: str = Field(min_length=1)


class HostIn(BaseModel):
    hostname: str
    forge_type: ForgeType
    token_env_var: str | None = None
    base_url: str | None = None
    # Write-only credentials. ``token`` is encrypted (HANDLER_SECRET_KEY) before it
    # touches the database and is never returned; ``generate_ssh_key`` mints a per-server
    # ed25519 deploy keypair — the public half comes back in ``ssh_public_key``.
    token: str | None = None
    generate_ssh_key: bool = False


class HostUpdateIn(BaseModel):
    forge_type: ForgeType | None = None
    token_env_var: str | None = None
    base_url: str | None = None
    token: str | None = None
    clear_token: bool = False
    regenerate_ssh_key: bool = False
    clear_ssh_key: bool = False


class HostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hostname: str
    forge_type: str
    token_env_var: str | None = None
    base_url: str | None = None
    # The public key to paste into the forge (deploy key / account key). The private
    # key and the token never leave the server; ``has_token`` says one is stored.
    ssh_public_key: str | None = None
    has_token: bool = False
    created_at: datetime


class ScheduleIn(BaseModel):
    """A recurring agent spawn: every ``interval_seconds``, run ``task`` as a fresh
    agent named ``<name_prefix>-<timestamp>``. The first run fires on the worker's next
    pass (``next_run_at`` starts at now)."""

    name_prefix: str = Field(min_length=1)
    task: str = Field(min_length=1)
    interval_seconds: int = Field(ge=10)
    role: Role | None = None
    worktree: str | None = None
    subdir: str | None = None
    enabled: bool = True


class ScheduleUpdateIn(BaseModel):
    name_prefix: str | None = Field(default=None, min_length=1)
    task: str | None = Field(default=None, min_length=1)
    interval_seconds: int | None = Field(default=None, ge=10)
    role: Role | None = None
    worktree: str | None = None
    subdir: str | None = None
    enabled: bool | None = None


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    name_prefix: str
    task: str
    role: Role | None = None
    worktree: str | None = None
    subdir: str | None = None
    interval_seconds: int
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None = None
    last_command_id: int | None = None
    created_at: datetime


class ApprovalIn(BaseModel):
    branch: str
    status: Literal["approved", "rejected"] = "approved"
    agent_name: str | None = None  # read HEAD from this agent's working dir when no sha
    sha: str | None = None
    pr: str | None = None
    note: str | None = None


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    branch: str
    approved_sha: str | None = None
    pr_ref: str | None = None
    status: str
    approved_by_agent_id: int | None = None
    actor: str | None = None
    note: str | None = None
    created_at: datetime


class CheckmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: int
    checkpoint_at: datetime
    status: str
    where_it_stopped: str | None = None
    next_steps: list[str] | None = None
    open_question: str | None = None
    log_entry_id: int | None = None
    tests_status: str
    tested_at: datetime | None = None
    build_status: str
    built_at: datetime | None = None


class LogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    created_at: datetime
    session_id: str | None = None
    status: str
    summary: str | None = None
    decisions: str | None = None
    question: str | None = None
    answer: str | None = None
    visibility: str
    push_sha: str | None = None
    ci_status: str
    ci_checked_at: datetime | None = None


class AnswerIn(BaseModel):
    answer: str
    # If omitted, the answer targets the agent's latest open question.
    log_entry_id: int | None = None


class AnswerOut(BaseModel):
    log_entry_id: int
    answered: bool


class ResumeIn(BaseModel):
    # Optional explicit answer to feed back; if omitted, the stored answer is used.
    answer: str | None = None


class ResumeOut(BaseModel):
    agent: str
    resumed: bool
    detail: str


class SharedContextIn(BaseModel):
    value: str


class SharedContextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    set_by_agent_id: int | None = None
    updated_at: datetime
