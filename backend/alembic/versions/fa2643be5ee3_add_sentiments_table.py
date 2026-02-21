"""add sentiments table

Revision ID: fa2643be5ee3
Revises: f1a2b3c4d5e6
Create Date: 2026-01-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'fa2643be5ee3'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('sentiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('compound_score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('positive_score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('negative_score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('neutral_score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sentiments_product_id', 'sentiments', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_sentiments_product_id', table_name='sentiments')
    op.drop_table('sentiments')


