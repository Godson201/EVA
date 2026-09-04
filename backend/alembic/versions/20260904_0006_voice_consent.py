"""Add auditable voice consent and deletion metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20260904_0006"
down_revision = "20260904_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("voice_profiles", sa.Column("consent_assertion", sa.Text(), nullable=True))
    op.add_column("voice_profiles", sa.Column("purpose", sa.String(255), nullable=True))
    op.add_column("voice_profiles", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("voice_profiles", "deletion_requested_at")
    op.drop_column("voice_profiles", "purpose")
    op.drop_column("voice_profiles", "consent_assertion")
