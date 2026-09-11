"""System: health, readiness, providers, settings, metrics. Real checks."""
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import func

from ..config.settings import get_settings
from ..models.db import get_engine
from ..models.entities import ProcessingJob
from ..workers.runner import _is_stale, _utc_naive
from .deps import current_user, db_session, storage_dep

router = APIRouter(prefix="/api/system", tags=["system"])


class SettingsUpdate(BaseModel):
    stt_provider: str | None = None

    @field_validator("stt_provider")
    @classmethod
    def _stt(cls, v: str | None) -> str | None:
        if v is not None and v not in ("auto", "local", "github"):
            raise ValueError("stt_provider must be auto|local|github")
        return v


def _stt_override(db) -> str:
    from ..models.entities import SystemSetting
    row = db.query(SystemSetting).filter_by(key="stt_provider").first()
    return row.value if row and row.value in ("auto", "local", "github") else ""


def _settings_payload(db) -> dict:
    s = get_settings()
    ov = _stt_override(db)
    return {
        "stt_provider": ov or s.stt_provider,
        "stt_override": ov,
        "whisper": {"model": s.whisper_model, "device": s.whisper_device,
                    "compute_type": s.whisper_compute_type},
        "github": {"token_set": bool(s.github_token),
                   "owner": s.github_owner, "repo": s.github_repo},
    }


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
    from ..providers.remote_transcribe import RemoteGitHubProvider
    from ..providers.stt import FasterWhisperProvider
    s = get_settings()
    llm = get_llm_provider(s.llm_provider)
    local = FasterWhisperProvider(s.whisper_model)
    remote = RemoteGitHubProvider(s.github_token, s.github_owner, s.github_repo)
    l_ok = local.available()
    r_ok = remote.available()
    return {"llm": {"kind": s.llm_provider, "model": s.llm_model,
                    "available": llm.available() if s.llm_provider != "heuristic" else True,
                    "note": "heuristic fallback" if s.llm_provider == "heuristic" else ""},
            "stt": {"kind": "faster-whisper", "model": s.whisper_model,
                    "available": l_ok,
                    "engines": {"auto": l_ok or r_ok, "local": l_ok, "github": r_ok},
                    "local_mode": ("unavailable here: faster-whisper libs crash on this CPU"
                                   if not l_ok else "ready"),
                    "github_mode": ("ready: GitHub Actions runner via private gist"
                                    if r_ok else
                                    "not configured: set GITHUB_TOKEN / GITHUB_OWNER / GITHUB_REPO")}}


@router.get("/settings")
def get_settings_api(db=Depends(db_session)):
    return _settings_payload(db)


@router.put("/settings")
def put_settings_api(body: SettingsUpdate, db=Depends(db_session),
                     _u=Depends(current_user)):
    from ..models.entities import SystemSetting
    if body.stt_provider is not None:
        row = db.query(SystemSetting).filter_by(key="stt_provider").first()
        if row is None:
            db.add(SystemSetting(key="stt_provider", value=body.stt_provider))
        else:
            row.value = body.stt_provider
        db.commit()
    return _settings_payload(db)


@router.get("/metrics")
def metrics(db=Depends(db_session), _u=Depends(current_user)):
    """Operator metrics: queue depth, liveness, recent failures. Auth-protected."""
    import shutil

    s = get_settings()
    counts = dict(db.query(ProcessingJob.status, func.count()).group_by(
        ProcessingJob.status).all())
    running = db.query(ProcessingJob).filter_by(status="running").all()
    now = _utc_naive()
    timeout = float(s.worker_stale_timeout or 900)
    stale = [j.id for j in running if _is_stale(now, j.last_heartbeat,
                                                j.updated_at, j.created_at, timeout)]
    recent_failed = db.query(ProcessingJob).filter_by(status="failed").order_by(
        ProcessingJob.updated_at.desc()).limit(10).all()
    db_size = 0
    if s.database_url.startswith("sqlite:"):
        rel = urlparse(s.database_url).path
        try:
            db_size = os.path.getsize(rel or "./data/repurposeai.db")
        except OSError:
            db_size = -1
    return {
        "now": now.isoformat(timespec="seconds"),
        "stale_timeout_s": timeout,
        "jobs": counts,
        "running": [{"id": j.id, "stage": j.current_stage, "progress": j.progress,
                     "heartbeat_age_s": int(
                         (now - (j.last_heartbeat or j.updated_at or j.created_at)).total_seconds())}
                    for j in running],
        "stale_running": stale,
        "recent_failed": [{"id": j.id, "stage": j.current_stage,
                           "error": (j.error or "")[:120],
                           "updated_at": str(j.updated_at)} for j in recent_failed],
        "disk_free_gb": round(shutil.disk_usage(s.storage_path).free / 1e9, 1),
        "db_size_bytes": db_size,
    }
