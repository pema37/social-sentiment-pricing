# backend/workers/tasks/pricing_tasks.py
"""
Pricing Tasks - Celery tasks for generating price recommendations.

These tasks run on a schedule to:
1. Generate recommendations for all products with active rules
2. Expire old recommendations
3. Check competitor prices and trigger alerts
4. Apply stuck recommendations that failed to push

IMPORTANT: Each task creates its own database session to avoid event loop
conflicts when running in Celery's forked worker processes.

Structure:
- Helpers: Session management and async utilities
- Async Implementations: Core business logic (prefixed with _)
- Celery Tasks: Public API that wraps async implementations
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

import asyncio
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from core.config import settings
from core.logging import get_logger
from models.competitor_product import CompetitorProduct
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.pricing_rule import PricingRule
from models.product import Product
from services.pricing.approval_service import ApprovalService
from services.pricing.recommendation_service import RecommendationService
from workers.celery_app import celery_app

logger = get_logger(__name__)


# ==============================================================================
# HELPERS
# ==============================================================================


def get_task_session_maker():
    """
    Create a fresh async session maker for Celery tasks.

    Uses NullPool to prevent connection reuse across forked processes,
    which would cause "Future attached to a different loop" errors.
    """
    db_url = settings.DATABASE_URL

    # Convert postgresql:// to postgresql+asyncpg:// for async support
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Remove sslmode parameter - asyncpg doesn't support it as a query param
    if "sslmode=" in db_url:
        db_url = re.sub(r"[\?&]sslmode=[^&]*", "", db_url)
        db_url = db_url.replace("?&", "?").replace("&&", "&").rstrip("?&")

    # Determine if SSL should be enabled based on host
    use_ssl = "neon.tech" in db_url or "railway" in db_url

    engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": True} if use_ssl else {},
    )

    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def run_async(coro):
    """
    Run async code in sync Celery task.

    Creates a fresh event loop for each task execution to avoid
    conflicts with asyncpg connections from other workers.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


# ==============================================================================
# ASYNC IMPLEMENTATIONS (Core Business Logic)
# ==============================================================================


async def _generate_all_recommendations():
    """
    Generate recommendations for all products with active rules.

    Flow:
    1. Get all active pricing rules
    2. Get products for users with rules
    3. Generate recommendations for matching products
    4. Auto-apply eligible recommendations (push to e-commerce)
    5. Expire old recommendations
    """
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        # Step 1: Get all active pricing rules
        rules_stmt = select(PricingRule).where(PricingRule.is_active)
        rules_result = await db.execute(rules_stmt)
        active_rules = list(rules_result.scalars().all())

        if not active_rules:
            logger.info("No active pricing rules found")
            return {
                "products_checked": 0,
                "recommendations_created": 0,
                "recommendations_expired": 0,
                "auto_applied": 0,
                "errors": 0,
            }

        # Step 2: Get all active products for users who have rules
        user_ids = list(set(rule.user_id for rule in active_rules))
        products_stmt = select(Product).where(Product.user_id.in_(user_ids)).where(Product.is_active)
        products_result = await db.execute(products_stmt)
        all_products = list(products_result.scalars().all())

        logger.info(f"Found {len(active_rules)} active rules, {len(all_products)} products")

        # Step 3: Filter products that match at least one rule
        products_to_check = []
        for product in all_products:
            for rule in active_rules:
                if rule.user_id != product.user_id:
                    continue
                if rule.applies_to_product(product.id, product.category):
                    products_to_check.append(product)
                    break

        logger.info(f"Checking {len(products_to_check)} products with matching rules")

        # Step 4: Generate recommendations
        recommendations_created = 0
        errors = 0

        for product in products_to_check:
            try:
                service = RecommendationService(db)
                recommendation = await service.generate_recommendation(product=product, user_id=product.user_id)

                if recommendation:
                    recommendations_created += 1
                    logger.info(
                        f"Created recommendation for {product.name}: "
                        f"${product.current_price} -> ${recommendation.recommended_price}"
                    )
            except Exception as e:
                errors += 1
                logger.error(f"Error generating recommendation for product {product.id}: {e}")

        # Step 5: Process auto-approvals (push prices to e-commerce platforms)
        auto_applied = 0
        for user_id in user_ids:
            try:
                approval_service = ApprovalService(db)
                applied = await approval_service.process_auto_approvals(user_id)
                if applied:
                    auto_applied += len(applied)
                    logger.info(f"Auto-applied {len(applied)} recommendations for user {user_id}")
            except Exception as e:
                logger.error(f"Error processing auto-approvals for user {user_id}: {e}")

        # Step 6: Expire old recommendations
        service = RecommendationService(db)
        expired_count = await service.expire_old_recommendations()

        logger.info(
            f"Recommendation generation complete: "
            f"{recommendations_created} created, {auto_applied} auto-applied, "
            f"{expired_count} expired, {errors} errors"
        )

        return {
            "products_checked": len(products_to_check),
            "recommendations_created": recommendations_created,
            "recommendations_expired": expired_count,
            "auto_applied": auto_applied,
            "errors": errors,
        }


