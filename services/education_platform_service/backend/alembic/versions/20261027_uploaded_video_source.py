"""Keep uploaded video source separate from the playable output."""
from alembic import op
import sqlalchemy as sa

revision = "20261027_upload_source"
down_revision = "8b941a20cc31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("modules", sa.Column("video_import_source", sa.String(500), nullable=False, server_default=""))


def downgrade():
    op.drop_column("modules", "video_import_source")
