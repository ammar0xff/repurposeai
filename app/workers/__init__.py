from .runner import Worker

_WORKER: Worker | None = None


def get_worker() -> Worker:
    assert _WORKER is not None, "worker not started"
    return _WORKER


def set_worker(w: Worker):
    global _WORKER
    _WORKER = w
