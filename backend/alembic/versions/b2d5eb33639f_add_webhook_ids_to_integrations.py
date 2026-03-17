"""add_webhook_ids_to_integrations

Revision ID: b2d5eb33639f
Revises: 0f65b2d9de7c
Create Date: 2025-12-10 13:25:57.598418

"""

"""add_webhook_ids_to_integrations

Revision ID: b2d5eb33639f
Revises: 0f65b2d9de7c
Create Date: 2025-12-10 13:25:57.598418

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

revision = "b2d5eb33639f"
down_revision = "0f65b2d9de7c"


def upgrade():
    op.add_column("integrations", sa.Column("webhook_ids", JSON, nullable=True, server_default="[]"))


def downgrade():
    op.drop_column("integrations", "webhook_ids")
