"""Initial schema baseline. Existing initialized databases may safely upgrade."""
from alembic import op
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
 from backend.app.main import Base
 Base.metadata.create_all(bind=op.get_bind(),checkfirst=True)
def downgrade():
 raise RuntimeError('Destructive downgrade is disabled. Restore a reviewed database backup instead.')
