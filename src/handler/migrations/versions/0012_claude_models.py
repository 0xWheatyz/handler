"""claude model backends: local/alternative models behind the same claude binary

Revision ID: 0012_claude_models
Revises: 0011_skill_install
Create Date: 2026-07-29

Adds ``claude_models`` — operator-registered Anthropic-API-compatible endpoints (a local
Qwen/Llama behind LiteLLM or claude-code-router, an LLM gateway, …) selectable from a
per-spawn dropdown — and ``agents.model_id``, which pins an agent to the backend it was
spawned on so resumes come back up against the same one. The control layer injects a
selected row as ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_MODEL`` / ``ANTHROPIC_AUTH_TOKEN``
env into that one agent's process; no row selected keeps the worker's logged-in Claude
subscription. ``model_id`` carries no FK on purpose: deleting a backend must not orphan
agent history.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableJSON, PortableTimestamp

revision: str = "0012_claude_models"
down_revision: str | None = "0011_skill_install"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claude_models",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key_enc", sa.String()),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("small_fast_model", sa.String()),
        sa.Column("env", PortableJSON),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.add_column("agents", sa.Column("model_id", sa.BigInteger()))


def downgrade() -> None:
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("model_id")
    op.drop_table("claude_models")
