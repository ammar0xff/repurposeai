"""Relational schema: projects, media, jobs+stages, transcripts, scenes,
candidates+scores, clips, review, exports, settings, providers."""
import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Timestamped, UUIDPk


class Project(Base, UUIDPk, Timestamped):
    __tablename__ = "projects"
    user_id: Mapped[str] = mapped_column(String(64), index=True, default="local")
    title: Mapped[str] = mapped_column(String(255), default="Untitled")
    description: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    assets: Mapped[list["MediaAsset"]] = relationship(back_populates="project",
                                                      cascade="all, delete-orphan")
    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="project",
                                                       cascade="all, delete-orphan")


class MediaAsset(Base, UUIDPk, Timestamped):
    __tablename__ = "media_assets"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="source")  # source|audio|clip|thumb|export
    storage_key: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(128), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    project: Mapped[Project] = relationship(back_populates="assets")


class ProcessingJob(Base, UUIDPk, Timestamped):
    __tablename__ = "processing_jobs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    project: Mapped[Project] = relationship(back_populates="jobs")
    stages: Mapped[list["PipelineStage"]] = relationship(back_populates="job",
                                                         cascade="all, delete-orphan")


class PipelineStage(Base, UUIDPk):
    __tablename__ = "pipeline_stages"
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    name: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    job: Mapped[ProcessingJob] = relationship(back_populates="stages")


class Transcript(Base, UUIDPk, Timestamped):
    __tablename__ = "transcripts"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    engine: Mapped[str] = mapped_column(String(64), default="")
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0)
    words: Mapped[list] = mapped_column(JSON, default=list)
    segments: Mapped[list] = mapped_column(JSON, default=list)


class Scene(Base, UUIDPk):
    __tablename__ = "scenes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    engine: Mapped[str] = mapped_column(String(32), default="")


class Candidate(Base, UUIDPk, Timestamped):
    __tablename__ = "candidates"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text, default="")
    hook_text: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    eligible: Mapped[bool] = mapped_column(default=True)
    score: Mapped[float] = mapped_column(Float, default=0, index=True)
    scores: Mapped[list["CandidateScore"]] = relationship(back_populates="candidate",
                                                          cascade="all, delete-orphan")


class CandidateScore(Base):
    __tablename__ = "candidate_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))  # llm:<name> | heuristic
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    axes: Mapped[dict] = mapped_column(JSON, default=dict)
    overall: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    candidate: Mapped[Candidate] = relationship(back_populates="scores")


class Clip(Base, UUIDPk, Timestamped):
    __tablename__ = "clips"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    candidate_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    storage_key: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="rendered", index=True)
    render_profile: Mapped[str] = mapped_column(String(64), default="shorts_1080x1920")
    validation: Mapped[dict] = mapped_column(JSON, default=dict)


class CaptionStyle(Base, UUIDPk):
    __tablename__ = "caption_styles"
    name: Mapped[str] = mapped_column(String(64), unique=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class GeneratedMetadata(Base, UUIDPk, Timestamped):
    __tablename__ = "generated_metadata"
    clip_id: Mapped[str] = mapped_column(ForeignKey("clips.id"), index=True)
    titles: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    chosen_title: Mapped[int] = mapped_column(Integer, default=0)


class ReviewDecision(Base, UUIDPk, Timestamped):
    __tablename__ = "review_decisions"
    clip_id: Mapped[str] = mapped_column(ForeignKey("clips.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="local")
    decision: Mapped[str] = mapped_column(String(16))  # approved|rejected|needs_edit|exported
    note: Mapped[str] = mapped_column(Text, default="")


class Export(Base, UUIDPk, Timestamped):
    __tablename__ = "exports"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), default="")
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AIProvider(Base, UUIDPk, Timestamped):
    __tablename__ = "ai_providers"
    kind: Mapped[str] = mapped_column(String(32))  # llm|stt|vision
    name: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_check: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), default="unknown")


Index("ix_candidates_project_score", Candidate.project_id, Candidate.score)
Index("ix_clips_project_status", Clip.project_id, Clip.status)
