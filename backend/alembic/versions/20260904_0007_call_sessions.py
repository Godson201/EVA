"""Add persisted call-assistant sessions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260904_0007"
down_revision = "20260904_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.has_table(op.get_bind(), "call_sessions"):
        return
    op.create_table("call_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("source_language", sa.String(20)),
        sa.Column("target_language", sa.String(20)), sa.Column("transcript", JSONB(), nullable=False),
        sa.Column("summary", sa.Text()), sa.Column("action_items", JSONB(), nullable=False),
        sa.Column("sentiment_cues", JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_call_sessions_user_id", "call_sessions", ["user_id"])
    op.create_index("ix_call_sessions_status", "call_sessions", ["status"])


def downgrade() -> None:
    op.drop_table("call_sessions")
