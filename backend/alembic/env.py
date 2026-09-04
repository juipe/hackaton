"""Alembic runtime configuration.

The database URL comes from ``app.core.config.settings`` rather than ``alembic.ini``
so that ``DATABASE_URL`` from the environment governs the app and the migrations
identically. Importing ``app.models`` is what populates ``Base.metadata`` — without
it autogenerate would see an empty schema and happily emit a drop for every table.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers every mapper on Base.metadata)
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Prefer an explicit ``-x db_url=...`` override, else the application settings."""
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    return override or settings.database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection.

    The engine is built directly instead of through ``engine_from_config`` because
    the URL never passes through ``alembic.ini``, where ``%`` in a password would be
    read as ConfigParser interpolation.
    """
    connectable = create_engine(_database_url(), poolclass=pool.NullPool, future=True)

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                render_as_batch=connection.dialect.name == "sqlite",
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
