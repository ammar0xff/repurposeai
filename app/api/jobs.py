"""Jobs: list, detail (stages+progress), SSE stream, cancel."""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..models.entities import PipelineStage, ProcessingJob
from .deps import current_user, db_session

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _stages(db, job_id: str) -> list:
    return [{"name": s.name, "status": s.status, "progress": s.progress,
             "started_at": str(s.started_at or ""), "completed_at": str(s.completed_at or ""),
             "error": s.error}
            for s in db.query(PipelineStage).filter_by(job_id=job_id).all()]


@router.get("")
def listing(db=Depends(db_session), _u=Depends(current_user)):
    rows = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(100).all()
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
    except Exception:
        j.status = "cancelled"
        db.commit()
    return {"cancelled": jid}


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
