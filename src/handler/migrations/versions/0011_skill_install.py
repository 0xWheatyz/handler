"""skill install-from-prompt: the command type + auxiliary skill files

Revision ID: 0011_skill_install
Revises: 0010_claude_management
Create Date: 2026-07-23

Marketplace skill pages ship an install prompt you'd normally paste into an interactive
claude. ``skill_install`` runs that prompt through a one-off headless claude in a staging
directory on the worker and imports what it fetched as managed ``claude_skills`` rows.
``claude_skill_files`` holds the auxiliary files (references/, scripts/, …) a fetched
skill ships beyond its SKILL.md, so multi-file skills survive the import and sync whole.
The commands CHECK constraint change goes through ``batch_alter_table`` so SQLite
recreates the table while Postgres alters in place (same pattern as 0005).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt

revision: str = "0011_skill_install"
down_revision: str | None = "0010_claude_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_COMMAND_TYPES = (
    "'spawn', 'kill', 'resume', 'approve', 'reject', 'forge_init', 'mise_init', "
    "'poll_ci', 'sync', 'login_start', 'login_submit'"
)
NEW_COMMAND_TYPES = OLD_COMMAND_TYPES + ", 'skill_install'"


def upgrade() -> None:
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({NEW_COMMAND_TYPES})")
    op.create_table(
        "claude_skill_files",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column(
            "skill_id",
            sa.BigInteger(),
            sa.ForeignKey("claude_skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.UniqueConstraint("skill_id", "path", name="uq_claude_skill_files_skill_path"),
    )


def downgrade() -> None:
    op.drop_table("claude_skill_files")
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({OLD_COMMAND_TYPES})")
