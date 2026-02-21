"""
Ingestion Tasks - Celery tasks for fetching and processing social mentions.

These tasks run on a schedule to:
1. Fetch social mentions for all products with keywords
2. Process unprocessed mentions through sentiment analysis

IMPORTANT: Each task creates its own database session to avoid event loop
conflicts when running in Celery's forked worker processes.

RATE LIMIT FIX (2026-01-11):
- Reduced batch_size from 100 to 50
- Added circuit breaker integration to skip rate-limited APIs
- Falls back to VADER-only when AI APIs unavailable
- Commits after EACH mention (survives task timeouts)
- Always marks mentions as processed (prevents infinite retry loops)
"""

import asyncio
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from workers.celery_app import celery_app
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def get_task_session_maker():
    """
    Create a fresh async session maker for Celery tasks.
    
    Uses NullPool to prevent connection reuse across forked processes,
    which would cause "Future attached to a different loop" errors.
    """
    # Convert postgresql:// to postgresql+asyncpg:// for async support
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Remove sslmode parameter - asyncpg doesn't support it as a query param
    # It needs to be passed via connect_args instead
    if "sslmode=" in db_url:
        db_url = re.sub(r'[\?&]sslmode=[^&]*', '', db_url)
        # Clean up any trailing ? or &&
        db_url = db_url.replace('?&', '?').replace('&&', '&').rstrip('?&')
    
    # Determine if SSL should be enabled based on host
    use_ssl = "neon.tech" in db_url or "railway" in db_url
    
    engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,  # Critical: No pooling in workers
        connect_args={"ssl": True} if use_ssl else {},
    )
    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def run_async(coro):
    """
    Helper to run async code in sync Celery task.
    
    Creates a fresh event loop for each task execution to avoid
    conflicts with asyncpg connections from other workers.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Properly clean up pending tasks before closing
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


@celery_app.task(bind=True, name="ingestion.fetch_all_mentions", track_started=True)
def fetch_all_mentions(self):
    """
    Fetch social mentions for ALL products with keywords.
    
    This is the scheduled task that runs every 30 minutes to queue
    individual fetch tasks for each product that has keywords configured.
    """
    return run_async(_fetch_all_mentions(self))


async def _fetch_all_mentions(task_self):
    """Async implementation of fetch all mentions."""
    from models.product import Product
    
    session_maker = get_task_session_maker()
    
    async with session_maker() as session:
        task_self.update_state(state="LOADING_PRODUCTS", meta={})
        
        # Get all active products that have keywords configured
        stmt = select(Product).where(
            Product.keywords != None,
            Product.is_active == True
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        if not products:
            logger.info("No products with keywords found for social mention fetching")
            return {
                "status": "success",
                "message": "No products with keywords configured",
                "products_queued": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        task_self.update_state(
            state="QUEUEING", 
            meta={"total_products": len(products)}
        )
        
        # Queue individual fetch tasks for each product
        queued_count = 0
        for product in products:
            try:
                fetch_for_product.delay(str(product.id))
                queued_count += 1
            except Exception as e:
                logger.error(f"Failed to queue fetch for product {product.id}: {e}")
        
        logger.info(f"Queued social mention fetching for {queued_count} products")
        
        return {
            "status": "success",
            "products_queued": queued_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@celery_app.task(bind=True, name="ingestion.fetch_for_product", track_started=True)
def fetch_for_product(self, product_id: str):
    """
    Fetch social mentions for a specific product using its keywords.
    
    This task is called either:
    - By fetch_all_mentions for scheduled fetching
    - Directly when a user manually triggers a fetch
    """
    return run_async(_fetch_for_product(self, product_id))


async def _fetch_for_product(task_self, product_id: str):
    """Async implementation for single product fetch."""
    from models.product import Product
    from models.social_mention import SocialMention
    from services.ingestion.reddit_service import get_reddit_collector
    
    session_maker = get_task_session_maker()
    
    async with session_maker() as session:
        task_self.update_state(state="LOADING_PRODUCT", meta={"product_id": product_id})
        
        # Get product and its keywords
        stmt = select(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
        
        if not product:
            logger.error(f"Product not found: {product_id}")
            return {"status": "error", "message": "Product not found"}
        
        keywords = product.keywords or [product.name]
        task_self.update_state(state="FETCHING", meta={"keywords": keywords})
        
        logger.info(f"Fetching mentions for product '{product.name}' with keywords: {keywords}")
        
        # Fetch from Reddit (mock mode for demo)
        collector = get_reddit_collector(mock_mode=True)
        collected = await collector.collect(keywords, limit=10)
        
        # Convert to SocialMention models
        mentions = []
        for item in collected:
            mention = SocialMention(
                user_id=product.user_id,
                product_id=product.id,
                source=item.source.value,
                source_id=item.source_id,
                content=item.content[:2000],
                author=item.author,
                author_followers=item.author_followers,
                engagement_count=item.engagement_count,
                url=item.url,
                collected_at=datetime.now(timezone.utc),
                published_at=item.published_at,
                language=item.language,
                raw_data=item.raw_data,
                processed=False,
            )
            mentions.append(mention)
        
        task_self.update_state(state="SAVING", meta={"count": len(mentions)})
        
        # Save new mentions to database
        saved_count = 0
        for mention in mentions:
            try:
                session.add(mention)
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save mention: {e}")
        
        if mentions:
            await session.commit()
        
        logger.info(f"Saved {saved_count} mentions for product '{product.name}'")
        
        return {
            "status": "success",
            "product_id": product_id,
            "product_name": product.name,
            "keywords_used": keywords,
            "mentions_fetched": len(mentions),
            "mentions_saved": saved_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# =============================================================================
# PROCESS PENDING MENTIONS - With Rate Limit Fix
# =============================================================================

@celery_app.task(
    bind=True,
    name="ingestion.process_pending_mentions",
    track_started=True,
    soft_time_limit=270,
    time_limit=300,
)
def process_pending_mentions(self, batch_size: int = 50):
    """
    Process unprocessed social mentions through sentiment analysis.
    
    This task runs every 5 minutes to:
    1. Fetch unprocessed mentions from the database
    2. Run sentiment analysis using VADER + OpenAI + Gemini (hybrid)
    3. Store the sentiment results
    
    RATE LIMIT FIX:
    - batch_size reduced from 100 to 50
    - Checks circuit breaker before AI API calls
    - Falls back to VADER-only when rate limited
    - Commits after EACH mention (survives task timeouts)
    - Always marks mentions as processed (no infinite loops)
    """
    return run_async(_process_pending_mentions(self, batch_size))


async def _process_pending_mentions(task_self, batch_size: int):
    """Async implementation of processing pending mentions."""
    from decimal import Decimal
    from models.social_mention import SocialMention
    from models.sentiment import Sentiment
    from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer, RateLimitError
    from services.rate_limit_manager import (
        get_rate_limit_manager,
        is_api_available,
        record_api_success,
        record_api_rate_limit,
    )
    
    session_maker = get_task_session_maker()
    rate_manager = get_rate_limit_manager()
    
    async with session_maker() as session:
        task_self.update_state(state="LOADING", meta={"batch_size": batch_size})
        
        # Get unprocessed mentions
        stmt = (
            select(SocialMention)
            .where(SocialMention.processed == False)
            .order_by(SocialMention.collected_at.asc())
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        mentions = result.scalars().all()
        
        if not mentions:
            logger.debug("No pending mentions to process")
            return {
                "status": "success",
                "message": "No pending mentions to process",
                "processed_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        logger.info(f"Processing {len(mentions)} pending mentions")
        task_self.update_state(state="PROCESSING", meta={"total": len(mentions)})
        
        # Check circuit breaker state BEFORE starting batch
        openai_available = is_api_available("openai")
        gemini_available = is_api_available("gemini")
        
        if not gemini_available:
            logger.warning("Gemini circuit OPEN - will use OpenAI or VADER")
        if not openai_available:
            logger.warning("OpenAI circuit OPEN - will use Gemini or VADER")
        if not gemini_available and not openai_available:
            logger.warning("Both AI circuits OPEN - using VADER-only for this batch")
        
        # Initialize hybrid analyzer
        analyzer = HybridSentimentAnalyzer()
        available_sources = analyzer.get_available_sources()
        logger.info(f"Sentiment analyzers available: {available_sources}")
        
        processed_count = 0
        degraded_count = 0  # Mentions processed without AI
        errors = []
        rate_limited_this_batch = False
        
        for i, mention in enumerate(mentions):
            try:
                task_self.update_state(
                    state="PROCESSING", 
                    meta={
                        "current": i + 1,
                        "total": len(mentions),
                        "degraded": degraded_count,
                    }
                )
                
                # Determine whether to use AI based on circuit state
                use_ai = (
                    not rate_limited_this_batch
                    and (gemini_available or openai_available)
                )
                
                try:
                    # Analyze sentiment
                    sentiment_result = await analyzer.analyze(mention.content, use_ai=use_ai)
                    
                    # Record success if AI was used
                    if "gemini" in sentiment_result.sources_used:
                        record_api_success("gemini")
                    if "openai" in sentiment_result.sources_used:
                        record_api_success("openai")
                        
                except RateLimitError as e:
                    # Rate limit hit - record it and disable AI for rest of batch
                    logger.warning(f"Rate limit hit: {e}")
                    rate_limited_this_batch = True
                    record_api_rate_limit(e.api_name, e.retry_after)
                    
                    # Retry this mention with VADER only
                    sentiment_result = await analyzer.analyze(mention.content, use_ai=False)
                    degraded_count += 1
                    
                except Exception as e:
                    # Check if it's a rate limit error in disguise
                    error_str = str(e).lower()
                    if "429" in str(e) or "rate" in error_str or "too many" in error_str:
                        rate_limited_this_batch = True
                        record_api_rate_limit("openai", 60)
                    
                    # Fall back to VADER only
                    logger.warning(f"AI analysis failed, using VADER: {e}")
                    sentiment_result = await analyzer.analyze(mention.content, use_ai=False)
                    degraded_count += 1
                
                # Check if this was a degraded analysis (no AI used)
                is_degraded = (
                    "gemini" not in sentiment_result.sources_used
                    and "openai" not in sentiment_result.sources_used
                )
                
                # Store sentiment in raw_data for aggregator to read
                raw_data = mention.raw_data or {}
                raw_data["sentiment"] = {
                    "compound": sentiment_result.compound,
                    "label": sentiment_result.label,
                    "confidence": sentiment_result.confidence,
                    "positive": sentiment_result.positive,
                    "negative": sentiment_result.negative,
                    "neutral": sentiment_result.neutral,
                    "sources_used": sentiment_result.sources_used,
                    "individual_scores": sentiment_result.individual_scores,
                    "emotions": sentiment_result.emotions,
                    "topics": sentiment_result.topics,
                    "is_sarcastic": sentiment_result.is_sarcastic,
                    "is_degraded": is_degraded,  # Track for monitoring
                }
                mention.raw_data = raw_data
                
                # Create Sentiment record for pricing rules to query
                sentiment_record = Sentiment(
                    product_id=mention.product_id,
                    source=mention.source,
                    raw_text=mention.content[:1000],  # Truncate for storage
                    compound_score=Decimal(str(round(sentiment_result.compound, 3))),
                    positive_score=Decimal(str(round(sentiment_result.positive, 3))),
                    negative_score=Decimal(str(round(sentiment_result.negative, 3))),
                    neutral_score=Decimal(str(round(sentiment_result.neutral, 3))),
                    author=mention.author,
                    url=mention.url,
                    analyzed_at=datetime.now(timezone.utc),
                )
                session.add(sentiment_record)
                
                # CRITICAL: Always mark as processed to prevent infinite retry
                mention.processed = True
                processed_count += 1
                
                # CRITICAL: Commit after EACH mention to survive task timeouts
                await session.commit()
                
                logger.debug(
                    f"Analyzed mention {mention.id}: "
                    f"score={sentiment_result.compound:.3f}, "
                    f"label={sentiment_result.label}, "
                    f"sources={sentiment_result.sources_used}"
                    f"{' (DEGRADED)' if is_degraded else ''}"
                )
                
            except Exception as e:
                logger.error(f"Error processing mention {mention.id}: {e}")
                errors.append({
                    "mention_id": str(mention.id),
                    "error": str(e)
                })
                
                # CRITICAL: Even on error, mark as processed to prevent infinite retry
                # These can be manually reprocessed later if needed
                try:
                    mention.processed = True
                    raw_data = mention.raw_data or {}
                    raw_data["sentiment_error"] = str(e)
                    mention.raw_data = raw_data
                    await session.commit()
                except Exception:
                    pass
        
        # Log summary with circuit breaker status
        circuit_status = rate_manager.get_all_status()
        logger.info(
            f"Processed {processed_count} mentions "
            f"({degraded_count} degraded/VADER-only), "
            f"{len(errors)} errors. "
            f"Circuits: {circuit_status}"
        )
        
        return {
            "status": "success",
            "processed_count": processed_count,
            "degraded_count": degraded_count,
            "error_count": len(errors),
            "analyzers_used": available_sources,
            "circuit_breakers": circuit_status,
            "errors": errors[:10],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    

    