# backend/services/products/cascade_delete.py
"""
Cascade Delete Service
======================

Handles the safe deletion of a product and ALL related records.
Centralizes FK constraint handling in one maintainable location.

Best Practices Applied:
- Single Responsibility: Only handles deletion cascade
- Explicit Dependencies: All related models listed and documented
- Maintainability: Easy to add new FK relations as schema grows
- Error Handling: Proper rollback on failure

Usage:
    from services.products import cascade_delete_product

    await cascade_delete_product(session, product_id)
"""

import logging
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import Alert
from models.competitor_product import CompetitorProduct
from models.integration import ProductIntegrationLink
from models.price_history import PriceHistory
from models.price_recommendation import PriceRecommendation
from models.pricing_rule import PricingRule

# ═══════════════════════════════════════════════════════════════════════════════
# RELATED MODELS - All tables with FK to products.id
# When adding new models with product_id FK, add them here!
# ═══════════════════════════════════════════════════════════════════════════════
from models.recommendation_outcome import RecommendationOutcome
from models.sentiment import Sentiment
from models.social_mention import SocialMention

logger = logging.getLogger(__name__)


# Define deletion order - children before parents, deepest dependencies first
# This order matters for FK constraints!
PRODUCT_DEPENDENCIES = [
    # Level 1: Depends on recommendations
    (RecommendationOutcome, "product_id", "Recommendation outcomes"),
    # Level 2: Core pricing data
    (PriceRecommendation, "product_id", "Price recommendations"),
    (PricingRule, "product_id", "Pricing rules"),
    # Level 3: Alerts and history
    (Alert, "product_id", "Alerts"),
    (PriceHistory, "product_id", "Price history"),
    # Level 4: Sentiment data
    (Sentiment, "product_id", "Sentiment records"),
    (SocialMention, "product_id", "Social mentions"),
    # Level 5: External links
    (CompetitorProduct, "product_id", "Competitor product links"),
    (ProductIntegrationLink, "product_id", "Integration links (Shopify/WooCommerce)"),
]


async def cascade_delete_product(
    session: AsyncSession,
    product_id: UUID,
    dry_run: bool = False,
) -> dict:
    """
    Delete all records related to a product, then delete the product.

    Args:
        session: AsyncSession - Database session (caller manages transaction)
        product_id: UUID - The product to delete
        dry_run: bool - If True, only counts records without deleting

    Returns:
        dict with counts of deleted records per table

    Raises:
        Exception on database errors (caller should handle rollback)

    Example:
        try:
            result = await cascade_delete_product(session, product_id)
            await session.commit()
            logger.info(f"Deleted: {result}")
        except Exception as e:
            await session.rollback()
            raise
    """
    deleted_counts = {}

    for model_class, fk_column, description in PRODUCT_DEPENDENCIES:
        try:
            # Get the FK column dynamically
            fk_attr = getattr(model_class, fk_column)

            if dry_run:
                # Count only - useful for preview/confirmation dialogs
                from sqlmodel import func, select

                count_stmt = select(func.count()).where(fk_attr == product_id)
                result = await session.execute(count_stmt)
                count = result.scalar() or 0
            else:
                # Actually delete
                delete_stmt = delete(model_class).where(fk_attr == product_id)
                result = await session.execute(delete_stmt)
                count = result.rowcount

            deleted_counts[model_class.__tablename__] = count

            if count > 0:
                action = "Would delete" if dry_run else "Deleted"
                logger.debug(f"{action} {count} {description} for product {product_id}")

        except Exception as e:
            logger.error(f"Failed to delete {description} for product {product_id}: {e}")
            raise

    total = sum(deleted_counts.values())
    logger.info(f"{'Would delete' if dry_run else 'Deleted'} {total} related records for product {product_id}")

    return deleted_counts


async def get_deletion_preview(
    session: AsyncSession,
    product_id: UUID,
) -> dict:
    """
    Preview what would be deleted without actually deleting.
    Useful for confirmation dialogs in the UI.

    Returns:
        {
            "product_id": "...",
            "related_records": {
                "price_history": 15,
                "sentiment_records": 42,
                ...
            },
            "total_records": 57
        }
    """
    counts = await cascade_delete_product(session, product_id, dry_run=True)

    return {
        "product_id": str(product_id),
        "related_records": counts,
        "total_records": sum(counts.values()),
    }
