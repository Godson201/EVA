"""Create the EVA V2 PostgreSQL schema."""

from alembic import op

from app.db.base import Base
import app.models  # noqa: F401

revision = "20260903_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
