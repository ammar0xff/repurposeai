"""Reframing strategies: center | face | speaker | smart | manual.
Fallback chain: face -> speaker -> center. Never mandatory."""
from abc import ABC, abstractmethod


class ReframingStrategy(ABC):
    @abstractmethod
    def anchor(self, source: str, start: float, end: float,
               width: int, height: int) -> float:
        """Horizontal anchor 0..1 for the crop window."""


class CenterStrategy(ReframingStrategy):
    def anchor(self, source, start, end, width, height) -> float:
        return 0.5


class FaceStrategy(ReframingStrategy):
    def anchor(self, source, start, end, width, height) -> float:
        try:
            return _face_median(source, start, end)
        except ImportError:
            return SpeakerStrategy().anchor(source, start, end, width, height)


class SpeakerStrategy(ReframingStrategy):
    def anchor(self, source, start, end, width, height) -> float:
        return 0.5  # audio-side speaker diarization is a future provider


class SmartStrategy(ReframingStrategy):
    def anchor(self, source, start, end, width, height) -> float:
        return FaceStrategy().anchor(source, start, end, width, height)


class ManualStrategy(ReframingStrategy):
    def __init__(self, anchor: float = 0.5):
        self._a = max(0.0, min(1.0, anchor))

    def anchor(self, source, start, end, width, height) -> float:
        return self._a


