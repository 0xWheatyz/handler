"""checkmark gates gain a 'skipped' verdict

Revision ID: 0017_gate_skipped
Revises: 0016_user_accounts
Create Date: 2026-08-19

The Stop gate can now decline to run the suite when there is provably nothing to
verify — a ``scout`` role ending on a clean tree, whose whole job is to look and hand
findings on. That verdict is not ``unknown`` (we didn't look) and certainly not
``pass`` (nothing ran), so the checkmark needs a third word for it. Widening the CHECK
is additive: every existing row already holds one of the three old values.

Both gate columns move together — they share one vocabulary, and a future gate that
can be moot for the same reason should not need another migration.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017_gate_skipped"
down_revision: str | None = "0016_user_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_GATE_STATUSES = "'pass', 'fail', 'unknown'"
NEW_GATE_STATUSES = OLD_GATE_STATUSES + ", 'skipped'"

# (constraint name, column) — batch_alter_table so SQLite recreates the table while
# Postgres alters in place, the same shape migration 0004 used to widen command types.
_GATES = (("ck_checkmarks_tests", "tests_status"), ("ck_checkmarks_build", "build_status"))


def _rewrite(values: str) -> None:
    with op.batch_alter_table("checkmarks", schema=None) as batch_op:
        for name, column in _GATES:
            batch_op.drop_constraint(name, type_="check")
            batch_op.create_check_constraint(name, f"{column} IN ({values})")


def upgrade() -> None:
    _rewrite(NEW_GATE_STATUSES)


def downgrade() -> None:
    # Any row parked on the new verdict has to land somewhere the old CHECK accepts;
    # 'unknown' is the honest reading of "no verdict was recorded".
    for _, column in _GATES:
        op.execute(f"UPDATE checkmarks SET {column} = 'unknown' WHERE {column} = 'skipped'")
    _rewrite(OLD_GATE_STATUSES)
