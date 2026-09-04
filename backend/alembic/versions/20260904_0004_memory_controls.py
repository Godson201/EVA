"""Add explicit memory consent, provenance, deduplication, and retention fields."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260904_0004"
down_revision = "20260904_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column("memories", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("memories", sa.Column("provenance", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("memories", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE memories SET content_hash = encode(sha256(convert_to(lower(trim(content)), 'UTF8')), 'hex')")
    op.alter_column("memories", "content_hash", nullable=False)
    op.create_index("ix_memories_content_hash", "memories", ["content_hash"])
    op.create_index("ix_memories_expires_at", "memories", ["expires_at"])
    op.create_index("ix_memories_user_category_hash", "memories", ["user_id", "category", "content_hash"])


def downgrade() -> None:
    op.drop_index("ix_memories_user_category_hash", table_name="memories")
    op.drop_index("ix_memories_expires_at", table_name="memories")
    op.drop_index("ix_memories_content_hash", table_name="memories")
    op.drop_column("memories", "expires_at")
    op.drop_column("memories", "deleted_at")
    op.drop_column("memories", "rejected_at")
    op.drop_column("memories", "provenance")
    op.drop_column("memories", "content_hash")
