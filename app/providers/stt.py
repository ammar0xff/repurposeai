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

    _cache = None

    def available(self) -> bool:
        # Subprocess probe: native wheels (PyAV/ctranslate2) can SIGILL on old
        # CPUs, which cannot be caught in-process. Cache the verdict.
        if FasterWhisperProvider._cache is not None:
            return FasterWhisperProvider._cache
        try:
            import subprocess
            import sys
            r = subprocess.run([sys.executable, '-c', 'import faster_whisper'],
                               capture_output=True, timeout=60)
            FasterWhisperProvider._cache = r.returncode == 0
        except Exception:
            FasterWhisperProvider._cache = False
        return FasterWhisperProvider._cache

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