async def _generate_recommendation_for_product(product_id: str, user_id: str):
    """
    Generate recommendation for a single product.

    Called manually or triggered by events like:
    - Competitor price change detected
    - Significant sentiment change
    - Manual user request
    """
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        # Get the product
        stmt = select(Product).where(Product.id == UUID(product_id))
        result = await db.execute(stmt)
        product = result.scalars().first()

        if not product:
            logger.error(f"Product not found: {product_id}")
            return {"error": "Product not found"}

        try:
            service = RecommendationService(db)
            recommendation = await service.generate_recommendation(product=product, user_id=UUID(user_id))

            if recommendation:
                logger.info(
                    f"Created recommendation for {product.name}: "
                    f"${product.current_price} -> ${recommendation.recommended_price}"
                )
                return {
                    "success": True,
                    "recommendation_id": str(recommendation.id),
                    "current_price": str(product.current_price),
                    "recommended_price": str(recommendation.recommended_price),
                    "change_percent": str(recommendation.change_percent),
                }
            else:
                return {
                    "success": True,
                    "recommendation_id": None,
                    "message": "No rule matched or no price change needed",
                }

        except Exception as e:
            logger.error(f"Error generating recommendation: {e}")
            return {"error": str(e)}


async def _check_competitor_prices():
    """
    Check for competitor price changes and trigger recommendations.

    Flow:
    1. Get all active competitor products
    2. Compare with our product prices
    3. Trigger recommendation generation for significant changes (>5%)
    """
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        # Get all active competitor products
        stmt = select(CompetitorProduct).where(CompetitorProduct.is_active)
        result = await db.execute(stmt)
        competitor_products = list(result.scalars().all())

        logger.info(f"Checking {len(competitor_products)} competitor products")

        # Batch load all related products in one query
        product_ids = {cp.product_id for cp in competitor_products if cp.product_id}
        if product_ids:
            products_result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
            products_map = {p.id: p for p in products_result.scalars().all()}
        else:
            products_map = {}

        significant_changes = 0

        for cp in competitor_products:
            if not cp.current_price or not cp.product_id:
                continue

            our_product = products_map.get(cp.product_id)

            if not our_product or not our_product.current_price:
                continue

            price_diff_pct = abs((cp.current_price - our_product.current_price) / our_product.current_price * 100)

            # Trigger recommendation for significant differences
            if price_diff_pct > 5:
                significant_changes += 1
                logger.info(
                    f"Significant price difference detected: "
                    f"{our_product.name} (${our_product.current_price}) vs "
                    f"competitor (${cp.current_price}) - {price_diff_pct:.1f}%"
                )

                # Queue recommendation generation
                generate_recommendation_for_product.delay(str(our_product.id), str(our_product.user_id))

        return {"competitor_products_checked": len(competitor_products), "significant_changes": significant_changes}


async def _expire_recommendations():
    """Expire old pending recommendations past their valid_until date."""
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        service = RecommendationService(db)
        expired_count = await service.expire_old_recommendations()

        logger.info(f"Expired {expired_count} old recommendations")

        return {"expired_count": expired_count}


async def _apply_stuck_recommendations():
    """
    Apply recommendations stuck in AUTO_APPROVED status.

    These are recommendations that passed auto-approval criteria but
    failed to push to the e-commerce platform for some reason.
    """
    session_maker = get_task_session_maker()

    async with session_maker() as db:
        # Find stuck recommendations
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.status == RecommendationStatus.AUTO_APPROVED)
            .where(PriceRecommendation.applied_at.is_(None))
        )
        result = await db.execute(stmt)
        stuck = list(result.scalars().all())

        logger.info(f"Found {len(stuck)} stuck AUTO_APPROVED recommendations")

        applied = 0
        failed = 0
        errors_detail = []

        for rec in stuck:
            try:
                approval_service = ApprovalService(db)
                await approval_service.apply_price(rec.id, rec.user_id)
                applied += 1
                logger.info(f"Applied stuck recommendation {rec.id}")
            except Exception as e:
                failed += 1
                errors_detail.append({"id": str(rec.id), "error": str(e)})
                logger.error(f"Failed to apply {rec.id}: {e}")

        return {
            "found": len(stuck),
            "applied": applied,
            "failed": failed,
            "errors": errors_detail[:10],  # Limit error details
        }


# ==============================================================================
# CELERY TASKS (Public API)
# ==============================================================================


@celery_app.task(name="workers.tasks.pricing_tasks.generate_all_recommendations")
def generate_all_recommendations():
    """
    Generate pricing recommendations for all products with active rules.

    Scheduled: Runs hourly
    """
    return run_async(_generate_all_recommendations())


@celery_app.task(name="workers.tasks.pricing_tasks.generate_recommendation_for_product")
def generate_recommendation_for_product(product_id: str, user_id: str):
    """
    Generate recommendation for a specific product.

    Triggered by: Competitor price changes, sentiment changes, manual request
    """
    return run_async(_generate_recommendation_for_product(product_id, user_id))


@celery_app.task(name="workers.tasks.pricing_tasks.check_competitor_prices")
def check_competitor_prices():
    """
    Check for competitor price changes and trigger recommendations.

    Scheduled: Runs every 30 minutes
    """
    return run_async(_check_competitor_prices())


@celery_app.task(name="workers.tasks.pricing_tasks.expire_recommendations")
def expire_recommendations():
    """
    Expire old pending recommendations.

    Scheduled: Runs daily
    """
    return run_async(_expire_recommendations())


@celery_app.task(name="workers.tasks.pricing_tasks.apply_stuck_recommendations")
def apply_stuck_recommendations():
    """
    Apply recommendations stuck in AUTO_APPROVED status.

    Use: Manual trigger or scheduled as recovery task
    """
    return run_async(_apply_stuck_recommendations())