def _face_median(source: str, start: float, end: float) -> float:
    import subprocess
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(max(end - start, 0.5)),
           "-i", source, "-vf", "fps=1,scale=320:-1",
           "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    p = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    if p.returncode != 0 or not p.stdout:
        return 0.5
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
    except ImportError:
        # Haar fallback ships with opencv data files
        import cv2
        import numpy as np
        data, xs, soi = p.stdout, [], b"\xff\xd8"
        idx = [i for i in range(len(data)) if data.startswith(soi, i)]
        cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        for a, b in zip(idx, idx[1:] + [len(data)]):
            img = cv2.imdecode(np.frombuffer(data[a:b], np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            for x, _, w, _ in cc.detectMultiScale(gray, 1.2, 4, minSize=(30, 30)):
                xs.append((x + w / 2) / img.shape[1])
        xs.sort()
        return float(max(0.0, min(1.0, xs[len(xs) // 2]))) if xs else 0.5
    # mediapipe path
    import cv2
    import numpy as np
    det = mp.solutions.face_detection.FaceDetection(model_selection=0,
                                                   min_detection_confidence=0.5)
    data, xs, soi = p.stdout, [], b"\xff\xd8"
    idx = [i for i in range(len(data)) if data.startswith(soi, i)]
    for a, b in zip(idx, idx[1:] + [len(data)]):
        img = cv2.imdecode(np.frombuffer(data[a:b], np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        res = det.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        for d in res.detections or []:
            bb = d.location_data.relative_bounding_box
            xs.append(bb.xmin + bb.width / 2)
    xs.sort()
    return float(max(0.0, min(1.0, xs[len(xs) // 2]))) if xs else 0.5


def face_track(source: str, start: float, end: float,
               window: float = 6.0) -> list[tuple[float, float]]:
    """Per-window median face anchor, holding the last value when unseen.

    Returns [(t, anchor)] in clip-local seconds (t starts at 0) or [] when
    nothing usable is detected. Consecutive anchors are clamped so the camera
    pan never snaps between positions.
    """
    import subprocess

    duration = max(end - start, 0.5)
    buckets = max(int(duration // window) + 1, 1)
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration),
             "-i", source, "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-vf", "fps=1,scale=640:360", "-"],
            capture_output=True, timeout=180, check=False)
    except subprocess.TimeoutExpired:
        return []
    body = p.stdout
    if p.returncode != 0 or not body:
        return []
    n = len(body) // (640 * 360 * 3)
    if not n:
        return []
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    cc = cv2.CascadeClassifier(cv2.data.haarcascades
                               + "haarcascade_frontalface_default.xml")
    hits: list[list[float]] = [[] for _ in range(buckets)]
    for i in range(n):
        img = np.frombuffer(body[i * 640 * 360 * 3:(i + 1) * 640 * 360 * 3],
                            np.uint8).reshape(360, 640, 3)
        for x, _, w, _ in cc.detectMultiScale(
                cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5,
                minSize=(40, 40)):
            hits[min(i, buckets - 1)].append((x + w / 2) / 640)
    track: list[tuple[float, float]] = []
    hold = 0.5
    for k, xs in enumerate(hits):
        if xs:
            hold = float(np.median(xs))
            if hold < 0.05 or hold > 0.95:
                hold = 0.5
        mid = min(start + window * k + window / 2, end)
        track.append((max(mid - start, 0.0), hold))
    out: list[tuple[float, float]] = []
    prev = None
    for mid, a in track:
        if prev is not None:
            a = min(prev + 0.10, max(prev - 0.10, a))
        a = max(0.0, min(1.0, a))
        out.append((mid, a))
        prev = a
    return out


def _track_expr(track: list[tuple[float, float]]) -> str:
    """Piecewise-linear crop-x timeline; half-open windows + hold tail."""
    terms = []
    for i in range(len(track) - 1):
        t0, a0 = track[i]
        t1, a1 = track[i + 1]
        m = (a1 - a0) / (t1 - t0) if t1 > t0 else 0.0
        terms.append(f"({a0:.3f}{m:+.3f}*(t-{t0:.3f}))"
                     f"*gte(t,{t0:.3f})*lt(t,{t1:.3f})")
    t_last, a_last = track[-1]
    terms.append(f"{a_last:.3f}*gte(t,{t_last:.3f})")
    return "+".join(terms)


def get_strategy(name: str, **kw) -> ReframingStrategy:
    if name == "face":
        return FaceStrategy()
    if name == "speaker":
        return SpeakerStrategy()
    if name == "smart":
        return SmartStrategy()
    if name == "manual":
        return ManualStrategy(**kw)
    return CenterStrategy()


def crop_filter(src_w: int, src_h: int, dst_w: int, dst_h: int, anchor: float,
                duration: float = 0.0,
                track: list[tuple[float, float]] | None = None) -> str:
    """Animated Ken Burns pan: slow drift onto the anchor column.

    `track` (optional, clip-local (t, anchor) pairs) makes the window follow
    the subject with a piecewise-linear pan; a gentle additive drift is layered
    on top so a fixed subject never reads as a frozen still. Without a track
    the window eases a wider drift onto `anchor`. The frame is upscaled once
    (18%) and the fixed-aspect window pans over time, so the clip is never a
    frozen single spot.
    `duration <= 0` keeps the historical static crop (tests / manual renders).
    Crop w/h stay constant - ffmpeg rejects time-varying crop sizes mid-stream.
    """
    anchor = max(0.0, min(1.0, anchor))
    war = dst_w / dst_h
    if duration and duration > 0:
        if track and len(track) >= 2:
            x = _track_expr(track)
            x = f"{x}+0.10*((t/{duration:.4f})-0.5)"
        else:
            a_from = max(0.0, min(1.0, anchor - 0.22))
            x = (f"({a_from:.3f}+{anchor - a_from:.3f}*"
                 f"(t/{duration:.4f}))")
        expr = (f"scale=trunc(iw*1.18/2)*2:trunc(ih*1.18/2)*2,"
                f"crop={war:.4f}*ih:ih:"
                f"x='(iw-ow)*max(0,min(1,{x}))':y=(ih-oh)/2")
    else:
        expr = f"crop={war:.4f}*ih:ih:x='(in_w-out_w)*{anchor:.3f}':y=0"
    return f"{expr},scale={dst_w}:{dst_h}:flags=lanczos"
