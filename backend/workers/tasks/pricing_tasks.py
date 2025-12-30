# backend/workers/tasks/pricing_tasks.py
"""
Pricing Tasks - Celery tasks for generating price recommendations.

These tasks run on a schedule to:
1. Generate recommendations for all products with active rules
2. Expire old recommendations
3. Check competitor prices and trigger alerts
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlmodel import select

from workers.celery_app import celery_app
from db.session import get_session_context
from models.product import Product
from models.pricing_rule import PricingRule
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.competitor_product import CompetitorProduct
from services.pricing.recommendation_service import RecommendationService
from core.logging import get_logger

logger = get_logger(__name__)


def run_async(coro):
    """Helper to run async code in sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="workers.tasks.pricing_tasks.generate_all_recommendations")
def generate_all_recommendations():
    """
    Generate pricing recommendations for all products with active rules.
    
    This is the main scheduled task that runs hourly to check all products
    and generate recommendations based on current market signals.
    """
    return run_async(_generate_all_recommendations())


async def _generate_all_recommendations():
    """Async implementation of recommendation generation."""
    
    async with get_session_context() as db:
        # Get product IDs that have active pricing rules (avoid DISTINCT on JSON columns)
        subquery = (
            select(PricingRule.product_id)
            .where(PricingRule.is_active == True)
            .distinct()
            .subquery()
        )
        
        stmt = (
            select(Product)
            .where(Product.id.in_(select(subquery.c.product_id)))
        )
        
        result = await db.execute(stmt)
        products = list(result.scalars().all())
        
        logger.info(f"Checking {len(products)} products for recommendations")
        
        recommendations_created = 0
        errors = 0
        
        for product in products:
            try:
                service = RecommendationService(db)
                recommendation = await service.generate_recommendation(
                    product=product,
                    user_id=product.user_id
                )
                
                if recommendation:
                    recommendations_created += 1
                    logger.info(
                        f"Created recommendation for {product.name}: "
                        f"${product.current_price} -> ${recommendation.recommended_price}"
                    )
            except Exception as e:
                errors += 1
                logger.error(f"Error generating recommendation for product {product.id}: {e}")
        
        # Also expire old recommendations
        service = RecommendationService(db)
        expired_count = await service.expire_old_recommendations()
        
        logger.info(
            f"Recommendation generation complete: "
            f"{recommendations_created} created, {expired_count} expired, {errors} errors"
        )
        
        return {
            "products_checked": len(products),
            "recommendations_created": recommendations_created,
            "recommendations_expired": expired_count,
            "errors": errors
        }
    

@celery_app.task(name="workers.tasks.pricing_tasks.generate_recommendation_for_product")
def generate_recommendation_for_product(product_id: str, user_id: str):
    """
    Generate recommendation for a specific product.
    
    This can be called manually or triggered by events like:
    - Competitor price change detected
    - Significant sentiment change
    - Manual user request
    """
    return run_async(_generate_recommendation_for_product(product_id, user_id))


async def _generate_recommendation_for_product(product_id: str, user_id: str):
    """Async implementation for single product recommendation."""
    
    async with get_session_context() as db:
        # Get the product
        stmt = select(Product).where(Product.id == UUID(product_id))
        result = await db.execute(stmt)
        product = result.scalars().first()
        
        if not product:
            logger.error(f"Product not found: {product_id}")
            return {"error": "Product not found"}
        
        try:
            service = RecommendationService(db)
            recommendation = await service.generate_recommendation(
                product=product,
                user_id=UUID(user_id)
            )
            
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
                    "change_percent": str(recommendation.change_percent)
                }
            else:
                return {
                    "success": True,
                    "recommendation_id": None,
                    "message": "No rule matched or no price change needed"
                }
                
        except Exception as e:
            logger.error(f"Error generating recommendation: {e}")
            return {"error": str(e)}


@celery_app.task(name="workers.tasks.pricing_tasks.check_competitor_prices")
def check_competitor_prices():
    """
    Check for competitor price changes and trigger recommendations.
    
    This task:
    1. Fetches current competitor prices
    2. Compares with stored prices
    3. Triggers recommendation generation for significant changes
    """
    return run_async(_check_competitor_prices())


async def _check_competitor_prices():
    """Async implementation of competitor price checking."""
    
    async with get_session_context() as db:
        # Get all active competitor products
        stmt = select(CompetitorProduct).where(CompetitorProduct.is_active == True)
        result = await db.execute(stmt)
        competitor_products = list(result.scalars().all())
        
        logger.info(f"Checking {len(competitor_products)} competitor products")
        
        significant_changes = 0
        
        for cp in competitor_products:
            # Check if price has changed significantly (>5%)
            if cp.current_price and cp.product_id:
                # Get our product
                product_stmt = select(Product).where(Product.id == cp.product_id)
                result = await db.execute(product_stmt)
                our_product = result.scalars().first()
                
                if our_product and our_product.current_price:
                    price_diff_pct = abs(
                        (cp.current_price - our_product.current_price) 
                        / our_product.current_price * 100
                    )
                    
                    # If competitor is significantly different, trigger recommendation
                    if price_diff_pct > 5:
                        significant_changes += 1
                        logger.info(
                            f"Significant price difference detected: "
                            f"{our_product.name} (${our_product.current_price}) vs "
                            f"competitor (${cp.current_price}) - {price_diff_pct:.1f}%"
                        )
                        
                        # Trigger recommendation generation
                        generate_recommendation_for_product.delay(
                            str(our_product.id),
                            str(our_product.user_id)
                        )
        
        return {
            "competitor_products_checked": len(competitor_products),
            "significant_changes": significant_changes
        }


@celery_app.task(name="workers.tasks.pricing_tasks.expire_recommendations")
def expire_recommendations():
    """Expire old pending recommendations."""
    return run_async(_expire_recommendations())


async def _expire_recommendations():
    """Async implementation of recommendation expiration."""
    
    async with get_session_context() as db:
        service = RecommendationService(db)
        expired_count = await service.expire_old_recommendations()
        
        logger.info(f"Expired {expired_count} old recommendations")
        
        return {"expired_count": expired_count}
    

