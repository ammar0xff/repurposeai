"""Campaigns: versioned briefs, blockers, dry-run validation."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.ids import new_id
from ..models.entities import Campaign, Clip
from ..services.campaigns import blockers, create_from_dict, p0_missing
from ..validation.campaign import validate_job
from .deps import current_user, db_session

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignIn(BaseModel):
    name: str
    rules: dict = {}
    verified: bool = False


def _out(c: Campaign) -> dict:
    b = blockers(c.rules or {}, c.verified)
    return {"id": c.id, "name": c.name, "version": c.version,
            "rules": c.rules, "verified": c.verified,
            "p0_missing": p0_missing(c.rules or {}), "blockers": b,
            "ready": not b}


@router.post("", status_code=201)
def create(body: CampaignIn, db=Depends(db_session), _u=Depends(current_user)):
    return _out(create_from_dict(db, _u, body.name, body.rules, body.verified))


@router.get("")
def listing(limit: int = 50, offset: int = 0, db=Depends(db_session),
            _u=Depends(current_user)):
    limit = max(1, min(limit, 200))
    q = db.query(Campaign).filter_by(user_id=_u).order_by(Campaign.created_at.desc())
    rows = q.offset(offset).limit(limit).all()
    return {"total": q.count(), "items": [_out(c) for c in rows]}


@router.get("/{cid}")
def get(cid: str, db=Depends(db_session), _u=Depends(current_user)):
    c = db.query(Campaign).filter_by(id=cid, user_id=_u).first()
    if not c:
        raise HTTPException(404, "campaign not found")
    return _out(c)


@router.put("/{cid}")
def update(cid: str, body: CampaignIn, db=Depends(db_session),
           _u=Depends(current_user)):
    c = db.query(Campaign).filter_by(id=cid, user_id=_u).first()
    if not c:
        raise HTTPException(404, "campaign not found")
    c.name, c.rules, c.verified = body.name[:128], dict(body.rules), body.verified
    c.version = (c.version or 1) + 1
    db.commit()
    return _out(c)


@router.delete("/{cid}")
def delete(cid: str, db=Depends(db_session), _u=Depends(current_user)):
    c = db.query(Campaign).filter_by(id=cid, user_id=_u).first()
    if not c:
        raise HTTPException(404, "campaign not found")
    db.delete(c)
    db.commit()
    return {"deleted": cid}


@router.post("/validate")
def validate(body: dict, db=Depends(db_session), _u=Depends(current_user)):
    """Dry-run gate over already-rendered clips. Body: {campaign_id, clips:[...], job:{}}.
    Each clip: {file, duration, width, height, captioned, candidate, title, caption}."""
    c = db.query(Campaign).filter_by(id=body.get("campaign_id", ""),
                                     user_id=_u).first()
    if not c:
        raise HTTPException(404, "campaign not found")
    job = dict(body.get("job", {}))
    if not job.get("extra_tags"):
        job["extra_tags"] = (c.rules or {}).get("hashtags", [])
    return validate_job(body.get("clips", []), c.rules or {}, job)


@router.get("/{cid}/clips")
def campaign_clips(cid: str, db=Depends(db_session), _u=Depends(current_user)):
    """Clips rendered under this campaign (via job params)."""
    from ..models.entities import ProcessingJob
    c = db.query(Campaign).filter_by(id=cid, user_id=_u).first()
    if not c:
        raise HTTPException(404, "campaign not found")
    out = []
    for cl in db.query(Clip).order_by(Clip.created_at.desc()).limit(200).all():
        j = db.query(ProcessingJob).filter_by(id=cl.job_id).first()
        if j and (j.params or {}).get("campaign_id") == cid:
            out.append({"id": cl.id, "start": cl.start, "end": cl.end,
                        "status": cl.status, "validation": cl.validation})
    return out
