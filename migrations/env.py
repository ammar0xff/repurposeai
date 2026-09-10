"""Alembic env. Never auto-mutate production; migrations are explicit files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import context
from sqlalchemy import create_engine

from app.config.settings import get_settings
from app.models import Base  # noqa: F401  (model registration)

from pathlib import Path as _P

_P("./data").mkdir(parents=True, exist_ok=True)  # sqlite needs the dir, not the tables

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, future=True)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
