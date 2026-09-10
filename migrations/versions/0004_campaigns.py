"""Campaigns table.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("user_id", sa.String(64), server_default="local"),
        sa.Column("name", sa.String(128)),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("rules", sa.JSON, server_default="{}"),
        sa.Column("verified", sa.Boolean, server_default="0"))
    op.create_index("ix_campaigns_user", "campaigns", ["user_id"])


def downgrade() -> None:
    op.drop_table("campaigns")
