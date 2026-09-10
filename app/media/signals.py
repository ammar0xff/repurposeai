"""Scene + silence signals. FFmpeg built-in; PySceneDetect optional upgrade."""
import re
import subprocess


def _ffmpeg(*args: str, timeout: int = 300) -> str:
    try:
        p = subprocess.run(["ffmpeg", "-hide_banner", *args],
                           capture_output=True, text=True, timeout=timeout, check=False)
        return p.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def scene_cuts(source: str, threshold: float = 0.3) -> tuple[list, str]:
    """PySceneDetect (ContentDetector) when importable, else ffmpeg select."""
    import importlib.util

    from ..core.logging import log
    if importlib.util.find_spec("scenedetect") is not None:
        try:
            from scenedetect import ContentDetector, SceneManager, open_video
            v = open_video(source)
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=27.0))
            sm.detect_scenes(v, show_progress=False)
            cuts = sorted({s.get_timecodes()[0].get_seconds() for s in sm.get_scene_list()})
            return [round(c, 2) for c in cuts if c > 0.5], "pyscene"
        except Exception as e:  # noqa: BLE001 - third-party detector; any failure -> ffmpeg fallback
            log.warning("scenedetect failed (%s); ffmpeg fallback", e)
    else:
        log.debug("scenedetect not installed; ffmpeg fallback")
    err = _ffmpeg("-i", source, "-vf",
                  f"select='gt(scene,{threshold})',showinfo", "-vsync", "v",
                  "-f", "null", "-")
    cuts = sorted({round(float(m.group(1)), 2)
                   for m in re.finditer(r"pts_time:([0-9.]+)", err)})
    return [c for c in cuts if c > 0.5], "ffmpeg-scene" if cuts or err else "none"


def silence(source: str, noise_db: int = -30, min_dur: float = 0.5) -> list:
    err = _ffmpeg("-i", source, "-af",
                  f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-")
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start: ([0-9.]+)", err)]
    ends = [float(m.group(1)) for m in re.finditer(r"silence_end: ([0-9.]+)", err)]
    return [(round(s, 2), round(e, 2)) for s, e in zip(starts, ends) if e - s >= min_dur]
