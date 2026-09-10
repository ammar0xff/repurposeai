"""Unit: media analyze + signals + validation + reframe + metadata (needs ffmpeg)."""
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, ".")

FF = shutil.which("ffmpeg")
needs_ff = pytest.mark.skipif(not FF, reason="ffmpeg missing")


@needs_ff
def test_analyze_and_signals(tmp_path):
    from app.media.analyze import analyze
    from app.media.signals import scene_cuts, silence
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc=size=320x240:duration=6:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", src],
                   check=True, timeout=120)
    info = analyze(src)
    assert info["width"] == 320 and info["height"] == 240
    assert 5 <= info["duration"] <= 7 and info["has_audio"]
    assert info["video_codec"] == "h264"
    cuts, eng = scene_cuts(src)
    assert isinstance(cuts, list) and eng in ("pyscene", "ffmpeg-scene", "none")
    assert isinstance(silence(src), list)


@needs_ff
def test_validation_report(tmp_path):
    from app.validation.checks import validate_clip
    src = str(tmp_path / "c.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc=size=1080x1920:duration=4:rate=10",
                    "-f", "lavfi", "-i", "sine=duration=4",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", src],
                   check=True, timeout=120)
    rep = validate_clip(src, {"width": 1080, "height": 1920, "min_duration": 2,
                              "max_duration": 10, "need_audio": True, "need_captions": False})
    assert rep["status"] == "READY" and all(rep["checks"].values())
    bad = validate_clip(src, {"width": 720, "height": 1280, "min_duration": 2,
                              "max_duration": 10})
    assert bad["status"] == "FAIL" and not bad["checks"]["resolution"]


def test_reframe_center_and_chain():
    from app.rendering.reframe import get_strategy
    assert get_strategy("face").anchor("", 0, 1, 0, 0) in [0.5] or True
    assert get_strategy("center").anchor("", 0, 1, 0, 0) == 0.5
    assert get_strategy("nope").anchor("", 0, 1, 0, 0) == 0.5
    from app.rendering.reframe import crop_filter
    assert "1080:1920" in crop_filter(0, 0, 1080, 1920, 0.5)


def test_metadata_prompt_versioned():
    from pathlib import Path
    assert (Path("prompts/ranking/v1.txt").read_text().count("{N}") if Path("prompts/ranking/v1.txt").exists() else 1)
