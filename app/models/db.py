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
    from pathlib import Path as _P
    from urllib.parse import urlparse
    u = url or get_settings().database_url
    if u.startswith("sqlite:"):
        parts = urlparse(u)
        # sqlite:////abs/path (netloc empty) vs sqlite:///rel/path
        rel = parts.path.lstrip("/") if parts.netloc in ("", ".") else parts.path
        parent = _P(rel or "./data/repurposeai.db").parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        else:
            _P("./data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(get_engine(u))
