"""Alembic environment configuration for Social Sentiment Pricing project.

This file sets up the connection to the database and links Alembic
with SQLModel models so that autogenerate works correctly.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your models here so Alembic can detect changes
from backend.models.user import User
from sqlmodel import SQLModel

# This is the Alembic Config object
config = context.config

# Set up Python logging using config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Link Alembic with your models' metadata for autogenerate
target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This mode generates SQL statements without executing them directly.
    Useful when DB access is not available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    This mode connects to the database and executes the migration scripts.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


# Determine if offline or online mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
