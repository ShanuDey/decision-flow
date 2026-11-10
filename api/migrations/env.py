from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import flows, runs  # noqa: F401  (register models on Base.metadata)
from app.db import Base
from app.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
url = get_settings().database_url

if context.is_offline_mode():
    # `alembic upgrade head --sql`: print the SQL instead of running it.
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    # Migrations run once at startup, so a sync connection is enough (no event loop needed).
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
