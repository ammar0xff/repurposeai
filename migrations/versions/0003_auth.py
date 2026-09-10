"""Users + API tokens.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("username", sa.String(64), unique=True),
        sa.Column("pw_hash", sa.String(256)))
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id")),
        sa.Column("token_sha", sa.String(64), unique=True),
        sa.Column("expires_at", sa.Float, server_default="0"))
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_api_tokens_user", "api_tokens", ["user_id"])
    op.create_index("ix_api_tokens_sha", "api_tokens", ["token_sha"])


def downgrade() -> None:
    op.drop_table("api_tokens")
    op.drop_table("users")
