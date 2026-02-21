"""Fix keywords column to JSONB

Revision ID: fix_keywords_jsonb
Revises: e975e3aa34d1
Create Date: 2024-12-31
"""
from alembic import op

revision = 'fix_keywords_jsonb'
down_revision = 'e975e3aa34d1'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE products ALTER COLUMN keywords TYPE JSONB USING keywords::jsonb')

def downgrade():
    op.execute('ALTER TABLE products ALTER COLUMN keywords TYPE JSON USING keywords::json')
