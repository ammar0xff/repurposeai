"""DB-backed worker: claims queued jobs, runs Pipeline, supports cancel.
No Redis required. Concurrency capped by MAX_CONCURRENT_JOBS."""
import threading
import time

from ..core.logging import log
from ..models.db import get_session_factory


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
        from ..models.entities import ProcessingJob
        db = get_session_factory()()
        try:
            with self._lock:
                self._threads = {k: v for k, v in self._threads.items() if v.is_alive()}
                if len(self._threads) >= self.max_jobs:
                    return  # stays queued; dispatcher picks it up
                pipe = self.make_pipeline(db)
                th = threading.Thread(target=self._guarded, args=(pipe, job_id),
                                      daemon=True, name=f"rpa-{job_id[:8]}")
                self._threads[job_id] = th
                th.start()
        finally:
            db.close()

    def _guarded(self, pipe, job_id: str):
        try:
            pipe.run(job_id)
        except Exception as e:  # never kill the dispatcher
            log.error("worker crash on %s: %s", job_id, e)

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
                    q = db.query(ProcessingJob).filter_by(status="queued").order_by(
                        ProcessingJob.created_at).limit(self.max_jobs).all()
                    for j in q:
                        self.submit(j.id)
                finally:
                    db.close()
            except Exception as e:
                log.error("dispatcher error: %s", e)
            time.sleep(3)
