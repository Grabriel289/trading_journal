"""Alembic env — wires CryptoJournal's models + DB URL into Alembic.

Key choices:
- Database URL pulled from `backend.config.DATABASE_URL` so we have a single
  source of truth (defaults to SQLite; the future PG migration just swaps URL).
- `render_as_batch=True` so column adds/alters on SQLite work via the
  table-rebuild dance — without it, SQLite would refuse the ALTER.
- `compare_type=True` so autogenerate detects type changes, not only additions.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from backend.config import DATABASE_URL
from backend.db.database import Base

# Importing the package triggers `backend/models/__init__.py`, which itself
# imports every model module. Any new model added to that __init__ is picked
# up automatically — Alembic will see it on the next autogenerate.
import backend.models  # noqa: F401


config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
