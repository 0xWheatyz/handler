"""headless runner: workers, runs, events, session archives

Revision ID: 0008_headless_runs
Revises: 0007_agent_pane_output
Create Date: 2026-07-21

Dormant schema for the headless ``claude -p --output-format stream-json`` runner
(nothing writes these until the runner is enabled):

- ``workers`` — worker registry + heartbeat, the reaper's liveness input.
- ``agent_runs`` — one row per headless invocation (spawn or resume), tracking the
  process's real life: status, exit code, cancel flag, final result event.
- ``agent_events`` — the persisted stream-json event log the UI reads.
- ``session_archives`` — latest claude session tar.gz per agent, so ``--resume`` works
  from any worker with no shared filesystem.
- ``agents`` gains ``session_id`` (null = legacy tmux agent, the rollout discriminator)
  and ``worker_id``; ``commands`` gains ``target_worker`` (pins login_submit to the
  worker holding the live login session).
- ``crashed`` joins the agent status vocabulary (reaper-set); the CHECK constraint
  swaps go through ``batch_alter_table`` so SQLite recreates while Postgres alters in
  place (same pattern as 0006's command type).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableJSON, PortableTimestamp

revision: str = "0008_headless_runs"
down_revision: str | None = "0007_agent_pane_output"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_AGENT_STATUSES = "'working', 'paused_for_input', 'blocked', 'done'"
NEW_AGENT_STATUSES = "'working', 'paused_for_input', 'blocked', 'done', 'crashed'"
RUN_KINDS = "'spawn', 'resume'"
RUN_STATUSES = "'running', 'completed', 'failed', 'crashed', 'canceled'"


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("hostname", sa.String()),
        sa.Column("pid", sa.BigInteger()),
        sa.Column("max_runs", sa.BigInteger()),
        sa.Column("active_runs", sa.BigInteger()),
        sa.Column("started_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("heartbeat_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("exit_code", sa.BigInteger()),
        sa.Column("result", PortableJSON),
        sa.Column("started_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", PortableTimestamp),
        sa.CheckConstraint(f"kind IN ({RUN_KINDS})", name="ck_agent_runs_kind"),
        sa.CheckConstraint(f"status IN ({RUN_STATUSES})", name="ck_agent_runs_status"),
    )
    op.create_index(
        "ix_agent_runs_status_worker", "agent_runs", ["status", "worker_id"]
    )
    op.create_table(
        "agent_events",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("session_id", sa.String()),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", PortableJSON),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_events_agent_id", "agent_events", ["agent_id", "id"])
    op.create_table(
        "session_archives",
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("agents.id"), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("archive", sa.LargeBinary(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.add_column("agents", sa.Column("session_id", sa.String()))
    op.add_column("agents", sa.Column("worker_id", sa.String()))
    op.add_column("commands", sa.Column("target_worker", sa.String()))
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_constraint("ck_agents_status", type_="check")
        batch_op.create_check_constraint(
            "ck_agents_status", f"status IN ({NEW_AGENT_STATUSES})"
        )
    with op.batch_alter_table("checkmarks", schema=None) as batch_op:
        batch_op.drop_constraint("ck_checkmarks_status", type_="check")
        batch_op.create_check_constraint(
            "ck_checkmarks_status", f"status IN ({NEW_AGENT_STATUSES})"
        )


def downgrade() -> None:
    with op.batch_alter_table("checkmarks", schema=None) as batch_op:
        batch_op.drop_constraint("ck_checkmarks_status", type_="check")
        batch_op.create_check_constraint(
            "ck_checkmarks_status", f"status IN ({OLD_AGENT_STATUSES})"
        )
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_constraint("ck_agents_status", type_="check")
        batch_op.create_check_constraint(
            "ck_agents_status", f"status IN ({OLD_AGENT_STATUSES})"
        )
    op.drop_column("commands", "target_worker")
    op.drop_column("agents", "worker_id")
    op.drop_column("agents", "session_id")
    op.drop_table("session_archives")
    op.drop_index("ix_agent_events_agent_id", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_runs_status_worker", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_table("workers")
