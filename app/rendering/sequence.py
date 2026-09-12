"""Montage rendering: sequence items -> per-item clips -> xfade stitch.

Transitions apply *into* an item from the one before it (item 0's transition
is ignored). Pure filter-fragments (xfade) are built by montage_filter so the
stitching math is unit-testable without ffmpeg.
"""
import subprocess
import time
from pathlib import Path

from ..core.errors import MediaError
from ..media.analyze import ffprobe

TRANSITIONS = {
    "crossfade": "fade",
    "dissolve": "dissolve",
    "zoom": "zoomin",
    "slide_left": "slideleft",
    "slide_right": "slideright",
    "slide_up": "slideup",
    "slide_down": "slidedown",
    "wipe": "wipeleft",
}
DEFAULT_TRANSITION = "crossfade"
DEFAULT_TRANSITION_DURATION = 0.8
MIN_TRANSITION = 0.05


def xfade_name(transition: str | None) -> str | None:
    """Map our transition vocabulary onto ffmpeg xfade transitions.

    Unknown names pass through and let ffmpeg validate. cut/none -> None
    (montage_filter renders it as a hard cut).
    """
    t = (transition or DEFAULT_TRANSITION).strip().lower()
    if t in ("cut", "none"):
        return None
    return TRANSITIONS.get(t, t)


def montage_filter(durations: list[float], transitions: list[str | None],
                   trans_durations: list[float], fps: int = 30) -> tuple[str, str, str, float]:
    """Build one filter_complex string stitching N inputs. No binary involved.

    durations[i] is input i's length in seconds; transitions[i] (i>=1) fades
    input i in over trans_durations[i]. Returns
    (filter_complex, vlabel, alabel, final_duration).
    """
    n = len(durations)
    if n == 0:
        raise ValueError("montage needs at least one item")
    graph: list[str] = []
    for i in range(n):
        graph.append(f"[{i}:v]trim=duration={durations[i]:.4f},"
                     f"setpts=PTS-STARTPTS,fps={fps},format=yuv420p[v{i}]")
        graph.append(f"[{i}:a]atrim=duration={durations[i]:.4f},"
                     f"asetpts=PTS-STARTPTS,"
                     f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
    if n == 1:
        return ";".join(graph), "[v0]", "[a0]", durations[0]
    vid_in, aud_in, total = "[v0]", "[a0]", durations[0]
    for i in range(1, n):
        name = xfade_name(transitions[i] if i < len(transitions) else DEFAULT_TRANSITION)
        td = trans_durations[i] if i < len(trans_durations) else DEFAULT_TRANSITION_DURATION
        td = max(0.0, min(float(td), durations[i - 1], durations[i]))
        if name is None or td < MIN_TRANSITION:
            name, td = "fade", MIN_TRANSITION
        offset = max(total - td, 0.0)
        vout, aout = f"[x{i}]", f"[y{i}]"
        graph.append(f"{vid_in}[v{i}]xfade=transition={name}:duration={td:.4f}:"
                     f"offset={offset:.4f}{vout}")
        graph.append(f"{aud_in}[a{i}]acrossfade=d={td:.4f}:c1=tri:c2=tri{aout}")
        vid_in, aud_in, total = vout, aout, total + durations[i] - td
    return ";".join(graph), vid_in, aud_in, total


def _duration(path: str, ffprobe_bin: str = "ffprobe") -> float:
    info = ffprobe(path, ffprobe_bin)
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    if dur <= 0:
        raise MediaError(f"Montage input has no duration: {path}")
    return dur


def render_sequence(inputs: list[str], transitions: list[str | None],
                    trans_durations: list[float], out: str,
                    fps: int = 30, ffmpeg: str = "ffmpeg",
                    crf: int = 20, preset: str = "veryfast") -> dict:
    """Transcode inputs into one stitched montage at <out>. Reuses existing
    rendered clips; re-encodes only the seam via xfade/acrossfade."""
    if not inputs:
        raise MediaError("Montage needs at least one item.")
    t0 = time.time()
    durations = [_duration(p, _probe_bin(ffmpeg)) for p in inputs]
    fchain, vlabel, alabel, total = montage_filter(durations, transitions, trans_durations, fps)
    cmd = [ffmpeg, "-y", "-v", "error"]
    for p in inputs:
        cmd += ["-i", p]
    cmd += ["-filter_complex", fchain, "-map", vlabel, "-map", alabel,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-threads", "2", "-x264-params", "rc-lookahead=10",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out]
    try:
        subprocess.run(cmd, check=True, timeout=3600)
    except FileNotFoundError as e:
        raise MediaError("FFmpeg not found.", details=str(e)) from e
    except subprocess.TimeoutExpired as e:
        raise MediaError("Montage render timed out.", details=str(e)) from e
    except subprocess.CalledProcessError as e:
        raise MediaError("FFmpeg could not stitch the montage.",
                         details=(e.stderr or (e.stdout or ""))[-500:]) from e
    size = Path(out).stat().st_size
    if size == 0:
        raise MediaError("Montage render produced a zero-byte file.")
    return {"input_durations": durations, "size": size,
            "final_duration": round(total, 2),
            "elapsed": round(time.time() - t0, 2)}


def _probe_bin(ffmpeg: str) -> str:
    return "ffprobe" if ffmpeg == "ffmpeg" else str(Path(ffmpeg).with_name("ffprobe"))