"""Sequences: montage timelines per project (+ autofill + render + download)."""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..core.ids import new_id
from ..models.entities import Candidate, Clip, Project, Sequence
from ..rendering.sequence import DEFAULT_TRANSITION, DEFAULT_TRANSITION_DURATION, render_sequence
from .deps import current_user, db_session, pipeline_dep, storage_dep
from .schemas import SequenceIn, SequenceOut, SequenceRenderIn

router = APIRouter(prefix="/api/projects/{pid}/sequence", tags=["sequences"])


def _project(db, pid: str, user: str) -> Project:
    p = db.query(Project).filter_by(id=pid, user_id=user).first()
    if not p:
        raise HTTPException(404, "project not found")
    return p


def _owned(db, pid: str, user: str) -> Sequence:
    seq = db.query(Sequence).filter_by(project_id=pid).order_by(
        Sequence.created_at.desc(), Sequence.id.desc()).first()
    if not seq:
        raise HTTPException(404, "no sequence yet for this project")
    return seq


def _clip(db, cid: str, pid: str) -> Clip:
    c = db.query(Clip).filter_by(id=cid, project_id=pid).first()
    if not c:
        raise HTTPException(404, "clip not found in this project")
    return c


def _out(seq: Sequence, db) -> SequenceOut:
    """Enrich stored item dicts with the referenced clip's own defaults."""
    enriched = []
    for it in (seq.items or []):
        item = dict(it)
        c = db.query(Clip).filter_by(id=item.get("clip_id", "")).first()
        if c:
            item["clip"] = {"start": c.start, "end": c.end, "status": c.status,
                            "render_profile": c.render_profile}
        enriched.append(item)
    return SequenceOut(id=seq.id, name=seq.name, items=enriched,
                       rendered_key=seq.rendered_key,
                       rendered_validation=seq.rendered_validation or {})


