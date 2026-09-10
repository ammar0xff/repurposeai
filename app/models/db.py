"""Engine + session factory. SQLite default; Postgres via DATABASE_URL."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config.settings import get_settings
from .base import Base


def get_engine(url: str = ""):
    url = url or get_settings().database_url
    kw: dict = {"future": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kw)


def get_session_factory(url: str = ""):
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def init_db(url: str = "") -> None:
    """Create tables directly (dev/test). Production uses Alembic migrations."""
    Base.metadata.create_all(get_engine(url))
