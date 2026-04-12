"""
FILE: backend/workers/tasks/ingestion_tasks.py
SURGICAL PATCH — only the task decorators and run_async changed.

What changed vs original:
  - fetch_all_mentions:       added queue="sentiment"
  - fetch_for_product:        added queue="sentiment"
  - process_pending_mentions: added queue="sentiment"
  - run_async:                uses persistent event loop from worker_process_init
                              signal (set in celery_app.py) instead of creating
                              and destroying a new loop on every task call.
                              New loop per call breaks httpx/aiohttp connection
                              pool reuse and adds GC overhead.

Why queue isolation: isolates ingestion work to its own Celery queue so a
Reddit spike / Gemini quota burst can never block a merchant's product sync.

All other code (get_task_session_maker, all async implementations) is
100% identical to the original file.
"""

import asyncio
import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from core.config import settings
from core.logging import get_logger
from workers.celery_app import celery_app

logger = get_logger(__name__)


def get_task_session_maker():
    """
    Create a fresh async session maker for Celery tasks.

    Uses NullPool to prevent connection reuse across forked processes,
    which would cause "Future attached to a different loop" errors.
    """
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = re.sub(r"[\?&]sslmode=[^&]*", "", db_url)
        db_url = db_url.replace("?&", "?").replace("&&", "&").rstrip("?&")

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
    Run an async coroutine in the worker's persistent event loop.

    The loop is created once per prefork worker process via the
    worker_process_init signal in celery_app.py. Reusing the same loop
    across task calls allows httpx/aiohttp connection pools to survive
    between tasks (keepalive, pool reuse) and avoids GC churn from
    creating and closing a loop on every task execution.

    Thread-safety: each prefork worker process is memory-isolated,
    so there is no shared state between workers.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# =============================================================================
# FETCH ALL MENTIONS
# =============================================================================

@celery_app.task(
    bind=True,
    name="ingestion.fetch_all_mentions",
    track_started=True,
    queue="sentiment",
)
def fetch_all_mentions(self):
    """
    Fetch social mentions for ALL products with keywords.
    Runs every 30 minutes on the sentiment queue.
    """
    return run_async(_fetch_all_mentions(self))


async def _fetch_all_mentions(task_self):
    from models.product import Product

    session_maker = get_task_session_maker()

    async with session_maker() as session:
        task_self.update_state(state="LOADING_PRODUCTS", meta={})

        stmt = select(Product).where(Product.keywords.is_not(None), Product.is_active)
        result = await session.execute(stmt)
        products = result.scalars().all()

        if not products:
            logger.info("No products with keywords found for social mention fetching")
            return {
                "status": "success",
                "message": "No products with keywords configured",
                "products_queued": 0,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        task_self.update_state(state="QUEUEING", meta={"total_products": len(products)})

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
            "timestamp": datetime.now(UTC).isoformat(),
        }


# =============================================================================
# FETCH FOR PRODUCT
# =============================================================================

@celery_app.task(
    bind=True,
    name="ingestion.fetch_for_product",
    track_started=True,
    queue="sentiment",
)
def fetch_for_product(self, product_id: str):
    """
    Fetch social mentions for a specific product using its keywords.
    """
    return run_async(_fetch_for_product(self, product_id))


async def _fetch_for_product(task_self, product_id: str):
    from models.product import Product
    from models.social_mention import SocialMention
    from services.ingestion.reddit_service import get_reddit_collector

    session_maker = get_task_session_maker()

    async with session_maker() as session:
        task_self.update_state(state="LOADING_PRODUCT", meta={"product_id": product_id})

        stmt = select(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            logger.error(f"Product not found: {product_id}")
            return {"status": "error", "message": "Product not found"}

        keywords = product.keywords or [product.name]
        task_self.update_state(state="FETCHING", meta={"keywords": keywords})

        logger.info(f"Fetching mentions for product '{product.name}' with keywords: {keywords}")

        collector = get_reddit_collector(mock_mode=True)
        collected = await collector.collect(keywords, limit=10)

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
                collected_at=datetime.now(UTC),
                published_at=item.published_at,
                language=item.language,
                raw_data=item.raw_data,
                processed=False,
            )
            mentions.append(mention)

        task_self.update_state(state="SAVING", meta={"count": len(mentions)})

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
            "timestamp": datetime.now(UTC).isoformat(),
        }


# =============================================================================
# PROCESS PENDING MENTIONS
# =============================================================================

@celery_app.task(
    bind=True,
    name="ingestion.process_pending_mentions",
    track_started=True,
    soft_time_limit=270,
    time_limit=300,
    queue="sentiment",
)
def process_pending_mentions(self, batch_size: int = 50, user_id: str | None = None):
    """
    Process unprocessed social mentions through sentiment analysis.
    Runs every 5 minutes on the sentiment queue.

    Args:
        batch_size: Number of mentions to process per batch.
        user_id: If provided, only process mentions belonging to this user.
    """
    return run_async(_process_pending_mentions(self, batch_size, user_id=user_id))


