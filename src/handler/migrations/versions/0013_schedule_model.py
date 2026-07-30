"""schedules pick a model backend

Revision ID: 0013_schedule_model
Revises: 0012_claude_models
Create Date: 2026-07-29

The spawn form's model dropdown, extended to recurring spawns: ``schedules.model_id``
names the ``claude_models`` backend every fired run spawns on (null = the Claude
subscription). The worker copies it into each firing's spawn payload, so the launched
agent gets pinned exactly as a hand-spawned one would. No FK, same rationale as
``agents.model_id``: deleting a backend must make the next firing fail visibly in
Activity, not break the schedule row.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_schedule_model"
down_revision: str | None = "0012_claude_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("model_id", sa.BigInteger()))


def downgrade() -> None:
    with op.batch_alter_table("schedules", schema=None) as batch_op:
        batch_op.drop_column("model_id")
