from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from db.models import Base
from db.session import DATABASE_URL

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # a plain engine: batch mode rebuilds SQLite tables, which fails while the app's
    # engine enforces foreign keys and other tables point at the one being rebuilt
    with create_engine(DATABASE_URL).connect() as connection:
        # batch mode lets SQLite handle ALTER TABLE via table copies
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
