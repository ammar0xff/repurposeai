"""Unit: worker liveness (stale-reap predicate) + SQLite production PRAGMAs."""
import datetime

from app.workers.runner import _is_stale


def _dt(offset_s: int) -> datetime.datetime:
    base = datetime.datetime(2026, 9, 11, 12, 0, 0, tzinfo=datetime.UTC)
    return base + datetime.timedelta(seconds=offset_s)


def test_fresh_heartbeat_not_stale():
    assert not _is_stale(_dt(0), _dt(-60), _dt(-100), _dt(-100), timeout=900)


def test_stale_heartbeat_reaped():
    assert _is_stale(_dt(0), _dt(-901), _dt(-910), _dt(-910), timeout=900)


def test_boundary_exactly_timeout_not_stale():
    assert not _is_stale(_dt(0), _dt(-900), _dt(-901), _dt(-901), timeout=900)


def test_pre_heartbeat_rows_fall_back_to_updated():
    assert not _is_stale(_dt(0), None, _dt(-60), _dt(-200), timeout=900)


def test_pre_heartbeat_row_old_updated_reaped():
    assert _is_stale(_dt(0), None, _dt(-901), _dt(-950), timeout=900)


def test_all_none_is_stale():
    assert _is_stale(_dt(0), None, None, None, timeout=900)


def test_sqlite_pragmas_enforced(tmp_path):
    from app.models.db import get_engine
    url = f"sqlite:///{tmp_path / 'prag.db'}"
    eng = get_engine(url)
    try:
        with eng.connect() as c:
            assert c.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert c.exec_driver_sql("PRAGMA busy_timeout").scalar() == 10000
            assert c.exec_driver_sql("PRAGMA synchronous").scalar() == 1  # NORMAL
    finally:
        eng.dispose()