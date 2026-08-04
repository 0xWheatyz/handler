"""agent memory: notes + links

Revision ID: 0014_agent_memory
Revises: 0013_schedule_model
Create Date: 2026-08-04

The distilled, linked knowledge layer over the raw transcript/log history. Agents write
notes (facts, decisions, gotchas, runbooks) through the bundled handler-memory MCP
server; operators write them from the dashboard's Memory page. Links make the notes a
graph — the web of "how everything is connected" the /memory page draws. Scoped per
project or global; state lives only here, so it survives disposable workers by
construction.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableJSON, PortableTimestamp

revision: str = "0014_agent_memory"
down_revision: str | None = "0013_schedule_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_notes",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id")),
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("agents.id")),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="fact"),
        sa.Column("tags", PortableJSON),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('fact', 'decision', 'gotcha', 'runbook')", name="ck_memory_notes_kind"
        ),
    )
    op.create_index("ix_memory_notes_project_id", "memory_notes", ["project_id", "id"])
    op.create_table(
        "memory_links",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column(
            "src_note_id",
            sa.BigInteger(),
            sa.ForeignKey("memory_notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dst_note_id",
            sa.BigInteger(),
            sa.ForeignKey("memory_notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(), nullable=False, server_default="relates_to"),
        sa.Column("created_by_agent_id", sa.BigInteger(), sa.ForeignKey("agents.id")),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("src_note_id", "dst_note_id", "relation", name="uq_memory_links_edge"),
    )
    op.create_index("ix_memory_links_src", "memory_links", ["src_note_id"])
    op.create_index("ix_memory_links_dst", "memory_links", ["dst_note_id"])


def downgrade() -> None:
    op.drop_table("memory_links")
    op.drop_table("memory_notes")
