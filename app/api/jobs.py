"""Jobs: list, detail (stages+progress), SSE stream, cancel, retry."""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..core.logging import log
from ..models.entities import PipelineStage, ProcessingJob
from .deps import current_user, db_session

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _stages(db, job_id: str) -> list:
    return [{"name": s.name, "status": s.status, "progress": s.progress,
             "started_at": str(s.started_at or ""), "completed_at": str(s.completed_at or ""),
             "error": s.error}
            for s in db.query(PipelineStage).filter_by(job_id=job_id).all()]


@router.get("")
def listing(limit: int = 50, offset: int = 0, db=Depends(db_session),
            _u=Depends(current_user)):
    limit = max(1, min(limit, 200))
    q = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc())
    rows = q.offset(offset).limit(limit).all()
    return [{"id": j.id, "project_id": j.project_id, "status": j.status,
             "progress": j.progress, "current_stage": j.current_stage,
             "error": j.error, "created_at": str(j.created_at)} for j in rows]


@router.get("/{jid}")
def detail(jid: str, db=Depends(db_session), _u=Depends(current_user)):
    j = db.query(ProcessingJob).filter_by(id=jid).first()
    if not j:
        raise HTTPException(404, "job not found")
    return {"id": j.id, "project_id": j.project_id, "status": j.status,
            "progress": j.progress, "current_stage": j.current_stage,
            "error": j.error, "params": j.params, "stages": _stages(db, jid)}


@router.post("/{jid}/cancel")
def cancel(jid: str, db=Depends(db_session), _u=Depends(current_user)):
    from ..workers import get_worker
    j = db.query(ProcessingJob).filter_by(id=jid).first()
    if not j:
        raise HTTPException(404, "job not found")
    try:
        get_worker().cancel(jid)
    except (AssertionError, RuntimeError) as e:
        log.warning("cancel via worker failed (%s); marking cancelled", e)
        j.status = "cancelled"
        db.commit()
    return {"cancelled": jid}


@router.post("/{jid}/retry")
def retry(jid: str, db=Depends(db_session), _u=Depends(current_user)):
    """Resume a terminal failed/cancelled job. Pipeline skips done stages, so a
    mid-job crash re-runs from the interrupted stage without re-ingesting."""
    from ..workers import get_worker
    j = db.query(ProcessingJob).filter_by(id=jid).first()
    if not j:
        raise HTTPException(404, "job not found")
    if j.status in ("queued", "running"):
        raise HTTPException(409, "job already active")
    j.status, j.error, j.progress = "queued", "", 0
    j.current_stage, j.last_heartbeat = "queued", None
    for st in j.stages:
        if st.status != "done":
            st.status, st.error, st.progress = "pending", "", 0
            st.started_at = st.completed_at = None
    db.commit()
    log.info("retry job: %s", jid)
    try:
        get_worker().submit(j.id)
    except (AssertionError, RuntimeError) as e:
        log.warning("retry submit deferred (%s); dispatcher will pick up", e)
    return {"job_id": j.id, "status": "queued"}


@router.get("/{jid}/events")
async def events(jid: str, db=Depends(db_session), _u=Depends(current_user)):
    """SSE live progress with polling fallback on the client."""
    async def gen():
        for _ in range(600):  # ~10 min cap; client reconnects
            d = db_session()
            try:
                j = d.query(ProcessingJob).filter_by(id=jid).first()
                if not j:
                    yield "event: error\ndata: {\"error\": \"not found\"}\n\n"
                    return
                yield "data: " + json.dumps({
                    "status": j.status, "progress": j.progress,
                    "stage": j.current_stage, "error": j.error,
                    "stages": _stages(d, jid)}) + "\n\n"
                if j.status in ("ready_for_review", "failed", "cancelled"):
                    return
            finally:
                d.close()
            await asyncio.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")
