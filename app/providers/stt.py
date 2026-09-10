"""STT provider abstraction. Word-level timestamps are mandatory output."""
from abc import ABC, abstractmethod


class STTProvider(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def transcribe(self, wav_path: str, model: str = "", language: str | None = None) -> dict:
        """Return {engine, language, duration, words:[{w,start,end}], segments?}."""


class FasterWhisperProvider(STTProvider):
    name = "faster-whisper"

    def __init__(self, model: str = "small", device: str = "cpu", compute_type: str = "int8"):
        self.model, self.device, self.compute_type = model, device, compute_type

    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe(self, wav_path: str, model: str = "", language: str | None = None) -> dict:
        from faster_whisper import WhisperModel
        m = WhisperModel(model or self.model, device=self.device, compute_type=self.compute_type)
        segs, info = m.transcribe(wav_path, word_timestamps=True, language=language)
        words, segments = [], []
        for s in segs:
            segments.append({"text": s.text.strip(), "start": round(s.start, 2), "end": round(s.end, 2)})
            for w in (s.words or []):
                if w.word.strip():
                    words.append({"w": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)})
        return {"engine": f"faster-whisper/{model or self.model}",
                "language": getattr(info, "language", language),
                "duration": round(words[-1]["end"], 2) if words else 0.0,
                "words": words, "segments": segments}
