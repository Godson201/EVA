"""Add one-time password reset tokens."""

from alembic import op
from app.models import PasswordResetToken

revision = "20260904_0008"
down_revision = "20260904_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    PasswordResetToken.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    PasswordResetToken.__table__.drop(bind=op.get_bind(), checkfirst=True)
