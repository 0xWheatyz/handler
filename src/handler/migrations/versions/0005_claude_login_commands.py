"""claude web-login command types

Revision ID: 0005_claude_login_commands
Revises: 0004_git_servers_schedules
Create Date: 2026-07-13

Adds the ``login_start`` and ``login_submit`` command types so the dashboard can drive
the bundled ``claude`` binary's ``/login`` OAuth flow inside the control container: the
worker opens an interactive ``claude`` session, selects the subscription account, returns
the claude.com authorization URL for the operator to open, and later feeds back the code
they paste. The commands CHECK constraint change goes through ``batch_alter_table`` so
SQLite recreates the table while Postgres alters in place (same pattern as 0004's
``sync``).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_claude_login_commands"
down_revision: str | None = "0004_git_servers_schedules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_COMMAND_TYPES = (
    "'spawn', 'kill', 'resume', 'approve', 'reject', 'forge_init', 'poll_ci', 'sync'"
)
NEW_COMMAND_TYPES = OLD_COMMAND_TYPES + ", 'login_start', 'login_submit'"


def upgrade() -> None:
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({NEW_COMMAND_TYPES})")


def downgrade() -> None:
    with op.batch_alter_table("commands", schema=None) as batch_op:
        batch_op.drop_constraint("ck_commands_type", type_="check")
        batch_op.create_check_constraint("ck_commands_type", f"type IN ({OLD_COMMAND_TYPES})")
