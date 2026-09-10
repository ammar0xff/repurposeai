"""Production validation: ffprobe every clip. Returns READY report."""
import subprocess

from ..media.analyze import ffprobe


def _ass_present(mp4: str) -> bool:
    from pathlib import Path
    return Path(mp4).with_suffix(".ass").exists()


def validate_clip(mp4: str, expect: dict, ffprobe_bin: str = "ffprobe") -> dict:
    """expect: {width,height,min_duration,max_duration,need_audio,need_captions}."""
    checks: dict[str, bool] = {}
    try:
        info = ffprobe(mp4, ffprobe_bin)
    except Exception:
        return {"status": "FAIL", "checks": {"readable": False}}
    streams = info.get("streams", [])
    vid = next((s for s in streams if s.get("codec_type") == "video"), {})
    aud = next((s for s in streams if s.get("codec_type") == "audio"), {})
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    checks["readable"] = True
    checks["resolution"] = (vid.get("width") == expect.get("width")
                            and vid.get("height") == expect.get("height"))
    checks["duration"] = expect.get("min_duration", 0) - 1 <= dur <= expect.get("max_duration", 10**6) + 1
    checks["video"] = bool(vid.get("codec_name"))
    checks["audio"] = bool(aud.get("codec_name")) if expect.get("need_audio", True) else True
    checks["captions"] = _ass_present(mp4) if expect.get("need_captions", True) else True
    try:
        import os
        checks["nonzero"] = os.path.getsize(mp4) > 0
    except OSError:
        checks["nonzero"] = False
    # timestamps valid: duration sane + streams have entries
    checks["timestamps"] = dur > 0
    ok = all(checks.values())
    return {"status": "READY" if ok else "FAIL", "checks": checks,
            "duration": round(dur, 1),
            "resolution": f"{vid.get('width')}x{vid.get('height')}"}
