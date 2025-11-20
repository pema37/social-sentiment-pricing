"""Initial DB schema

Revision ID: 5b445434844a
Revises: 01b2c3d4e5f6
Create Date: 2025-11-20 09:36:12.661629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5b445434844a'
down_revision: Union[str, Sequence[str], None] = '01b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: drop old tables to prepare for new schema.

    WARNING: this will remove data in existing tables.
    Adjust as needed if you want to preserve data.
    """
    # Drop indexes first to avoid dependency conflicts
    op.drop_index(op.f('ix_competitor_name'), table_name='competitor')
    op.drop_index(op.f('ix_competitorproduct_competitor_id'), table_name='competitorproduct')
    op.drop_index(op.f('ix_competitorproduct_product_id'), table_name='competitorproduct')
    op.drop_index(op.f('ix_product_owner_id'), table_name='product')
    op.drop_index(op.f('ix_product_sku'), table_name='product')

    # Drop tables in order that respects foreign key dependencies
    op.drop_table('competitorproduct')
    op.drop_table('playing_with_neon')
    op.drop_table('product')
    op.drop_table('competitor')


def downgrade() -> None:
    """Downgrade schema: recreate previously dropped tables and indexes."""

    # Recreate product table
    op.create_table(
        'product',
        sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('product_id_seq'::regclass)"), autoincrement=True, nullable=False),
        sa.Column('owner_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('sku', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('base_price', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False),
        sa.Column('currency', sa.VARCHAR(length=3), autoincrement=False, nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name='product_pkey'),
        postgresql_ignore_search_path=False
    )
    op.create_index(op.f('ix_product_sku'), 'product', ['sku'], unique=False)
    op.create_index(op.f('ix_product_owner_id'), 'product', ['owner_id'], unique=False)

    # Recreate competitorproduct table
    op.create_table(
        'competitorproduct',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('competitor_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('competitor_sku', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('competitor_url', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('last_seen_price', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
        sa.Column('currency', sa.VARCHAR(length=3), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitor.id'], name=op.f('competitorproduct_competitor_id_fkey')),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], name=op.f('competitorproduct_product_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('competitorproduct_pkey'))
    )
    op.create_index(op.f('ix_competitorproduct_product_id'), 'competitorproduct', ['product_id'], unique=False)
    op.create_index(op.f('ix_competitorproduct_competitor_id'), 'competitorproduct', ['competitor_id'], unique=False)

    # Recreate playing_with_neon table
    op.create_table(
        'playing_with_neon',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('value', sa.REAL(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('playing_with_neon_pkey'))
    )

    # Recreate competitor table
    op.create_table(
        'competitor',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('website', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('competitor_pkey'))
    )
    op.create_index(op.f('ix_competitor_name'), 'competitor', ['name'], unique=False)
