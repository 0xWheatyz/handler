"""Pydantic request/response models. ``from_attributes`` lets us hand a DB row
mapping straight in; timestamps serialize as ISO-8601.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectIn(BaseModel):
    id: str
    root_dir: str
    git_remote: str | None = None
    credential_ref: str | None = None


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


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: str
    name: str
    working_dir: str
    status: str
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
