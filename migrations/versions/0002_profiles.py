"""Candidate score profiles.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidate_scores",
                  sa.Column("profile", sa.String(32), server_default="balanced"))


def downgrade() -> None:
    op.drop_column("candidate_scores", "profile")
