"""create prospect_audit_events table

Revision ID: prospect_analytics_001
Revises: retro_audit_001
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "prospect_analytics_001"
down_revision = "retro_audit_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prospect_audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("store_url", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("input_mode", sa.String(10), nullable=True),
        sa.Column("products_found", sa.Integer(), nullable=True),
        sa.Column("estimated_impact", sa.String(50), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("prospect_audit_events")



    