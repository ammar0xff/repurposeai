"""Clips: approve/reject/edit/rerender/download + metadata variants."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..core.ids import new_id
from ..models.entities import Clip, GeneratedMetadata, Project, ReviewDecision
from .deps import current_user, db_session, pipeline_dep, storage_dep
from .schemas import RerenderIn, ReviewIn

router = APIRouter(prefix="/api/clips", tags=["clips"])


def _owned(db, cid: str, user: str) -> Clip:
    c = db.query(Clip).filter_by(id=cid).first()
    if not c:
        raise HTTPException(404, "clip not found")
    p = db.query(Project).filter_by(id=c.project_id, user_id=user).first()
    if not p:
        raise HTTPException(403, "forbidden")
    return c


@router.post("/{cid}/approve")
def approve(cid: str, body: ReviewIn, db=Depends(db_session), _u=Depends(current_user)):
    c = _owned(db, cid, _u)
    db.add(ReviewDecision(id=new_id(), clip_id=cid, user_id=_u,
                          decision="approved", note=body.note))
    c.status = "approved"
    db.commit()
    return {"id": cid, "decision": "approved"}


@router.post("/{cid}/reject")
def reject(cid: str, body: ReviewIn, db=Depends(db_session), _u=Depends(current_user)):
    c = _owned(db, cid, _u)
    db.add(ReviewDecision(id=new_id(), clip_id=cid, user_id=_u,
                          decision="rejected", note=body.note))
    c.status = "rejected"
    db.commit()
    return {"id": cid, "decision": "rejected"}


@router.post("/{cid}/rerender")
def rerender(cid: str, body: RerenderIn, db=Depends(db_session),
             pipe=Depends(pipeline_dep), _u=Depends(current_user)):
    """Edit timestamps/style/meta then re-render only this clip (no re-STT)."""
    from ..rendering.renderer import Renderer
    from ..validation.checks import validate_clip
    c = _owned(db, cid, _u)
    cfg = (db.query(Project).filter_by(id=c.project_id).first().config) or {}
    start = body.start if body.start is not None else c.start
    end = body.end if body.end is not None else c.end
    if not (end > start):
        raise HTTPException(422, "end must be after start")
    from ..models.entities import Transcript
    tr = db.query(Transcript).filter_by(project_id=c.project_id).first()
    words = tr.words if tr else []
    import os
    from ..storage.base import project_key
    tmp = f"/tmp/rpa-re-{c.id}.mp4"
    rdr = Renderer()
    meta = rdr.render(pipe._src_path(db.query(Project).filter_by(id=c.project_id).first()),
                      start, end, words, tmp,
                      cfg.get("render_profile", "shorts_1080x1920"),
                      body.reframe or cfg.get("reframe", "center"),
                      body.caption_style or cfg.get("caption_style", "bold"),
                      cfg.get("credit", ""))
    key = project_key(c.project_id, "clips", f"{c.id}-v{int(__import__('time').time())}.mp4")
    st = pipe.storage.put_file(key, tmp)
    os.unlink(tmp)
    c.start, c.end, c.storage_key = start, end, st
    c.status = "rendered"
    c.validation = validate_clip(pipe.storage.get_path(st), {
        "width": 1080, "height": 1920, "min_duration": 5, "max_duration": 600,
        "need_audio": True, "need_captions": True})
    md = db.query(GeneratedMetadata).filter_by(clip_id=cid).first()
    if md:
        if body.title:
            md.titles = [body.title] + [t for t in md.titles if t != body.title]
            md.chosen_title = 0
        if body.description is not None:
            md.description = body.description
        if body.hashtags is not None:
            md.hashtags = body.hashtags
    db.commit()
    return {"id": cid, "start": start, "end": end, "validation": c.validation}


@router.get("/{cid}/download")
def download(cid: str, db=Depends(db_session), st=Depends(storage_dep),
             _u=Depends(current_user)):
    c = _owned(db, cid, _u)
    try:
        data = st.get(c.storage_key)
    except Exception:
        raise HTTPException(404, "artifact missing from storage")
    return Response(data, media_type="video/mp4",
                    headers={"Content-Disposition": f"attachment; filename={cid}.mp4"})
