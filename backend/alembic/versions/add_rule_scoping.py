"""Add rule scoping fields

Revision ID: rule_scoping_001
Revises: <YOUR_LATEST_REVISION>
Create Date: 2024-12-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = 'rule_scoping_001'
down_revision = 'phase2_competitors' 
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('pricing_rules',
        sa.Column('applies_to_all_products', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('pricing_rules',
        sa.Column('applies_to_products', JSONB, nullable=True))
    op.add_column('pricing_rules',
        sa.Column('applies_to_categories', JSONB, nullable=True))
    op.alter_column('pricing_rules', 'product_id',
        existing_type=UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.drop_column('pricing_rules', 'applies_to_categories')
    op.drop_column('pricing_rules', 'applies_to_products')
    op.drop_column('pricing_rules', 'applies_to_all_products')
    op.alter_column('pricing_rules', 'product_id',
        existing_type=UUID(as_uuid=True), nullable=False)
    
