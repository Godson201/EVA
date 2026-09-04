"""Add queued document processing jobs."""

from alembic import op
from app.models import ProcessingJob

revision = "20260904_0002"
down_revision = "20260903_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ProcessingJob.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ProcessingJob.__table__.drop(bind=op.get_bind(), checkfirst=True)
