"""create retrospective_audits table

Revision ID: retro_audit_001
Revises: (add your current head here)
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers
revision = "retro_audit_001"
down_revision = "sku_per_user_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrospective_audits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("lookback_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("total_products_analyzed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_estimated_impact", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_lost_revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_missed_margin", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("monthly_projected_loss", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("annual_projected_loss", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("summary_json", JSON(), nullable=False, server_default="{}"),
        sa.Column("sku_results_json", JSON(), nullable=False, server_default="[]"),
        sa.Column("analysis_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Index for fast lookup: latest audit per user
    op.create_index(
        "ix_retrospective_audits_user_created",
        "retrospective_audits",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_retrospective_audits_user_created")
    op.drop_table("retrospective_audits")



