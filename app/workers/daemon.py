"""Standalone worker entrypoint (docker worker service, bare-metal deploys).
Runs the dispatcher loop forever; jobs arrive via the DB queue."""
import time

from ..config.settings import get_settings
from ..core.logging import setup
from ..models.db import init_db
from ..services.pipeline import Pipeline
from ..storage.local import LocalFilesystemStorage
from . import set_worker
from .runner import Worker


def main() -> None:
    setup()
    st = get_settings()
    init_db()
    store = LocalFilesystemStorage(st.storage_path)
    w = Worker(lambda db: Pipeline(db, store, st), max_jobs=st.max_concurrent_jobs)
    set_worker(w)
    w.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        w.stop()


if __name__ == "__main__":
    main()
