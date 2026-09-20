"""Add private nested document folders and automatic classification."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260920_0009"
down_revision = "20260904_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_folders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("document_folders.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_document_folders_user_id", "document_folders", ["user_id"])
    op.create_index("ix_document_folders_parent_id", "document_folders", ["parent_id"])
    op.add_column("documents", sa.Column("folder_id", UUID(as_uuid=True), sa.ForeignKey("document_folders.id", ondelete="SET NULL")))
    op.add_column("documents", sa.Column("classification", sa.String(40), nullable=False, server_default="general"))
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])
    op.create_index("ix_documents_classification", "documents", ["classification"])


def downgrade() -> None:
    op.drop_index("ix_documents_classification", table_name="documents")
    op.drop_index("ix_documents_folder_id", table_name="documents")
    op.drop_column("documents", "classification")
    op.drop_column("documents", "folder_id")
    op.drop_index("ix_document_folders_parent_id", table_name="document_folders")
    op.drop_index("ix_document_folders_user_id", table_name="document_folders")
    op.drop_table("document_folders")
