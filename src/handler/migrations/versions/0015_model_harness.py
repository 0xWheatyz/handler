"""model backends: harness selection (claude | pi)

Revision ID: 0015_model_harness
Revises: 0014_agent_memory
Create Date: 2026-08-12

Adds ``claude_models.harness`` — which agent binary a backend row launches. ``claude``
(the default, and what every existing row becomes) keeps the current behavior: the
``claude`` binary pointed at an Anthropic-API-compatible endpoint. ``pi`` launches the
same agent run through the lightweight `pi` coding agent instead, which speaks the
OpenAI Completions API natively — so a local vLLM/llama.cpp/Ollama endpoint needs no
Anthropic-translation proxy in front of it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_model_harness"
down_revision: str | None = "0014_agent_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "claude_models",
        sa.Column("harness", sa.String(), nullable=False, server_default="claude"),
    )


def downgrade() -> None:
    with op.batch_alter_table("claude_models", schema=None) as batch_op:
        batch_op.drop_column("harness")
