"""Password auth: setup (first user), login (token), change, logout.
Tokens are random; only sha256 is stored. Never store plaintext passwords."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ..core.auth import check_password, hash_password, new_token, token_expiry
from ..core.ids import new_id
from ..models.entities import APIToken, User
from .deps import db_session


class Creds(BaseModel):
    username: str
    password: str


class ChangePw(BaseModel):
    username: str
    old_password: str
    new_password: str


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/setup", status_code=201)
def setup(body: Creds, db=Depends(db_session)):
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(409, 'username taken')
    if len(body.password) < 10 or len(body.username) < 2:
        raise HTTPException(422, "username >=2 chars, password >=10 chars")
    u = User(id=new_id(), username=body.username[:64],
             pw_hash=hash_password(body.password))
    db.add(u)
    db.commit()
    return {"user": u.username}


@router.post("/login")
def login(body: Creds, db=Depends(db_session)):
    u = db.query(User).filter_by(username=body.username).first()
    if not u or not check_password(body.password, u.pw_hash):
        raise HTTPException(401, "bad credentials")
    raw, digest = new_token()
    db.add(APIToken(id=new_id(), user_id=u.id, token_sha=digest,
                    expires_at=token_expiry()))
    db.commit()
    return {"token": raw, "user": u.username}


@router.post("/change")
def change(body: ChangePw, db=Depends(db_session)):
    u = db.query(User).filter_by(username=body.username).first()
    if not u or not check_password(body.old_password, u.pw_hash):
        raise HTTPException(401, "bad credentials")
    if len(body.new_password) < 10:
        raise HTTPException(422, "new password >=10 chars")
    u.pw_hash = hash_password(body.new_password)
    db.query(APIToken).filter_by(user_id=u.id).delete()  # rotate: kill sessions
    db.commit()
    return {"changed": True}


@router.post("/logout")
def logout(db=Depends(db_session), authorization: str = Header(default="")):
    import hashlib
    if authorization.startswith('Bearer '):
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        db.query(APIToken).filter_by(token_sha=digest).delete()
        db.commit()
    return {"ok": True}
