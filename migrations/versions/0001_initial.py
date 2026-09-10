"""Initial schema: projects, media, jobs, transcripts, scenes, candidates,
clips, metadata, review, exports, settings, providers.

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _tbl(name, *cols):
    op.create_table(
        name,
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        *cols)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("user_id", sa.String(64), server_default="local"),
        sa.Column("title", sa.String(255), server_default="Untitled"),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("duration", sa.Float, server_default="0"),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("config", sa.JSON, server_default="{}"))
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("kind", sa.String(16), server_default="source"),
        sa.Column("storage_key", sa.String(512)),
        sa.Column("mime", sa.String(128), server_default=""),
        sa.Column("size", sa.Integer, server_default="0"),
        sa.Column("meta", sa.JSON, server_default="{}"))
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("status", sa.String(32), server_default="queued"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("current_stage", sa.String(32), server_default="queued"),
        sa.Column("error", sa.Text, server_default=""),
        sa.Column("params", sa.JSON, server_default="{}"))
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("job_id", sa.String(32), sa.ForeignKey("processing_jobs.id")),
        sa.Column("name", sa.String(32)),
        sa.Column("status", sa.String(16), server_default="pending"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("error", sa.Text, server_default=""))
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("engine", sa.String(64), server_default=""),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("duration", sa.Float, server_default="0"),
        sa.Column("words", sa.JSON, server_default="[]"),
        sa.Column("segments", sa.JSON, server_default="[]"))
    op.create_table(
        "scenes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("start", sa.Float), sa.Column("end", sa.Float),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("engine", sa.String(32), server_default=""))
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("job_id", sa.String(32), sa.ForeignKey("processing_jobs.id")),
        sa.Column("start", sa.Float), sa.Column("end", sa.Float),
        sa.Column("text", sa.Text, server_default=""),
        sa.Column("hook_text", sa.Text, server_default=""),
        sa.Column("features", sa.JSON, server_default="{}"),
        sa.Column("eligible", sa.Boolean, server_default="1"),
        sa.Column("score", sa.Float, server_default="0"))
    op.create_table(
        "candidate_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.String(32), sa.ForeignKey("candidates.id")),
        sa.Column("source", sa.String(32)),
        sa.Column("model", sa.String(128), server_default=""),
        sa.Column("prompt_version", sa.String(32), server_default=""),
        sa.Column("axes", sa.JSON, server_default="{}"),
        sa.Column("overall", sa.Float, server_default="0"),
        sa.Column("reason", sa.Text, server_default=""))
    op.create_table(
        "clips",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("job_id", sa.String(32), sa.ForeignKey("processing_jobs.id")),
        sa.Column("candidate_id", sa.String(32), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("start", sa.Float), sa.Column("end", sa.Float),
        sa.Column("storage_key", sa.String(512), server_default=""),
        sa.Column("status", sa.String(32), server_default="rendered"),
        sa.Column("render_profile", sa.String(64), server_default="shorts_1080x1920"),
        sa.Column("validation", sa.JSON, server_default="{}"))
    op.create_table(
        "caption_styles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), unique=True),
        sa.Column("config", sa.JSON, server_default="{}"))
    op.create_table(
        "generated_metadata",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("clip_id", sa.String(32), sa.ForeignKey("clips.id")),
        sa.Column("titles", sa.JSON, server_default="[]"),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("caption", sa.Text, server_default=""),
        sa.Column("hashtags", sa.JSON, server_default="[]"),
        sa.Column("keywords", sa.JSON, server_default="[]"),
        sa.Column("chosen_title", sa.Integer, server_default="0"))
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("clip_id", sa.String(32), sa.ForeignKey("clips.id")),
        sa.Column("user_id", sa.String(64), server_default="local"),
        sa.Column("decision", sa.String(16)),
        sa.Column("note", sa.Text, server_default=""))
    op.create_table(
        "exports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id")),
        sa.Column("storage_key", sa.String(512), server_default=""),
        sa.Column("manifest", sa.JSON, server_default="{}"))
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text, server_default=""))
    op.create_table(
        "ai_providers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("kind", sa.String(32)),
        sa.Column("name", sa.String(64)),
        sa.Column("config", sa.JSON, server_default="{}"),
        sa.Column("enabled", sa.Boolean, server_default="1"),
        sa.Column("last_check", sa.DateTime, nullable=True),
        sa.Column("last_status", sa.String(32), server_default="unknown"))
    for tbl, cols in [
        ("projects", ["user_id", "status", "created_at"]),
        ("media_assets", ["project_id"]), ("processing_jobs", ["project_id", "status", "created_at"]),
        ("pipeline_stages", ["job_id", "name"]), ("transcripts", ["project_id"]),
        ("scenes", ["project_id"]), ("candidates", ["project_id", "job_id", "score"]),
        ("candidate_scores", ["candidate_id"]), ("clips", ["project_id", "job_id", "status"]),
        ("generated_metadata", ["clip_id"]), ("review_decisions", ["clip_id"]),
        ("exports", ["project_id"])]:
        for c in cols:
            op.create_index(f"ix_{tbl}_{c}", tbl, [c])
    op.create_index("ix_candidates_project_score", "candidates", ["project_id", "score"])
    op.create_index("ix_clips_project_status", "clips", ["project_id", "status"])


def downgrade() -> None:
    for tbl in ("ai_providers", "system_settings", "exports", "review_decisions",
                "generated_metadata", "caption_styles", "clips", "candidate_scores",
                "candidates", "scenes", "transcripts", "pipeline_stages",
                "processing_jobs", "media_assets", "projects"):
        op.drop_table(tbl)
