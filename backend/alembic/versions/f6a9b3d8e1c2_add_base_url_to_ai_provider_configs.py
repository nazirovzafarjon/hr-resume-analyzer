"""Add base_url to user_ai_provider_configs (additive, nullable)."""
from alembic import op
import sqlalchemy as sa

revision = 'f6a9b3d8e1c2'
down_revision = 'f5c7d8a9e1b2'
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("user_ai_provider_configs")}
    if "base_url" not in columns:
        op.add_column('user_ai_provider_configs', sa.Column('base_url', sa.String(length=500), nullable=True))

def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("user_ai_provider_configs")}
    if "base_url" in columns:
        op.drop_column('user_ai_provider_configs', 'base_url')
