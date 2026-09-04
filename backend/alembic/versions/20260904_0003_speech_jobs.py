"""Link processing jobs to speech attachments and transcriptions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = "20260904_0003"
down_revision = "20260904_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("processing_jobs")}
    if "attachment_id" not in columns:
        op.add_column("processing_jobs", sa.Column("attachment_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_processing_jobs_attachment_id_attachments", "processing_jobs", "attachments", ["attachment_id"], ["id"], ondelete="CASCADE")
    if "transcription_id" not in columns:
        op.add_column("processing_jobs", sa.Column("transcription_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_processing_jobs_transcription_id_transcriptions", "processing_jobs", "transcriptions", ["transcription_id"], ["id"], ondelete="CASCADE")
    indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes("processing_jobs")}
    if "ix_processing_jobs_attachment_id" not in indexes:
        op.create_index("ix_processing_jobs_attachment_id", "processing_jobs", ["attachment_id"])
    if "ix_processing_jobs_transcription_id" not in indexes:
        op.create_index("ix_processing_jobs_transcription_id", "processing_jobs", ["transcription_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_transcription_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_attachment_id", table_name="processing_jobs")
    op.drop_constraint("fk_processing_jobs_transcription_id_transcriptions", "processing_jobs", type_="foreignkey")
    op.drop_constraint("fk_processing_jobs_attachment_id_attachments", "processing_jobs", type_="foreignkey")
    op.drop_column("processing_jobs", "transcription_id")
    op.drop_column("processing_jobs", "attachment_id")
