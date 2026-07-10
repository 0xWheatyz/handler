"""Pydantic request/response models. ``from_attributes`` lets us hand a DB row
mapping straight in; timestamps serialize as ISO-8601.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

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


class ProjectIn(BaseModel):
    id: str
    root_dir: str
    git_remote: str | None = None
    credential_ref: str | None = None

    @field_validator("credential_ref")
    @classmethod
    def _check_credential_ref(cls, v: str | None) -> str | None:
        return _validate_web_credential_ref(v)


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


class HostIn(BaseModel):
    hostname: str
    forge_type: ForgeType
    token_env_var: str | None = None
    base_url: str | None = None


class HostUpdateIn(BaseModel):
    forge_type: ForgeType | None = None
    token_env_var: str | None = None
    base_url: str | None = None


class HostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hostname: str
    forge_type: str
    token_env_var: str | None = None
    base_url: str | None = None
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
