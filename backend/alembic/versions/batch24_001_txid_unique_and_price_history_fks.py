"""add unique constraint to payment txid and FK constraints to price_history

Revision ID: batch24_001
Revises: fk_ondelete_001
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "batch24_001"
down_revision: Union[str, Sequence[str], None] = "fk_ondelete_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # BUG-290: Add unique constraint to payments.txid
    # PostgreSQL allows multiple NULLs in a unique column, so pending payments
    # (txid=NULL) are unaffected.
    op.create_unique_constraint("uq_payments_txid", "payments", ["txid"])

    # BUG-291: Add foreign key constraints to price_history
    op.create_foreign_key(
        "fk_price_history_user_id",
        "price_history",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_price_history_product_id",
        "price_history",
        "products",
        ["product_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_price_history_product_id", "price_history", type_="foreignkey")
    op.drop_constraint("fk_price_history_user_id", "price_history", type_="foreignkey")
    op.drop_constraint("uq_payments_txid", "payments", type_="unique")
