"""add_alert_tables

Revision ID: ae4a25042fb1
Revises: 2e0555049c32
Create Date: 2025-12-03 08:06:55.046396

"""
from typing import Sequence, Union

import sqlmodel
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ae4a25042fb1'
down_revision: Union[str, Sequence[str], None] = '2e0555049c32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create alert_configurations table
    op.create_table('alert_configurations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alert_type', sa.Enum('SENTIMENT_DROP', 'SENTIMENT_SPIKE', 'VOLUME_SURGE', 'VIRAL_MENTION', 'COMPETITOR_PRICE_CHANGE', 'PRICE_RECOMMENDATION', 'PRICE_APPLIED', 'TREND_DETECTED', 'ANOMALY_DETECTED', name='alerttype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('product_ids', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('channels', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('channel_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False),
        sa.Column('max_per_day', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_configurations_user_id'), 'alert_configurations', ['user_id'], unique=False)
    
    # Create alerts table
    op.create_table('alerts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('configuration_id', sa.Uuid(), nullable=True),
        sa.Column('alert_type', sa.Enum('SENTIMENT_DROP', 'SENTIMENT_SPIKE', 'VOLUME_SURGE', 'VIRAL_MENTION', 'COMPETITOR_PRICE_CHANGE', 'PRICE_RECOMMENDATION', 'PRICE_APPLIED', 'TREND_DETECTED', 'ANOMALY_DETECTED', name='alerttype'), nullable=False),
        sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='alertseverity'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('product_id', sa.Uuid(), nullable=True),
        sa.Column('competitor_id', sa.Uuid(), nullable=True),
        sa.Column('recommendation_id', sa.Uuid(), nullable=True),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', 'ACKNOWLEDGED', 'RESOLVED', name='alertstatus'), nullable=False),
        sa.Column('channels_sent', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('channels_failed', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', sa.Uuid(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitors.id'], ),
        sa.ForeignKeyConstraint(['configuration_id'], ['alert_configurations.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['recommendation_id'], ['price_recommendations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_created_at'), 'alerts', ['created_at'], unique=False)
    op.create_index(op.f('ix_alerts_user_id'), 'alerts', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_alerts_user_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_created_at'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_index(op.f('ix_alert_configurations_user_id'), table_name='alert_configurations')
    op.drop_table('alert_configurations')
    
    # Drop the enums
    sa.Enum(name='alertstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='alertseverity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='alerttype').drop(op.get_bind(), checkfirst=True)
