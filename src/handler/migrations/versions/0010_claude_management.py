"""claude management: skills, connectors, plugins, and permission overrides

Revision ID: 0010_claude_management
Revises: 0009_runtime_secrets
Create Date: 2026-07-23

The dashboard's Claude page becomes a management surface, not just the login flow. The
operator's skills, MCP connectors, plugins, and permission overrides live here; the
control container reads them at every launch — skills sync to the worker's user-level
``~/.claude/skills``, connectors become the run's ``--mcp-config`` file, and plugins/
permissions fold into the generated per-agent ``settings.json``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableJSON, PortableTimestamp

revision: str = "0010_claude_management"
down_revision: str | None = "0009_runtime_secrets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claude_skills",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String()),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "claude_connectors",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("transport", sa.String(), nullable=False),
        sa.Column("command", sa.String()),
        sa.Column("args", PortableJSON),
        sa.Column("env", PortableJSON),
        sa.Column("url", sa.String()),
        sa.Column("headers", PortableJSON),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "transport IN ('stdio', 'http', 'sse')", name="ck_claude_connectors_transport"
        ),
    )
    op.create_table(
        "claude_plugins",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("marketplace", sa.String(), nullable=False),
        sa.Column("marketplace_repo", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "marketplace", name="uq_claude_plugins_name_marketplace"),
    )
    op.create_table(
        "claude_config",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", PortableJSON, nullable=False),
        sa.Column("updated_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("claude_config")
    op.drop_table("claude_plugins")
    op.drop_table("claude_connectors")
    op.drop_table("claude_skills")
