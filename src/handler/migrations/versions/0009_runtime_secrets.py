"""runtime_secrets: encrypted control-plane key/value store

Revision ID: 0009_runtime_secrets
Revises: 0008_headless_runs
Create Date: 2026-07-21

A small Fernet-encrypted key/value table (values encrypted with ``HANDLER_SECRET_KEY``
before insert, same policy as ``forge_hosts.token_enc``). First use: the claude OAuth
credential bundle — the interactive ``/login`` flow completes on one worker container,
and every other worker materializes the bundle from here at startup/refresh so any of
them can run headless ``claude -p`` without shared files.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableTimestamp

revision: str = "0009_runtime_secrets"
down_revision: str | None = "0008_headless_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_secrets",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value_enc", sa.String(), nullable=False),
        sa.Column("updated_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("runtime_secrets")