async def _process_pending_mentions(task_self, batch_size: int, user_id: str | None = None):
    from decimal import Decimal
    from uuid import UUID

    from models.sentiment import Sentiment
    from models.social_mention import SocialMention
    from services.hybrid_sentiment_analyzer import HybridSentimentAnalyzer, RateLimitError
    from services.rate_limit_manager import (
        get_rate_limit_manager,
        is_api_available,
        record_api_rate_limit,
        record_api_success,
    )

    session_maker = get_task_session_maker()
    rate_manager = get_rate_limit_manager()

    async with session_maker() as session:
        task_self.update_state(state="LOADING", meta={"batch_size": batch_size})

        stmt = select(SocialMention).where(SocialMention.processed.is_(False))
        if user_id:
            stmt = stmt.where(SocialMention.user_id == UUID(user_id))
        stmt = stmt.order_by(SocialMention.collected_at.asc()).limit(batch_size)
        result = await session.execute(stmt)
        mentions = result.scalars().all()

        if not mentions:
            logger.debug("No pending mentions to process")
            return {
                "status": "success",
                "message": "No pending mentions to process",
                "processed_count": 0,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        logger.info(f"Processing {len(mentions)} pending mentions")
        task_self.update_state(state="PROCESSING", meta={"total": len(mentions)})

        openai_available = is_api_available("openai")
        gemini_available = is_api_available("gemini")

        if not gemini_available:
            logger.warning("Gemini circuit OPEN - will use OpenAI or VADER")
        if not openai_available:
            logger.warning("OpenAI circuit OPEN - will use Gemini or VADER")
        if not gemini_available and not openai_available:
            logger.warning("Both AI circuits OPEN - using VADER-only for this batch")

        analyzer = HybridSentimentAnalyzer()
        available_sources = analyzer.get_available_sources()
        logger.info(f"Sentiment analyzers available: {available_sources}")

        processed_count = 0
        degraded_count = 0
        errors = []
        rate_limited_this_batch = False

        for i, mention in enumerate(mentions):
            try:
                task_self.update_state(
                    state="PROCESSING",
                    meta={"current": i + 1, "total": len(mentions), "degraded": degraded_count},
                )

                use_ai = not rate_limited_this_batch and (gemini_available or openai_available)

                try:
                    sentiment_result = await analyzer.analyze(mention.content, use_ai=use_ai)

                    if "gemini" in sentiment_result.sources_used:
                        record_api_success("gemini")
                    if "openai" in sentiment_result.sources_used:
                        record_api_success("openai")

                except RateLimitError as e:
                    logger.warning(f"Rate limit hit: {e}")
                    rate_limited_this_batch = True
                    record_api_rate_limit(e.api_name, e.retry_after)
                    sentiment_result = await analyzer.analyze(mention.content, use_ai=False)
                    degraded_count += 1

                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in str(e) or "rate" in error_str or "too many" in error_str:
                        rate_limited_this_batch = True
                        record_api_rate_limit("openai", 60)
                    logger.warning(f"AI analysis failed, using VADER: {e}")
                    sentiment_result = await analyzer.analyze(mention.content, use_ai=False)
                    degraded_count += 1

                is_degraded = (
                    "gemini" not in sentiment_result.sources_used
                    and "openai" not in sentiment_result.sources_used
                )

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
                    "is_degraded": is_degraded,
                }
                mention.raw_data = raw_data

                sentiment_record = Sentiment(
                    product_id=mention.product_id,
                    source=mention.source,
                    raw_text=mention.content[:1000],
                    compound_score=Decimal(str(round(sentiment_result.compound, 3))),
                    positive_score=Decimal(str(round(sentiment_result.positive, 3))),
                    negative_score=Decimal(str(round(sentiment_result.negative, 3))),
                    neutral_score=Decimal(str(round(sentiment_result.neutral, 3))),
                    author=mention.author,
                    url=mention.url,
                    analyzed_at=datetime.now(UTC),
                )
                session.add(sentiment_record)

                mention.processed = True
                processed_count += 1

                # Commit after each mention to survive task timeouts
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
                errors.append({"mention_id": str(mention.id), "error": str(e)})

                try:
                    mention.processed = True
                    raw_data = mention.raw_data or {}
                    raw_data["sentiment_error"] = str(e)
                    mention.raw_data = raw_data
                    await session.commit()
                except Exception:
                    pass

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
            "timestamp": datetime.now(UTC).isoformat(),
        }
    



    