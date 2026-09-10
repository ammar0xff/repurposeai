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
    p = subprocess.run(cmd, capture_output=True, timeout=120)
    if p.returncode != 0 or not p.stdout:
        return 0.5
    try:
        import mediapipe as mp
        import numpy as np
        import cv2
    except ImportError:
        # Haar fallback ships with opencv data files
        import numpy as np
        import cv2
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
    import numpy as np
    import cv2
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


def get_strategy(name: str, **kw) -> ReframingStrategy:
    return {"center": CenterStrategy, "face": FaceStrategy, "speaker": SpeakerStrategy,
            "smart": SmartStrategy, "manual": ManualStrategy}.get(name, CenterStrategy)(**kw)


def crop_filter(src_w: int, src_h: int, dst_w: int, dst_h: int, anchor: float) -> str:
    """ffmpeg crop expression preserving aspect via center-biased window."""
    anchor = max(0.0, min(1.0, anchor))
    return (f"crop={dst_w}/{dst_h}*ih:ih:x='(in_w-out_w)*{anchor:.3f}':y=0,"
            f"scale={dst_w}:{dst_h}")
