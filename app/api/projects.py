"""Projects: CRUD + ingest/process/cancel + children + export."""
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from ..core.ids import new_id
from ..core.logging import log
from ..models.entities import (
    Candidate,
    Clip,
    GeneratedMetadata,
    MediaAsset,
    ProcessingJob,
    Project,
    Transcript,
)
from ..workers import get_worker
from .deps import current_user, db_session, settings_dep, storage_dep
from .schemas import JobCreate, ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _out(p: Project) -> dict:
    return {"id": p.id, "title": p.title, "description": p.description or "",
            "language": p.language, "duration": p.duration, "status": p.status,
            "config": p.config or {}, "created_at": str(p.created_at),
            "updated_at": str(p.updated_at)}


@router.post("", response_model=ProjectOut, status_code=201)
def create(body: ProjectCreate, db=Depends(db_session), _u=Depends(current_user)):
    p = Project(id=new_id(), title=body.title[:255], description=body.description,
                config=dict(body.config), user_id=_u)
    db.add(p)
    db.commit()
    return _out(p)


@router.get("")
def listing(limit: int = 50, offset: int = 0, db=Depends(db_session),
            _u=Depends(current_user)):
    limit = max(1, min(limit, 200))
    q = db.query(Project).filter_by(user_id=_u).order_by(Project.created_at.desc())
    total = q.count()
    return {"total": total, "limit": limit, "offset": offset,
            "items": [_out(p) for p in q.offset(offset).limit(limit).all()]}


@router.get("/{pid}", response_model=ProjectOut)
def get(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    p = db.query(Project).filter_by(id=pid, user_id=_u).first()
    if not p:
        raise HTTPException(404, "project not found")
    return _out(p)


@router.delete("/{pid}")
def delete(pid: str, db=Depends(db_session), st=Depends(storage_dep),
           _u=Depends(current_user)):
    p = db.query(Project).filter_by(id=pid, user_id=_u).first()
    if not p:
        raise HTTPException(404, "project not found")
    for a in db.query(MediaAsset).filter_by(project_id=pid).all():
        try:
            st.delete(a.storage_key)
        except OSError as e:  # storage best-effort; DB is source of truth
            log.warning("delete skips missing artifact %s: %s", a.storage_key, e)
    db.delete(p)
    db.commit()
    return {"deleted": pid}


@router.post("/{pid}/upload")
def upload(pid: str, file: UploadFile, db=Depends(db_session),
           st=Depends(storage_dep), s=Depends(settings_dep), _u=Depends(current_user)):
    from ..storage.base import project_key
    p = db.query(Project).filter_by(id=pid, user_id=_u).first()
    if not p:
        raise HTTPException(404, "project not found")
    name = "".join(c for c in (file.filename or "upload") if c.isalnum() or c in "._-")[-100:]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ("mp4", "mkv", "mov", "webm", "mp3", "wav", "m4a", "avi"):
        raise HTTPException(422, "unsupported media type")
    data = file.file.read()
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "file exceeds MAX_UPLOAD_MB")
    key = project_key(pid, "uploads", f"{new_id()}-{name}")
    st.put(key, data)
    return {"storage_key": key, "size": len(data)}


@router.post("/{pid}/process", status_code=201)
def process(pid: str, body: JobCreate, db=Depends(db_session),
            _u=Depends(current_user)):
    p = db.query(Project).filter_by(id=pid, user_id=_u).first()
    if not p:
        raise HTTPException(404, "project not found")
    params = dict(body.params)
    if body.source:
        params["source"] = body.source
    if body.filename:
        params["filename"] = body.filename
    if body.upload_key:
        params["source"] = body.upload_key
        params["preuploaded"] = True
    if not params.get("source"):
        raise HTTPException(422, "source, filename+upload, or params.source required")
    params.setdefault("clip_count", (p.config or {}).get("clip_count", 5))
    job = ProcessingJob(id=new_id(), project_id=pid, status="queued", params=params)
    db.add(job)
    db.commit()
    try:
        get_worker().submit(job.id)
    except (AssertionError, RuntimeError) as e:
        log.warning("worker submit deferred (%s); dispatcher will pick up", e)
    return {"job_id": job.id, "status": "queued"}


