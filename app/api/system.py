"""System: health, readiness, providers. Real checks, no invented metrics."""
from fastapi import APIRouter, Depends

from ..config.settings import get_settings
from ..models.db import get_engine
from .deps import storage_dep

router = APIRouter(prefix="/api/system", tags=["system"])


def _check(name: str, fn):
    try:
        fn()
        return {"status": "ok"}
    except Exception as e:  # noqa: BLE001 - health probes must report, never raise
        return {"status": "fail", "error": f"{type(e).__name__}: {e}"[:200]}


@router.get("/health")
def health():
    return {"status": "ok", "service": "repurposeai"}


@router.get("/readiness")
def readiness(st=Depends(storage_dep)):
    import shutil
    import subprocess
    s = get_settings()

    def db():
        e = get_engine()
        with e.connect() as c:
            c.exec_driver_sql("SELECT 1")

    def ffmpeg():
        subprocess.run([s.ffmpeg_path, "-version"], capture_output=True,
                       check=True, timeout=15)

    def ffprobe():
        subprocess.run([s.ffprobe_path, "-version"], capture_output=True,
                       check=True, timeout=15)

    def stt():
        from ..providers.stt import FasterWhisperProvider
        if not FasterWhisperProvider(s.whisper_model).available():
            raise RuntimeError("faster-whisper unavailable here (missing or native libs crash); use runner hardware")

    def llm():
        from ..providers.llm import get_llm_provider
        p = get_llm_provider(s.llm_provider)
        if s.llm_provider != "heuristic" and not p.available():
            raise RuntimeError(f"{s.llm_provider} not configured")

    checks = {
        "database": _check("database", db),
        "storage": _check("storage", lambda: st.list("")),
        "ffmpeg": _check("ffmpeg", ffmpeg),
        "ffprobe": _check("ffprobe", ffprobe),
        "stt": _check("stt", stt),
        "llm": _check("llm", llm),
        "disk": {"status": "ok",
                 "free_gb": round(shutil.disk_usage(s.storage_path).free / 1e9, 1)},
    }
    ready = all(v.get("status") == "ok" for v in checks.values())
    return {"ready": ready, "checks": checks}


@router.get("/providers")
def providers():
    from ..providers.llm import get_llm_provider
    from ..providers.stt import FasterWhisperProvider
    s = get_settings()
    llm = get_llm_provider(s.llm_provider)
    return {"llm": {"kind": s.llm_provider, "model": s.llm_model,
                    "available": llm.available() if s.llm_provider != "heuristic" else True,
                    "note": "heuristic fallback" if s.llm_provider == "heuristic" else ""},
            "stt": {"kind": "faster-whisper", "model": s.whisper_model,
                    "available": FasterWhisperProvider(s.whisper_model).available()}}
