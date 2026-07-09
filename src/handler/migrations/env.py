"""Alembic environment — one config for both dialects.

The URL comes from ``handler.config.Settings`` (env ``DATABASE_URL``), and
``target_metadata`` is the single schema in ``handler.db.tables``. Because the
columns use ``with_variant`` / dialect-aware types, the same migration script emits
correct DDL for both Postgres and SQLite. ``render_as_batch`` is enabled for SQLite so
any future ``ALTER`` migration works (SQLite can't ALTER most things; batch mode does a
table-copy).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from handler.config import get_settings
from handler.db.tables import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url or ""),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()
        # Explicit commit: on Python 3.12+ the pysqlite driver only flushes a DDL
        # statement when a *later* statement forces it, so without this the final
        # migration's DDL and the alembic_version stamp are rolled back on close. This
        # is a no-op when the transaction was already committed.
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
