"""Media inspection via FFprobe. Results cached by the caller (DB/job record)."""
import json
import os
import subprocess

from ..core.errors import MediaError

ALLOWED_VIDEO = {"h264", "hevc", "vp9", "av1", "mpeg4"}
MAX_GB = float(os.environ.get("MAX_UPLOAD_GB", "4"))


def ffprobe(path: str, ffprobe_bin: str = "ffprobe") -> dict:
    try:
        p = subprocess.run(
            [ffprobe_bin, "-v", "error", "-show_entries",
             "format=duration,size:stream=index,codec_name,codec_type,width,height,"
             "avg_frame_rate,sample_rate,channels",
             "-of", "json", path],
            capture_output=True, text=True, timeout=120)
    except FileNotFoundError as e:
        raise MediaError("FFprobe not found. Install FFmpeg.",
                         details=str(e)) from e
    if p.returncode != 0:
        raise MediaError("Unreadable media file.",
                         details=(p.stderr or "")[:300])
    try:
        return json.loads(p.stdout or "{}")
    except json.JSONDecodeError as e:
        raise MediaError("FFprobe returned invalid data.", details=str(e)) from e


def analyze(path: str, ffprobe_bin: str = "ffprobe") -> dict:
    """-> {duration,width,height,fps,video_codec,audio_codec,sample_rate,channels,size}."""
    info = ffprobe(path, ffprobe_bin)
    streams = info.get("streams", [])
    if not streams:
        raise MediaError("No decodable streams found.")
    vid = next((s for s in streams if s.get("codec_type") == "video"), {})
    aud = next((s for s in streams if s.get("codec_type") == "audio"), {})
    if not vid:
        raise MediaError("No video stream found.")
    num, _, den = (vid.get("avg_frame_rate", "0/1") + "/1").split("/")[:3]
    try:
        fps = round(float(num) / float(den or 1), 3)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    size = int(info.get("format", {}).get("size", 0) or 0)
    if size > MAX_GB * 1024**3:
        raise MediaError(f"File exceeds {MAX_GB}GB limit.")
    return {
        "duration": float(info.get("format", {}).get("duration", 0) or 0),
        "width": int(vid.get("width", 0) or 0),
        "height": int(vid.get("height", 0) or 0),
        "fps": fps,
        "video_codec": vid.get("codec_name", ""),
        "audio_codec": aud.get("codec_name", "") if aud else "",
        "sample_rate": int(aud.get("sample_rate", 0) or 0) if aud else 0,
        "channels": int(aud.get("channels", 0) or 0) if aud else 0,
        "size": size,
        "has_audio": bool(aud),
    }


def guessaudio(path: str, ffprobe_bin: str = "ffprobe") -> bool:
    try:
        return bool(analyze(path, ffprobe_bin)["has_audio"])
    except MediaError:
        return False
