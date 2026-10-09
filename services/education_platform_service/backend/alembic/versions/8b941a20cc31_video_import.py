from alembic import op
import sqlalchemy as sa

revision = '8b941a20cc31'
down_revision = '6c2f1b7a9e40'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('modules', sa.Column('video_import_status', sa.String(32), nullable=False, server_default=''))

def downgrade():
    op.drop_column('modules', 'video_import_status')
