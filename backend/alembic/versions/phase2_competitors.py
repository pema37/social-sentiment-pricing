"""add competitor tracking tables

Revision ID: phase2_competitors
Revises: 388bc29ec2d1
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase2_competitors'
down_revision = '388bc29ec2d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create competitors table
    op.create_table(
        'competitors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scraping_config', postgresql.JSON(), nullable=True, default={}),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scrape_frequency_minutes', sa.Integer(), nullable=False, default=60),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_competitors_user_id', 'competitors', ['user_id'])
    op.create_index('ix_competitors_name', 'competitors', ['name'])
    op.create_index('ix_competitors_is_active', 'competitors', ['is_active'])

    # Create competitor_products table
    op.create_table(
        'competitor_products',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('competitor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('competitor_product_name', sa.String(500), nullable=False),
        sa.Column('competitor_product_url', sa.String(1000), nullable=False),
        sa.Column('competitor_sku', sa.String(100), nullable=True),
        sa.Column('current_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('last_price_update', sa.DateTime(timezone=True), nullable=True),
        sa.Column('price_available', sa.Boolean(), nullable=False, default=True),
        sa.Column('match_confidence', sa.Numeric(3, 2), nullable=False, default=1.0),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitors.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_competitor_products_product_id', 'competitor_products', ['product_id'])
    op.create_index('ix_competitor_products_competitor_id', 'competitor_products', ['competitor_id'])
    op.create_index('ix_competitor_products_is_active', 'competitor_products', ['is_active'])

    # Create competitor_price_history table
    op.create_table(
        'competitor_price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('competitor_product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('new_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('change_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('change_percent', sa.Numeric(6, 2), nullable=True),
        sa.Column('change_type', sa.String(50), nullable=False, default='unknown'),
        sa.Column('detected_promotion', sa.Boolean(), nullable=False, default=False),
        sa.Column('promotion_name', sa.String(255), nullable=True),
        sa.Column('was_available', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_available', sa.Boolean(), nullable=False, default=True),
        sa.Column('scraped_url', sa.String(1000), nullable=True),
        sa.Column('scrape_method', sa.String(50), nullable=False, default='http'),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['competitor_product_id'], 
            ['competitor_products.id'], 
            ondelete='CASCADE'
        ),
    )
    op.create_index(
        'ix_competitor_price_history_competitor_product_id', 
        'competitor_price_history', 
        ['competitor_product_id']
    )
    op.create_index(
        'ix_competitor_price_history_observed_at', 
        'competitor_price_history', 
        ['observed_at']
    )


def downgrade() -> None:
    op.drop_table('competitor_price_history')
    op.drop_table('competitor_products')
    op.drop_table('competitors')


