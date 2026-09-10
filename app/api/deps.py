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
                 s: Settings = Depends(settings_dep)) -> str:
    """Local single-account: no token configured = open (dev). With AUTH_TOKEN
    set, require `Authorization: Bearer <token>`."""
    if not s.auth_token:
        return "local"
    if authorization == f"Bearer {s.auth_token}":
        return "local"
    raise HTTPException(401, "unauthorized")
