"""Pydantic request/response schemas. API boundary only."""
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str = "Untitled"
    description: str = ""
    config: dict = Field(default_factory=dict)


class ProjectOut(BaseModel):
    id: str
    title: str
    description: str = ""
    language: str | None = None
    duration: float = 0
    status: str
    config: dict = {}
    created_at: str = ""
    updated_at: str = ""


class JobCreate(BaseModel):
    source: str = ""          # local path | URL (ingested by worker)
    filename: str = ""
    upload_key: str = ""      # pre-uploaded storage key (from POST /upload)
    params: dict = Field(default_factory=dict)


class ClipOut(BaseModel):
    id: str
    start: float
    end: float
    status: str
    score: float = 0
    render_profile: str = ""


class ReviewIn(BaseModel):
    decision: str  # approved|rejected|needs_edit|exported
    note: str = ""


class RerenderIn(BaseModel):
    start: float | None = None
    end: float | None = None
    caption_style: str | None = None
    reframe: str | None = None
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None


class ExportOut(BaseModel):
    id: str
    storage_key: str
    manifest: dict = {}
