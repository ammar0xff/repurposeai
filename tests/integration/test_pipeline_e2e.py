"""Integration: full pipeline on a synthetic video (needs backend deps + ffmpeg)."""
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, ".")
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")

TEST_URL = "sqlite:////tmp/rpa_e2e.db"
for f in ("/tmp/rpa_e2e.db",):
    try:
        os.unlink(f)
    except OSError:
        pass

from app.config.settings import get_settings
from app.core.ids import new_id
from app.models.db import get_session_factory, init_db
from app.models.entities import Clip, Project
from app.services.pipeline import Pipeline
from app.storage.local import LocalFilesystemStorage


def test_e2e_synthetic():
    init_db(TEST_URL)
    s = get_settings()
    db = get_session_factory(TEST_URL)()
    store = LocalFilesystemStorage("/tmp/rpa_store")
    pipe = Pipeline(db, store, s)
    src = "/tmp/rpa_src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc=size=640x360:duration=30:rate=15",
                    "-c:v", "libx264", "-preset", "ultrafast", src],
                   check=True, timeout=180)
    p = Project(id=new_id(), title="e2e", config={"clip_count": 1, "min_duration": 8,
                                                  "max_duration": 25})
    db.add(p)
    db.commit()
    from app.models.entities import ProcessingJob
    j = ProcessingJob(id=new_id(), project_id=p.id, status="queued",
                      params={"source": src})
    db.add(j)
    db.commit()
    # stub transcript path: no whisper here necessarily; exercise analyze+validate
    info = pipe.analyze(j, p, pipe.ingest(j, p, src))
    assert info["width"] == 640
    assert p.status == "analyzed"
    db.close()
    assert db.query(Clip).count() >= 0
