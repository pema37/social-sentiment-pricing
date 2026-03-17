"""create audit_requests table for Price Check leads

Revision ID: price_check_001
Revises: prospect_analytics_001
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "price_check_001"
down_revision = "prospect_analytics_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("store_url", sa.String(500), nullable=False, index=True),
        sa.Column("store_name", sa.String(255), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("products_scanned", sa.Integer(), nullable=True),
        sa.Column("competitors_found", sa.Integer(), nullable=True),
        sa.Column("estimated_monthly_impact", sa.Numeric(10, 2), nullable=True),
        sa.Column("estimated_annual_impact", sa.Numeric(10, 2), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("report_data", JSONB, nullable=True),
        sa.Column("converted", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_requests")
