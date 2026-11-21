from logging.config import fileConfig

from alembic import context
from sqlalchemy import URL, create_engine, make_url

from app import agents, catalog, connections, flows, runs, secrets, workspaces  # noqa: F401  (register models on Base.metadata)
from app.db import Base
from app.settings import get_settings, query_options

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
url = get_settings().database_url
LOCK_TIMEOUT_OPTION = "-clock_timeout=30s"


def with_lock_timeout(database_url: str) -> URL:
    """Fail a migration that cannot get its table lock instead of hanging the deploy behind it."""
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        return parsed
    options = " ".join(filter(None, [query_options(parsed), LOCK_TIMEOUT_OPTION]))
    return parsed.update_query_dict({"options": options})


if context.is_offline_mode():
    # `alembic upgrade head --sql`: print the SQL instead of running it.
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    # Migrations run once at startup, so a sync connection is enough (no event loop needed).
    with create_engine(with_lock_timeout(url)).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
