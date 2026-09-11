"""Engine + session factory. SQLite default; Postgres via DATABASE_URL."""
import logging
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from ..config.settings import get_settings
from .base import Base

logger = logging.getLogger("repurposeai.db")


def _set_sqlite_pragmas(dbapi_conn, _record):
    """Production-safe SQLite: WAL reads/writes, 10s busy wait, FKs enforced."""
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA foreign_keys=ON")
    finally:
        cur.close()


def get_engine(url: str = ""):
    url = url or get_settings().database_url
    kw: dict = {"future": True}
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
        eng = create_engine(url, **kw)
        event.listen(eng, "connect", _set_sqlite_pragmas)
        return eng
    return create_engine(url, **kw)


def get_session_factory(url: str = ""):
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def _alembic_head_revision() -> str | None:
    """Current migration head, or None when alembic files aren't reachable."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError:
        return None
    try:
        root = Path(__file__).resolve().parent.parent.parent
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "migrations"))
        return ScriptDirectory.from_config(cfg).get_current_head()
    except (KeyError, OSError, TypeError, ValueError) as exc:
        logger.debug("alembic head lookup unavailable: %s", exc)
        return None


def _stamp_head_if_unversioned(url: str) -> None:
    """Adopt a DB born via create_all as already-migrated at alembic head.

    create_all leaves no alembic_version row, so a later `alembic upgrade`
    would replay 0001's CREATE TABLE and collide. Stamp head (schema == current
    model, migrations co-ship with models) so both paths stay consistent.
    No-op when alembic is absent, the version table is already populated, or
    the DB is unreadable.
    """
    head = _alembic_head_revision()
    if not head:
        return
    try:
        eng = get_engine(url)
        with eng.begin() as conn:
            insp = inspect(eng)
            if insp.has_table("alembic_version"):
                if conn.execute(text("select 1 from alembic_version")).first():
                    return  # already versioned
                conn.execute(
                    text("insert into alembic_version (version_num) values (:v)"),
                    {"v": head},
                )
                return
            conn.execute(
                text("create table alembic_version (version_num varchar(32) not null primary key)")
            )
            conn.execute(
                text("insert into alembic_version (version_num) values (:v)"),
                {"v": head},
            )
    except SQLAlchemyError as exc:
        logger.warning("skip alembic stamp (locked/unreadable DB): %s", exc)


def init_db(url: str = "") -> None:
    """Create tables directly (dev/test). Production uses Alembic migrations."""
    u = url or get_settings().database_url
    if u.startswith("sqlite:"):
        parts = urlparse(u)
        # sqlite:////abs/path (netloc empty) vs sqlite:///rel/path
        rel = parts.path.lstrip("/") if parts.netloc in ("", ".") else parts.path
        parent = Path(rel or "./data/repurposeai.db").parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        else:
            Path("./data").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(get_engine(u))
    _stamp_head_if_unversioned(u)