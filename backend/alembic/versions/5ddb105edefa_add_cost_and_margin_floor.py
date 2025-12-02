"""add_cost_and_margin_floor

Revision ID: 5ddb105edefa
Revises: d99408af71fc
Create Date: 2025-12-02 06:04:20.607078
"""
from alembic import op
import sqlalchemy as sa


revision = '5ddb105edefa'
down_revision = 'd99408af71fc'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('cost', sa.Numeric(10, 2), nullable=True))
    op.add_column('pricing_settings', sa.Column('min_margin_percent', sa.Numeric(5, 2), nullable=False, server_default='10.0'))


def downgrade():
    op.drop_column('pricing_settings', 'min_margin_percent')
    op.drop_column('products', 'cost')

