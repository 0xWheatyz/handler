"""web management: command queue, forge hosts, operator approvals

Revision ID: 0003_web_management
Revises: 0002_forge_approvals
Create Date: 2026-07-10

Adds the ``commands`` queue/audit table (the API enqueues control actions; the
control-container worker executes them) and the ``forge_hosts`` registry (web-managed
host->token-env mapping). Also relaxes ``approvals.approved_by_agent_id`` to nullable and
adds ``approvals.actor`` so an operator can approve/reject from the dashboard without an
acting agent. Hand-written like 0001/0002 so both dialects render correctly; the
nullability change goes through ``batch_alter_table`` so SQLite (no native DROP NOT NULL)
recreates the table while Postgres uses a plain ``ALTER COLUMN``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableJSON, PortableTimestamp

revision: str = "0003_web_management"
down_revision: str | None = "0002_forge_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMMAND_TYPES = "'spawn', 'kill', 'resume', 'approve', 'reject', 'forge_init', 'poll_ci'"
COMMAND_STATUSES = "'queued', 'running', 'done', 'failed'"
FORGE_TYPES = "'github', 'gitlab', 'gitea', 'forgejo', 'bitbucket'"


def upgrade() -> None:
    # Operator approvals: drop NOT NULL on approved_by_agent_id + add the actor label.
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.alter_column(
            "approved_by_agent_id", existing_type=sa.BigInteger(), nullable=True
        )
        batch_op.add_column(sa.Column("actor", sa.String()))

    op.create_table(
        "commands",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id")),
        sa.Column("agent_name", sa.String()),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", PortableJSON),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("result", PortableJSON),
        sa.Column("error", sa.String()),
        sa.Column("requested_by", sa.String()),
        sa.Column("claimed_by", sa.String()),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("claimed_at", PortableTimestamp),
        sa.Column("finished_at", PortableTimestamp),
        sa.CheckConstraint(f"type IN ({COMMAND_TYPES})", name="ck_commands_type"),
        sa.CheckConstraint(f"status IN ({COMMAND_STATUSES})", name="ck_commands_status"),
    )
    op.create_index("ix_commands_status_id", "commands", ["status", "id"])

    op.create_table(
        "forge_hosts",
        sa.Column("hostname", sa.String(), primary_key=True),
        sa.Column("forge_type", sa.String(), nullable=False),
        sa.Column("token_env_var", sa.String()),
        sa.Column("base_url", sa.String()),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"forge_type IN ({FORGE_TYPES})", name="ck_forge_hosts_type"),
    )


def downgrade() -> None:
    op.drop_table("forge_hosts")
    op.drop_index("ix_commands_status_id", table_name="commands")
    op.drop_table("commands")
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.drop_column("actor")
        batch_op.alter_column(
            "approved_by_agent_id", existing_type=sa.BigInteger(), nullable=False
        )
