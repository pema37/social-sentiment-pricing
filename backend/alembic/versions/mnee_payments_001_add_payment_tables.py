"""add_mnee_payment_tables

Revision ID: mnee_payments_001
Revises: b2d5eb33639f
Create Date: 2025-12-25

Adds:
- bsv_wallet_address column to users table
- subscriptions table
- payments table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'mnee_payments_001'
down_revision = 'b2d5eb33639f'  # Your latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add bsv_wallet_address to users table
    op.add_column(
        'users',
        sa.Column('bsv_wallet_address', sa.String(50), nullable=True)
    )
    
    # 2. Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('tier', sa.String(20), nullable=False, server_default='free'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('monthly_price', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    
    # 3. Create payments table
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id'), nullable=True),
        sa.Column('amount', sa.String(20), nullable=False),
        sa.Column('amount_raw', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(10), nullable=False, server_default='MNEE'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('payment_type', sa.String(20), nullable=False, server_default='subscription'),
        sa.Column('txid', sa.String(100), nullable=True),
        sa.Column('from_address', sa.String(50), nullable=True),
        sa.Column('to_address', sa.String(50), nullable=True),
        sa.Column('memo', sa.String(200), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_payments_user_id', 'payments', ['user_id'])
    op.create_index('ix_payments_subscription_id', 'payments', ['subscription_id'])
    op.create_index('ix_payments_txid', 'payments', ['txid'])
    op.create_index('ix_payments_status', 'payments', ['status'])


def downgrade() -> None:
    # Drop payments table
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_index('ix_payments_txid', table_name='payments')
    op.drop_index('ix_payments_subscription_id', table_name='payments')
    op.drop_index('ix_payments_user_id', table_name='payments')
    op.drop_table('payments')
    
    # Drop subscriptions table
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_table('subscriptions')
    
    # Remove bsv_wallet_address from users
    op.drop_column('users', 'bsv_wallet_address')

