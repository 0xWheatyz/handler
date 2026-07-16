"""agent live-output snapshot

Revision ID: 0007_agent_pane_output
Revises: 0006_mise_init_command
Create Date: 2026-07-16

Adds ``last_output`` (text) and ``output_at`` (timestamp) to ``agents``. The control
worker snapshots each working agent's tmux pane tail into these columns on its poll loop,
so the API/UI can show what a live — or wedged — agent is actually doing (the tmux socket
lives only in the control container, so the DB is the one channel the API can read). Both
are nullable and back-fill lazily on the next poll, so the migration needs no data step.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableTimestamp

revision: str = "0007_agent_pane_output"
down_revision: str | None = "0006_mise_init_command"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("last_output", sa.String()))
    op.add_column("agents", sa.Column("output_at", PortableTimestamp))


def downgrade() -> None:
    op.drop_column("agents", "output_at")
    op.drop_column("agents", "last_output")