@router.get("", response_model=SequenceOut)
def get_sequence(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    _project(db, pid, _u)
    seq = _owned(db, pid, _u)
    return _out(seq, db)


@router.put("", response_model=SequenceOut)
def put_sequence(pid: str, body: SequenceIn, db=Depends(db_session),
                 _u=Depends(current_user)):
    _project(db, pid, _u)
    seq = db.query(Sequence).filter_by(project_id=pid).order_by(
        Sequence.created_at.desc(), Sequence.id.desc()).first()
    if not seq:
        seq = Sequence(id=new_id(), project_id=pid, user_id=_u)
        db.add(seq)
    if body.name is not None:
        seq.name = body.name
    if body.items is not None:
        seq.items = [it.model_dump() for it in body.items]
    db.commit()
    return _out(seq, db)


@router.post("/autofill", response_model=SequenceOut)
def autofill(pid: str, db=Depends(db_session), _u=Depends(current_user)):
    """Compose the timeline from the pipeline's best-ranked rendered clips."""
    p = _project(db, pid, _u)
    cfg = p.config or {}
    rows = (db.query(Clip)
            .join(Candidate, Clip.candidate_id == Candidate.id)
            .filter(Clip.project_id == pid, Clip.status == "rendered")
            .order_by(Candidate.score.desc())
            .all())
    if not rows:
        raise HTTPException(422, "no rendered clips to compose from")
    limit = int(cfg.get("clip_count", 5))
    items = [{"clip_id": c.id, "transition": DEFAULT_TRANSITION,
              "transition_duration": DEFAULT_TRANSITION_DURATION}
             for c in rows[:limit]]
    seq = _owned(db, pid, _u)
    seq.items = items
    seq.name = "Auto-fill montage" if not seq.items else seq.name
    db.commit()
    return _out(seq, db)


@router.post("/render")
def render(pid: str, body: SequenceRenderIn, db=Depends(db_session),
           pipe=Depends(pipeline_dep), _u=Depends(current_user)):
    """Render the montage: per-item clips (reusing stored clips where possible)
    stitched with xfade transitions, then validate + persist."""
    from ..models.entities import Transcript
    from ..rendering.renderer import Renderer
    from ..storage.base import project_key
    from ..validation.checks import validate_clip

    p = _project(db, pid, _u)
    seq = _owned(db, pid, _u)
    items = seq.items or []
    if not items:
        raise HTTPException(422, "empty timeline")
    cfg = p.config or {}
    tr = db.query(Transcript).filter_by(project_id=pid).first()
    words = tr.words if tr else []
    rdr = Renderer()
    src = pipe._src_path(p)
    profile = cfg.get("render_profile", "shorts_1080x1920")
    default_reframe = cfg.get("reframe", "smart")
    default_style = cfg.get("caption_style", "bold")
    default_credit = cfg.get("credit", "")
    body_trans = body.transition
    body_td = body.transition_duration

    inputs: list[str] = []
    transitions: list[str | None] = []
    trans_durations: list[float] = []
    tmp_files: list[str] = []
    try:
        for i, item in enumerate(items):
            cid = item.get("clip_id") or ""
            c = _clip(db, cid, pid)
            if c.status != "rendered":
                raise HTTPException(422, f"clip {cid} is not rendered")
            reframe = item.get("reframe") or default_reframe
            style = item.get("caption_style") or default_style
            credit = item.get("credit") if item.get("credit") is not None else default_credit
            start = item.get("start") if item.get("start") is not None else c.start
            end = item.get("end") if item.get("end") is not None else c.end
            if not (end > start):
                raise HTTPException(422, f"clip {cid} has invalid trim")
            has_override = any(item.get(k) is not None for k in
                               ("start", "end", "reframe", "caption_style", "credit"))
            if not has_override:
                inputs.append(pipe.storage.get_path(c.storage_key))
            else:
                tmp = f"/tmp/rpa-montage-{seq.id[:8]}-{i}.mp4"
                rdr.render(src, start, end, words, tmp, profile,
                           reframe, style, credit, loudnorm=True)
                tmp_files.append(tmp)
                inputs.append(tmp)
            transitions.append((item.get("transition") or body_trans or DEFAULT_TRANSITION)
                               if i > 0 else None)
            trans_durations.append(
                float(item.get("transition_duration") if item.get("transition_duration") is not None
                      else body_td if body_td is not None else DEFAULT_TRANSITION_DURATION))

        key = project_key(pid, "exports", f"montage-{seq.id}.mp4")
        out_tmp = f"/tmp/rpa-montage-{seq.id[:8]}.mp4"
        stats = render_sequence(inputs, transitions, trans_durations, out_tmp,
                                ffmpeg=pipe.s.ffmpeg_path)
        key_used = pipe.storage.put_file(key, out_tmp)
        seq.rendered_key = key_used
        seq.rendered_validation = validate_clip(pipe.storage.get_path(key_used), {
            "width": 1080, "height": 1920,
            "min_duration": 1, "max_duration": 3600,
            "need_audio": True, "need_captions": False})
        db.commit()
        return {"id": seq.id, "storage_key": key_used,
                "validation": seq.rendered_validation,
                "duration": stats.get("final_duration", 0.0),
                "download_url": f"/api/projects/{pid}/sequence/download"}
    finally:
        for f in tmp_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except OSError:
                pass


@router.get("/download")
def download(pid: str, db=Depends(db_session), st=Depends(storage_dep),
             _u=Depends(current_user)):
    _project(db, pid, _u)
    seq = _owned(db, pid, _u)
    if not seq.rendered_key:
        raise HTTPException(404, "montage not rendered yet")
    try:
        data = st.get(seq.rendered_key)
    except (OSError, RuntimeError, KeyError):
        raise HTTPException(404, "montage artifact missing from storage")
    return Response(data, media_type="video/mp4",
                    headers={"Content-Disposition": f"attachment; filename={seq.id}-montage.mp4"})