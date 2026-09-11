"""DB-backed worker: claims queued jobs, runs Pipeline, supports cancel.
No Redis required. Concurrency capped by MAX_CONCURRENT_JOBS."""
import datetime
import threading
import time

from ..core.logging import log
from ..models.db import get_session_factory


def _utc_naive():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def _is_stale(now, last_heartbeat, updated_at, created_at, timeout: float) -> bool:
    """True when a running job lost contact with its worker thread.

    Heartbeat column is the source of truth; falls back to updated/created for
    rows born before the column existed. All inputs are naive-UTC (as SQLite
    stores SQLAlchemy DateTime).
    """
    ts = last_heartbeat or updated_at or created_at
    if ts is None:
        return True
    return (now - ts).total_seconds() > timeout


class Worker:
    def __init__(self, make_pipeline, max_jobs: int = 2):
        self.make_pipeline = make_pipeline
        self.max_jobs = max_jobs
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._stop = False

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True, name="rpa-dispatch")
        t.start()
        log.info("worker dispatcher started (max=%d)", self.max_jobs)

    def stop(self):
        self._stop = True

    def active(self) -> list[str]:
        with self._lock:
            self._threads = {k: v for k, v in self._threads.items() if v.is_alive()}
            return list(self._threads)

    def submit(self, job_id: str):
        # No session here: the job thread owns its session (created below).
        # Sharing or prematurely closing sessions across threads corrupts
        # SQLAlchemy state (IllegalStateChangeError).
        db = get_session_factory()()
        with self._lock:
            self._threads = {k: v for k, v in self._threads.items() if v.is_alive()}
            if len(self._threads) >= self.max_jobs:
                db.close()
                return  # stays queued; dispatcher picks it up
            pipe = self.make_pipeline(db)
            th = threading.Thread(target=self._guarded, args=(pipe, job_id, db),
                                  daemon=True, name=f"rpa-{job_id[:8]}")
            self._threads[job_id] = th
            th.start()

    def _guarded(self, pipe, job_id: str, db=None):
        try:
            pipe.run(job_id)
        except Exception as e:  # noqa: BLE001 - worker must never die on job errors
            log.error("worker crash on %s: %s", job_id, e)
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception as e:  # noqa: BLE001 - best-effort cleanup
                    log.debug('session close failed: %s', e)

    def cancel(self, job_id: str):
        from ..models.entities import ProcessingJob
        from ..services.pipeline import Pipeline
        Pipeline.cancel(job_id)
        db = get_session_factory()()
        try:
            j = db.query(ProcessingJob).filter_by(id=job_id).first()
            if j and j.status in ("queued",):
                j.status = "cancelled"
                db.commit()
        finally:
            db.close()

    def _loop(self):
        from ..models.entities import ProcessingJob
        while not self._stop:
            try:
                db = get_session_factory()()
                try:
                    self._reap_stale()
                    q = db.query(ProcessingJob).filter_by(status="queued").order_by(
                        ProcessingJob.created_at).limit(self.max_jobs).all()
                    for j in q:
                        self.submit(j.id)
                finally:
                    db.close()
            except Exception as e:  # noqa: BLE001 - dispatcher loop is immortal by design
                log.error("dispatcher error: %s", e)
            time.sleep(3)

    def _reap_stale(self):
        """Mark running jobs whose worker died (crash/restart) as failed so they
        are not stuck forever and can be retried (pipeline is resumable)."""
        from ..config.settings import get_settings
        from ..models.entities import ProcessingJob
        timeout = float(get_settings().worker_stale_timeout or 900)
        db = get_session_factory()()
        try:
            now = _utc_naive()
            reaped = 0
            for j in db.query(ProcessingJob).filter(ProcessingJob.status == "running").all():
                if _is_stale(now, j.last_heartbeat, j.updated_at, j.created_at, timeout):
                    j.status = "failed"
                    j.error = (f"JobInterrupted: worker lost contact "
                               f"(no heartbeat >{int(timeout)}s)")
                    j.last_heartbeat = now
                    reaped += 1
            if reaped:
                db.commit()
                log.warning("reaped %d stale running job(s)", reaped)
        except Exception as e:  # noqa: BLE001 - reaper must never kill the dispatcher
            log.error("reaper error: %s", e)
        finally:
            db.close()
