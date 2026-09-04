"""Add auditable voice consent and deletion metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260904_0006"
down_revision = "20260904_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("voice_profiles")}
    for name, column in (("consent_assertion", sa.Column("consent_assertion", sa.Text(), nullable=True)), ("purpose", sa.Column("purpose", sa.String(255), nullable=True)), ("deletion_requested_at", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))):
        if name not in columns:
            op.add_column("voice_profiles", column)


def downgrade() -> None:
    op.drop_column("voice_profiles", "deletion_requested_at")
    op.drop_column("voice_profiles", "purpose")
    op.drop_column("voice_profiles", "consent_assertion")
