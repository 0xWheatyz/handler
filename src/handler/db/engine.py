"""Engine construction + connection helper.

The engine is built from ``Settings.database_url``. For SQLite we register a
connect-time listener issuing ``PRAGMA foreign_keys=ON`` — SQLite leaves FK
enforcement off by default, which would make every FK (including the
checkmarks<->log_entries cycle) cosmetic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Connection, Engine, create_engine, event

from ..config import get_settings


def _make_engine(url: str) -> Engine:
    connect_args: dict = {}
    if url.startswith("sqlite"):
        # Allow use across threads (FastAPI request threads, test client).
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args, future=True)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk_pragma(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return _make_engine(get_settings().database_url)


@contextmanager
def connection() -> Iterator[Connection]:
    """A transactional connection (commit on success, rollback on error)."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn
