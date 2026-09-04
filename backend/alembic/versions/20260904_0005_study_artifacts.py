"""Add durable, source-linked study artifacts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260904_0005"
down_revision = "20260904_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.has_table(op.get_bind(), "study_artifacts"):
        return
    op.create_table(
        "study_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("artifact_type", sa.String(30), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("input_text", sa.Text()), sa.Column("language", sa.String(20), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False), sa.Column("audience", sa.String(100), nullable=False),
        sa.Column("length", sa.String(20), nullable=False), sa.Column("content", JSONB(), nullable=False),
        sa.Column("source_refs", JSONB(), nullable=False), sa.Column("provider", sa.String(50)), sa.Column("model", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_study_artifacts_user_id", "study_artifacts", ["user_id"])
    op.create_index("ix_study_artifacts_conversation_id", "study_artifacts", ["conversation_id"])
    op.create_index("ix_study_artifacts_document_id", "study_artifacts", ["document_id"])
    op.create_index("ix_study_artifacts_artifact_type", "study_artifacts", ["artifact_type"])


def downgrade() -> None:
    op.drop_table("study_artifacts")
