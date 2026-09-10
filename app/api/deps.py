"""Shared dependencies: DB session, auth, storage, pipeline factory."""
from fastapi import Depends, Header, HTTPException

from ..config.settings import Settings, get_settings
from ..models.db import get_session_factory
from ..services.pipeline import Pipeline
from ..storage.base import StorageProvider
from ..storage.local import LocalFilesystemStorage

try:
    from ..storage.s3 import S3Storage
except ImportError:  # boto3 optional
    S3Storage = None  # type: ignore


def db_session():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def settings_dep() -> Settings:
    return get_settings()


def storage_dep(s: Settings = Depends(settings_dep)) -> StorageProvider:
    if s.storage_backend == "s3":
        if S3Storage is None:
            raise HTTPException(500, "boto3 not installed")
        import os
        return S3Storage(os.environ.get("S3_STORAGE_BUCKET", ""),
                         os.environ.get("S3_STORAGE_PREFIX", "repurposeai/"),
                         os.environ.get("AWS_REGION", ""))
    return LocalFilesystemStorage(s.storage_path)


def pipeline_dep(db=Depends(db_session), s: Settings = Depends(settings_dep),
                 st: StorageProvider = Depends(storage_dep)) -> Pipeline:
    return Pipeline(db, st, s)


def current_user(authorization: str = Header(default=""),
                 s: Settings = Depends(settings_dep),
                 db=Depends(db_session)) -> str:
    """Auth chain: legacy AUTH_TOKEN env -> DB token (password login) ->
    open dev mode (no users configured AND no AUTH_TOKEN). Returns user_id."""
    if authorization.startswith("Bearer "):
        tok = authorization[7:]
        if s.auth_token and tok == s.auth_token:
            return "local"
        import hashlib
        import time

        from ..models.entities import APIToken
        digest = hashlib.sha256(tok.encode()).hexdigest()
        row = db.query(APIToken).filter_by(token_sha=digest).first()
        if row and row.expires_at > time.time():
            return row.user_id
        raise HTTPException(401, "unauthorized")
    from ..models.entities import User
    if not s.auth_token and db.query(User).count() == 0:
        return "local"
    raise HTTPException(401, "unauthorized")
