"""git servers own their credentials + scheduled agent spawns

Revision ID: 0004_git_servers_schedules
Revises: 0003_web_management
Create Date: 2026-07-10

Turns the ``forge_hosts`` registry into a full "git server" record: an encrypted forge
token (``token_enc``) and a per-server ed25519 deploy key (``ssh_public_key`` shown to
the operator, ``ssh_private_key_enc`` encrypted at rest). Adds the ``schedules`` table
for recurring agent spawns, and the ``sync`` command type (clone-or-pull a project's
repo in the control container). The commands CHECK constraint change goes through
``batch_alter_table`` so SQLite recreates the table while Postgres alters in place.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableTimestamp

revision: str = "0004_git_servers_schedules"
down_revision: str | None = "0003_web_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_COMMAND_TYPES = "'spawn', 'kill', 'resume', 'approve', 'reject', 'forge_init', 'poll_ci'"
NEW_COMMAND_TYPES = OLD_COMMAND_TYPES + ", 'sync'"


def upgrade() -> None:
    op.add_column("forge_hosts", sa.Column("token_enc", sa.String()))
    op.add_column("forge_hosts", sa.Column("ssh_public_key", sa.String()))
    op.add_column("forge_hosts", sa.Column("ssh_private_key_enc", sa.String()))

    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({NEW_COMMAND_TYPES})")

    op.create_table(
        "schedules",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name_prefix", sa.String(), nullable=False),
        sa.Column("task", sa.String(), nullable=False),
        sa.Column("role", sa.String()),
        sa.Column("worktree", sa.String()),
        sa.Column("subdir", sa.String()),
        sa.Column("interval_seconds", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", PortableTimestamp, nullable=False),
        sa.Column("last_run_at", PortableTimestamp),
        sa.Column("last_command_id", sa.BigInteger(), sa.ForeignKey("commands.id")),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_schedules_enabled_next", "schedules", ["enabled", "next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_schedules_enabled_next", table_name="schedules")
    op.drop_table("schedules")
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({OLD_COMMAND_TYPES})")
    with op.batch_alter_table("forge_hosts", schema=None) as batch_op:
        batch_op.drop_column("ssh_private_key_enc")
        batch_op.drop_column("ssh_public_key")
        batch_op.drop_column("token_enc")
