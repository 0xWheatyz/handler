"""The schema — one ``MetaData``, six tables, mapping README section 3.1 exactly.

SQLAlchemy Core (not the ORM): the workload is a handful of explicit statements, and
Core keeps the same schema rendering correctly on both dialects with no session
lifecycle to manage across the API, CLI, and hook subprocesses.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
)

from .types import PortableBigInt, PortableJSON, PortableTimestamp

metadata = MetaData()

# Status vocabularies kept as free TEXT (README uses plain strings, not PG enums, so
# both dialects match). CheckConstraints make the allowed sets explicit and portable.
AGENT_STATUSES = ("working", "paused_for_input", "blocked", "done")
GATE_STATUSES = ("pass", "fail", "unknown")
CI_STATUSES = ("not_applicable", "pending", "pass", "fail")
VISIBILITIES = ("project", "global")


def _in(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),  # slug, e.g. "leeworks-api"
    Column("root_dir", String, nullable=False),
    Column("git_remote", String),
    # Pointer to a secret (env:VAR / file:/path / cmd:...), never the token — README 3.7.
    Column("credential_ref", String),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
)

agents = Table(
    "agents",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("project_id", String, ForeignKey("projects.id"), nullable=False),
    Column("name", String, nullable=False),  # unique within a project, not globally
    Column("working_dir", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    UniqueConstraint("project_id", "name", name="uq_agents_project_name"),
    CheckConstraint(_in("status", AGENT_STATUSES), name="ck_agents_status"),
)

log_entries = Table(
    "log_entries",
    metadata,
    Column("id", PortableBigInt, primary_key=True, autoincrement=True),
    Column("agent_id", BigInteger, ForeignKey("agents.id"), nullable=False),
    Column("created_at", PortableTimestamp, nullable=False, server_default=func.now()),
    Column("session_id", String),
    Column("status", String, nullable=False),
    Column("summary", String),
    Column("decisions", String),
    Column("question", String),
    Column("answer", String),  # filled in on resume; only field ever touched post-insert
    Column("visibility", String, nullable=False, server_default="project"),
    Column("push_sha", String),  # set if this checkpoint pushed; null otherwise
    Column("ci_status", String, nullable=False, server_default="not_applicable"),
    Column("ci_checked_at", PortableTimestamp),
    CheckConstraint(_in("visibility", VISIBILITIES), name="ck_log_visibility"),
    CheckConstraint(_in("ci_status", CI_STATUSES), name="ck_log_ci_status"),
)

checkmarks = Table(
    "checkmarks",
    metadata,
    # agent_id is PK *and* FK: "the small file that gets overwritten," one row per agent.
    Column("agent_id", BigInteger, ForeignKey("agents.id"), primary_key=True),
    Column("checkpoint_at", PortableTimestamp, nullable=False),
    Column("status", String, nullable=False),
    Column("where_it_stopped", String),
    Column("next_steps", PortableJSON),
    Column("open_question", String),
    # use_alter breaks the checkmarks <-> log_entries create-order cycle.
    Column(
        "log_entry_id",
        BigInteger,
        ForeignKey("log_entries.id", use_alter=True, name="fk_checkmarks_log_entry"),
    ),
    Column("tests_status", String, nullable=False, server_default="unknown"),
    Column("tested_at", PortableTimestamp),
    Column("build_status", String, nullable=False, server_default="unknown"),
    Column("built_at", PortableTimestamp),
    CheckConstraint(_in("status", AGENT_STATUSES), name="ck_checkmarks_status"),
    CheckConstraint(_in("tests_status", GATE_STATUSES), name="ck_checkmarks_tests"),
    CheckConstraint(_in("build_status", GATE_STATUSES), name="ck_checkmarks_build"),
)

shared_context = Table(
    "shared_context",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
    Column("set_by_agent_id", BigInteger, ForeignKey("agents.id")),
    Column("updated_at", PortableTimestamp, nullable=False, server_default=func.now()),
)
