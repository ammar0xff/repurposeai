"""Renderer: trim -> reframe -> captions -> encode. Arg arrays only, tracked."""
import subprocess
import time
from pathlib import Path

from ..captions.engine import to_ass
from ..core.errors import MediaError
from .reframe import crop_filter, get_strategy

PROFILES = {
    "shorts_1080x1920": {"w": 1080, "h": 1920},
    "reels_1080x1920": {"w": 1080, "h": 1920},
    "tiktok_1080x1920": {"w": 1080, "h": 1920},
    "square_1080x1080": {"w": 1080, "h": 1080},
    "landscape_1920x1080": {"w": 1920, "h": 1080},
}


class Renderer:
    def __init__(self, ffmpeg: str = "ffmpeg", crf: int = 20, preset: str = "veryfast"):
        self.ffmpeg, self.crf, self.preset = ffmpeg, crf, preset

    def render(self, source: str, start: float, end: float, words: list, out: str,
               profile: str = "shorts_1080x1920", reframe: str = "center",
               caption_style: str = "bold", credit: str = "",
               loudnorm: bool = False) -> dict:
        t0 = time.time()
        spec = PROFILES.get(profile, PROFILES["shorts_1080x1920"])
        anchor = get_strategy(reframe).anchor(source, start, end, 0, 0)
        ass = Path(out).with_suffix(".ass")
        ass.write_text(to_ass(words, start, end, caption_style),
                       encoding="utf-8")
        vf = crop_filter(0, 0, spec["w"], spec["h"], anchor)
        vf += f",subtitles='{ass}':force_style='FontSize=64'"
        if credit:
            safe = credit.replace(":", "\\:").replace("'", "")
            vf += (f",drawtext=text='{safe}':fontcolor=white@0.9:fontsize=30:"
                   f"x=(w-text_w)/2:y=h-140:box=1:boxcolor=black@0.5:boxborderw=12")
        cmd = [self.ffmpeg, "-y", "-v", "error",
               "-ss", str(start), "-to", str(end), "-i", source,
               "-vf", vf, "-c:v", "libx264", "-preset", self.preset,
               "-crf", str(self.crf), "-c:a", "aac", "-b:a", "128k"]
        if loudnorm:
            cmd += ["-af", "loudnorm"]
        cmd += ["-movflags", "+faststart", "-shortest", out]
        try:
            subprocess.run(cmd, check=True, timeout=1800)
        except FileNotFoundError as e:
            raise MediaError("FFmpeg not found.", details=str(e)) from e
        except subprocess.TimeoutExpired as e:
            raise MediaError("Rendering timed out.", details=str(e)) from e
        except subprocess.CalledProcessError as e:
            raise MediaError("FFmpeg could not encode the clip.",
                             details=f"rc={e.returncode}. Check source codec and disk space.") from e
        size = Path(out).stat().st_size
        if size == 0:
            raise MediaError("Render produced a zero-byte file.")
        return {"command": " ".join(cmd[:6]) + " ...",
                "duration": round(time.time() - t0, 1),
                "output_size": size, "codec": "h264",
                "resolution": f"{spec['w']}x{spec['h']}",
                "render_time": round(time.time() - t0, 1),
                "reframe_anchor": anchor, "errors": ""}
