"""Add explicit memory consent, provenance, deduplication, and retention fields."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260904_0004"
down_revision = "20260904_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("memories")}
    additions = {"content_hash": sa.Column("content_hash", sa.String(length=64), nullable=True), "provenance": sa.Column("provenance", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), "rejected_at": sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True), "deleted_at": sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), "expires_at": sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)}
    for name, column in additions.items():
        if name not in columns:
            op.add_column("memories", column)
    if "content_hash" not in columns:
        op.execute("UPDATE memories SET content_hash = encode(sha256(convert_to(lower(trim(content)), 'UTF8')), 'hex')")
        op.alter_column("memories", "content_hash", nullable=False)
    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("memories")}
    for name, fields in (("ix_memories_content_hash", ["content_hash"]), ("ix_memories_expires_at", ["expires_at"]), ("ix_memories_user_category_hash", ["user_id", "category", "content_hash"])):
        if name not in indexes:
            op.create_index(name, "memories", fields)


def downgrade() -> None:
    op.drop_index("ix_memories_user_category_hash", table_name="memories")
    op.drop_index("ix_memories_expires_at", table_name="memories")
    op.drop_index("ix_memories_content_hash", table_name="memories")
    op.drop_column("memories", "expires_at")
    op.drop_column("memories", "deleted_at")
    op.drop_column("memories", "rejected_at")
    op.drop_column("memories", "provenance")
    op.drop_column("memories", "content_hash")
