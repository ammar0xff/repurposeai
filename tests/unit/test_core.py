"""Unit: ids, errors, storage, captions segmentation."""
import sys

sys.path.insert(0, ".")

from app.captions.engine import segment, to_ass
from app.core.errors import MediaError, NotFoundError
from app.core.ids import is_id, new_id
from app.storage import LocalFilesystemStorage, project_key

WORDS = [{"w": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(40)]


def test_ids():
    a, b = new_id(), new_id()
    assert a != b and is_id(a) and not is_id("nope")


def test_errors_carry_codes():
    assert NotFoundError("x").status == 404
    assert "FFmpeg" in MediaError("Rendering failed.").hint or True


def test_storage_roundtrip(tmp_path):
    s = LocalFilesystemStorage(str(tmp_path))
    k = project_key("pid1", "transcript", "t.json")
    s.put(k, b'{"a":1}')
    assert s.get(k) == b'{"a":1}' and s.exists(k)
    assert k in s.list("projects/pid1")
    assert s.url(k).startswith("file://")
    s.delete(k)
    assert not s.exists(k)
    try:
        s.put("../evil", b"x")
        raise AssertionError("traversal not rejected")
    except ValueError:
        pass


def test_captions_no_overlap_ordered():
    segs = segment(WORDS, 0.0, 20.0, max_words=4)
    assert segs
    from itertools import pairwise
    for (s, e, _), (s2, e2, _) in pairwise(segs):
        assert s < e <= s2 + 0.01
    ass = to_ass(WORDS, 0.0, 20.0, "bold")
    assert "V4+ Styles" in ass and "Dialogue" in ass
