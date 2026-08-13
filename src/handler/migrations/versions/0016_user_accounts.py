"""user accounts: email login, sessions, reset/invite links, per-user ownership

Revision ID: 0016_user_accounts
Revises: 0015_model_harness
Create Date: 2026-08-12

Replaces "know the API key" with email + password accounts: the first account created
becomes the admin, later accounts are created by an admin (invite links), and password
resets ride the same one-shot-token table. Resources gain a nullable ``owner_user_id``
(projects, skills, connectors, plugins, model backends) — null means shared/legacy, so
an upgraded deployment behaves exactly as before until users start owning things. The
legacy env tokens keep working for scripts/CI; no data backfill is needed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from handler.db.types import PortableBigInt, PortableTimestamp

revision: str = "0016_user_accounts"
down_revision: str | None = "0015_model_harness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that gain per-user ownership. Nullable, no FK (mirrors agents.model_id: a
# deleted user must never orphan resources — delete_user reassigns rows to shared).
_OWNED_TABLES = (
    "projects",
    "claude_skills",
    "claude_connectors",
    "claude_plugins",
    "claude_models",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", PortableTimestamp, nullable=False),
        sa.Column("last_used_at", PortableTimestamp),
    )
    op.create_table(
        "auth_tokens",
        sa.Column("id", PortableBigInt, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("expires_at", PortableTimestamp, nullable=False),
        sa.Column("used_at", PortableTimestamp),
        sa.Column("created_at", PortableTimestamp, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("purpose IN ('reset', 'invite')", name="ck_auth_tokens_purpose"),
    )
    for table in _OWNED_TABLES:
        op.add_column(table, sa.Column("owner_user_id", sa.BigInteger()))


def downgrade() -> None:
    for table in _OWNED_TABLES:
        op.drop_column(table, "owner_user_id")
    op.drop_table("auth_tokens")
    op.drop_table("auth_sessions")
    op.drop_table("users")
