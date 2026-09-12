"""Montage rendering: sequence items -> per-item clips -> xfade stitch.

Transitions apply *into* an item from the one before it (item 0's transition
is ignored). Pure filter-fragments (xfade) are built by montage_filter so the
stitching math is unit-testable without ffmpeg.
"""
import os
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


LIMIT_GAIN = 0.891  # ~ -1 dBFS ceiling so xfade overlaps never clip


def montage_filter(durations: list[float], transitions: list[str | None],
                   trans_durations: list[float], fps: int = 30,
                   master_audio: bool = False) -> tuple[str, str, str, float]:
    """Build one filter_complex string stitching N inputs. No binary involved.

    durations[i] is input i's length in seconds; transitions[i] (i>=1) fades
    input i in over trans_durations[i]. Returns
    (filter_complex, vlabel, alabel, final_duration).

    With `master_audio=True` each input's audio is loudness-normalised to
    -14 LUFS / -1.5 dBTP before mixing, and the final mix passes through a
    limiter (-1 dBFS). Summed acrossfade overlaps then cannot clip.
    """
    n = len(durations)
    if n == 0:
        raise ValueError("montage needs at least one item")
    graph: list[str] = []
    for i in range(n):
        audio = (f"atrim=duration={durations[i]:.4f},"
                 f"asetpts=PTS-STARTPTS,"
                 f"aformat=sample_fmts=fltp:channel_layouts=stereo")
        graph.append(f"[{i}:v]trim=duration={durations[i]:.4f},"
                     f"setpts=PTS-STARTPTS,fps={fps},format=yuv420p[v{i}]")
        graph.append(f"[{i}:a]{audio}[a{i}]")
    if n == 1:
        built = ";".join(graph)
        if master_audio:
            built += ";[a0]alimiter=limit=0.891[amaster]"
            return built, "[v0]", "[amaster]", durations[0]
        return built, "[v0]", "[a0]", durations[0]
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
    built = ";".join(graph)
    if master_audio:
        built += f";{aud_in}alimiter=limit={LIMIT_GAIN}[amaster]"
        return built, vid_in, "[amaster]", total
    return built, vid_in, aud_in, total


def _duration(path: str, ffprobe_bin: str = "ffprobe") -> float:
    info = ffprobe(path, ffprobe_bin)
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    if dur <= 0:
        raise MediaError(f"Montage input has no duration: {path}")
    return dur


def _run_stitch(inputs: list[str], fchain: str, vlabel: str, alabel: str,
                out: str, ffmpeg: str, crf: int, preset: str) -> None:
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


def render_sequence(inputs: list[str], transitions: list[str | None],
                    trans_durations: list[float], out: str,
                    fps: int = 30, ffmpeg: str = "ffmpeg",
                    crf: int = 20, preset: str = "veryfast") -> dict:
    """Transcode inputs into one stitched montage at <out>.

    xfade holds the whole previous stream in memory while it waits for the
    transition offset, so a single N-input filter graph needs ~1.5 streams of
    decoded frames for every input (60s @ 1080x1920 ~= 5.6 GB for 5 clips).
    This box has 2 GB, so for N > 2 we stitch pairwise, chaining each result
    into the next step so the encode is always bounded to two streams
    (re-encoding only the seam each time).
    """
    if not inputs:
        raise MediaError("Montage needs at least one item.")
    t0 = time.time()
    durations = [_duration(p, _probe_bin(ffmpeg)) for p in inputs]
    _, _, _, total = montage_filter(durations, transitions, trans_durations, fps)

    if len(inputs) <= 2:
        fchain, vlabel, alabel, _ = montage_filter(durations, transitions,
                                                   trans_durations, fps,
                                                   master_audio=True)
        _run_stitch(inputs, fchain, vlabel, alabel, out, ffmpeg, crf, preset)
    else:
        step = inputs[0]
        intermediates: list[str] = []
        try:
            for i in range(1, len(inputs)):
                sd = _duration(step, _probe_bin(ffmpeg))
                step_out = f"{out}.mid{i - 1}.mp4"
                td = trans_durations[i] if i < len(trans_durations) else DEFAULT_TRANSITION_DURATION
                name = transitions[i] if i < len(transitions) else DEFAULT_TRANSITION
                fchain, vlabel, alabel, _ = montage_filter(
                    [sd, durations[i]], [None, name], [0.0, td], fps,
                    master_audio=True)
                _run_stitch([step, inputs[i]], fchain, vlabel, alabel,
                            step_out, ffmpeg, crf, preset)
                intermediates.append(step_out)
                if i > 1:
                    _unlink(intermediates[-2])
                step = step_out
            os.replace(step, out)
        finally:
            for f in intermediates:
                _unlink(f)

    size = Path(out).stat().st_size
    if size == 0:
        raise MediaError("Montage render produced a zero-byte file.")
    return {"input_durations": durations, "size": size,
            "final_duration": round(total, 2),
            "elapsed": round(time.time() - t0, 2)}


def _unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def _probe_bin(ffmpeg: str) -> str:
    return "ffprobe" if ffmpeg == "ffmpeg" else str(Path(ffmpeg).with_name("ffprobe"))