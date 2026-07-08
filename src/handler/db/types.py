"""Portable column types so one schema definition emits the right physical type
on both dialects.

- ``PortableJSON``  -> JSONB on Postgres, JSON-as-TEXT on SQLite.
- ``PortableTimestamp`` -> TIMESTAMPTZ on Postgres, ISO-8601 TEXT on SQLite,
  always UTC-aware in Python. Naive datetimes are normalized to UTC on bind so
  the two dialects agree.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Integer, TypeDecorator
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import JSON

# JSONB on Postgres, JSON (stored as TEXT, round-tripping dict/list) on SQLite.
PortableJSON = JSON().with_variant(postgresql.JSONB(), "postgresql")

# BIGSERIAL/BIGINT on Postgres, INTEGER on SQLite. Only ``INTEGER PRIMARY KEY`` aliases
# SQLite's rowid and autoincrements — a bare ``BIGINT PRIMARY KEY`` would be NULLable and
# would not auto-assign. Use this for autoincrementing PKs.
PortableBigInt = BigInteger().with_variant(Integer(), "sqlite")


class PortableTimestamp(TypeDecorator):
    """A timezone-aware timestamp that behaves identically on PG and SQLite.

    SQLAlchemy stores aware datetimes as ISO-8601 text on SQLite and as
    ``TIMESTAMPTZ`` on Postgres. We normalize every bound value to UTC so a naive
    datetime never silently becomes local-time on one backend and UTC on the other.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.TIMESTAMP(timezone=True))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime) and value.tzinfo is None:
            # SQLite hands back naive datetimes; they are UTC by our convention.
            return value.replace(tzinfo=UTC)
        return value