@router.post("/{pid}/cancel")
def cancel(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    jobs = db.query(ProcessingJob).filter_by(project_id=pid).all()
    if not any(j.project_id == pid for j in jobs):
        raise HTTPException(404, "project not found")
    for j in jobs:
        if j.status in ("queued", "running"):
            try:
                get_worker().cancel(j.id)
            except (AssertionError, RuntimeError):
                j.status = "cancelled"
    db.commit()
    return {"cancelled": True}


@router.get("/{pid}/candidates")
def candidates(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    if not db.query(Project).filter_by(id=pid, user_id=_u).first():
        raise HTTPException(404, "project not found")
    rows = db.query(Candidate).filter_by(project_id=pid).order_by(Candidate.score.desc()).all()
    return [{"id": r.id, "start": r.start, "end": r.end, "text": r.text,
             "hook_text": r.hook_text, "features": r.features, "eligible": r.eligible,
             "score": r.score, "job_id": r.job_id} for r in rows]


@router.get("/{pid}/clips")
def clips(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    if not db.query(Project).filter_by(id=pid, user_id=_u).first():
        raise HTTPException(404, "project not found")
    rows = db.query(Clip).filter_by(project_id=pid).order_by(Clip.created_at.desc()).all()
    from ..models.entities import CandidateScore
    out = []
    for c in rows:
        md = db.query(GeneratedMetadata).filter_by(clip_id=c.id).first()
        sc = db.query(CandidateScore).filter_by(candidate_id=c.candidate_id).order_by(CandidateScore.overall.desc()).first() if c.candidate_id else None
        dec = None
        from ..models.entities import ReviewDecision
        d = db.query(ReviewDecision).filter_by(clip_id=c.id).order_by(
            ReviewDecision.created_at.desc()).first()
        if d:
            dec = d.decision
        out.append({"id": c.id, "start": c.start, "end": c.end, "status": c.status,
                    "render_profile": c.render_profile, "validation": c.validation,
                    "axes": sc.axes if sc else {}, "score": round((sc.overall * 10) if sc else 0, 1),
                    "metadata": {"titles": md.titles if md else [],
                                 "caption": md.caption if md else "",
                                 "hashtags": md.hashtags if md else [],
                                 "chosen_title": md.chosen_title if md else 0},
                    "decision": dec})
    return out


@router.get("/{pid}/transcript")
def transcript(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    if not db.query(Project).filter_by(id=pid, user_id=_u).first():
        raise HTTPException(404, "project not found")
    t = db.query(Transcript).filter_by(project_id=pid).first()
    if not t:
        raise HTTPException(404, "no transcript yet")
    return {"engine": t.engine, "language": t.language, "duration": t.duration,
            "words": t.words, "segments": t.segments}


@router.post("/import", status_code=201)
def import_project(file: UploadFile, db=Depends(db_session),
                   st=Depends(storage_dep), _u=Depends(current_user)):
    """Restore a portable archive (see exporter.project_archive)."""
    import io
    import zipfile

    from ..models.entities import Candidate as _C
    from ..models.entities import MediaAsset as _A
    from ..storage.base import project_key
    raw = file.file.read()
    if len(raw) > 2 * 1024**3:
        raise HTTPException(413, "archive too large")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        meta = json.loads(z.read("project.json"))
    except (zipfile.BadZipFile, KeyError, ValueError, json.JSONDecodeError):
        raise HTTPException(422, "invalid project archive")
    m = meta.get("project", {})
    p = Project(id=new_id(), title=str(m.get("title", "Imported"))[:255],
                description=str(m.get("description", "")),
                config=dict(m.get("config", {})), user_id=_u)
    db.add(p)
    for c in meta.get("candidates", []):
        db.add(_C(id=new_id(), project_id=p.id, job_id="imported",
                  start=float(c.get("start", 0)), end=float(c.get("end", 0)),
                  text=str(c.get("text", ""))[:2000],
                  score=float(c.get("score", 0))))
    for name in z.namelist():
        if name.startswith("media/") and not name.endswith("/"):
            key = project_key(p.id, "source", name.rsplit("/", 1)[-1] or "media")
            st.put(key, z.read(name))
            db.add(_A(id=new_id(), project_id=p.id, kind="source",
                      storage_key=key, size=len(z.read(name))))
    db.commit()
    for d in meta.get("decisions", []):
        pass  # decisions reference old clip ids; intentionally not remapped
    return {"project_id": p.id, "title": p.title}


@router.post("/{pid}/export", response_model=dict, status_code=201)
def export(pid: str, db=Depends(db_session), st=Depends(storage_dep),
           _u=Depends(current_user)):
    p = db.query(Project).filter_by(id=pid, user_id=_u).first()
    if not p:
        raise HTTPException(404, "project not found")
    from ..services.exporter import build_export
    exp = build_export(db, st, p)
    return {"id": exp.id, "storage_key": exp.storage_key, "manifest": exp.manifest}
