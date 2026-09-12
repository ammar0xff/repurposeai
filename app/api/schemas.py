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


class SequenceItemIn(BaseModel):
    clip_id: str
    start: float | None = None
    end: float | None = None
    reframe: str | None = None
    caption_style: str | None = None
    credit: str | None = None
    transition: str | None = None
    transition_duration: float | None = None


class SequenceIn(BaseModel):
    name: str | None = None
    items: list[SequenceItemIn] | None = None


class SequenceOut(BaseModel):
    id: str
    name: str
    items: list[dict] = []
    rendered_key: str = ""
    rendered_validation: dict = {}


class SequenceRenderIn(BaseModel):
    transition: str | None = None
    transition_duration: float | None = None
