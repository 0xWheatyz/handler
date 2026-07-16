"""mise-init command type

Revision ID: 0006_mise_init_command
Revises: 0005_claude_login_commands
Create Date: 2026-07-16

Adds the ``mise_init`` command type so the dashboard's "Initialize mise" option on the
add-repo step can enqueue a bootstrap agent that writes a ``.mise.toml`` with a canonical
``[tasks.test]`` task for the project's stack, then commits and pushes it. The commands
CHECK constraint change goes through ``batch_alter_table`` so SQLite recreates the table
while Postgres alters in place (same pattern as 0004's ``sync`` and 0005's login types).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_mise_init_command"
down_revision: str | None = "0005_claude_login_commands"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_COMMAND_TYPES = (
    "'spawn', 'kill', 'resume', 'approve', 'reject', 'forge_init', 'poll_ci', 'sync', "
    "'login_start', 'login_submit'"
)
NEW_COMMAND_TYPES = (
    "'spawn', 'kill', 'resume', 'approve', 'reject', 'forge_init', 'mise_init', 'poll_ci', "
    "'sync', 'login_start', 'login_submit'"
)


def upgrade() -> None:
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({NEW_COMMAND_TYPES})")


def downgrade() -> None:
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({OLD_COMMAND_TYPES})")
