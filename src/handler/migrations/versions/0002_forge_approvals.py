"""forge phase 2: agent role + approvals

Revision ID: 0002_forge_approvals
Revises: 0001_initial
Create Date: 2026-07-08

Adds the nullable ``agents.role`` column (junior | senior | deploy, informational) and
the ``approvals`` table the hard deploy/merge gate checks (README Phase 2). Hand-written
like 0001 so both dialects render correctly; SQLite supports ``ALTER TABLE ADD COLUMN``
natively, so a plain ``op.add_column`` works on both backends.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableTimestamp

revision: str = "0002_forge_approvals"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPROVAL_STATUSES = "'approved', 'rejected'"


def upgrade() -> None:
    op.add_column("agents", sa.Column("role", sa.String()))

    op.create_table(
        "approvals",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("branch", sa.String(), nullable=False),
        sa.Column("approved_sha", sa.String()),
        sa.Column("pr_ref", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "approved_by_agent_id",
            sa.BigInteger(),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("note", sa.String()),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"status IN ({APPROVAL_STATUSES})", name="ck_approvals_status"),
    )
    op.create_index("ix_approvals_project_branch", "approvals", ["project_id", "branch"])


def downgrade() -> None:
    op.drop_index("ix_approvals_project_branch", table_name="approvals")
    op.drop_table("approvals")
    op.drop_column("agents", "role")
