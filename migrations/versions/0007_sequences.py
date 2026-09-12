"""sequences: montage timelines (ordered clips + transitions + overrides).

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sequences",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32),
                  sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(64), server_default="local"),
        sa.Column("name", sa.String(255), server_default="Montage"),
        sa.Column("items", sa.JSON, server_default="[]"),
        sa.Column("rendered_key", sa.String(512), server_default=""),
        sa.Column("rendered_validation", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_sequences_project_id", "sequences", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_sequences_project_id", table_name="sequences")
    op.drop_table("sequences")