# backend/workers/tasks/ingestion_tasks.py
"""
Ingestion Tasks - Celery tasks for fetching and processing social mentions.

These tasks run on a schedule to:
1. Fetch social mentions for all products with keywords
2. Process unprocessed mentions through sentiment analysis
"""

from datetime import datetime, timezone
from workers.celery_app import celery_app
from db.session import run_async, get_session_context
from core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="ingestion.fetch_all_mentions", track_started=True)
def fetch_all_mentions(self):
    """
    Fetch social mentions for ALL products with keywords.
    
    This is the scheduled task that runs every 30 minutes to queue
    individual fetch tasks for each product that has keywords configured.
    """
    from models import Product
    from sqlmodel import select
    
    async def _fetch_all():
        async with get_session_context() as session:
            self.update_state(state="LOADING_PRODUCTS", meta={})
            
            # Get all products that have keywords configured
            result = await session.execute(
                select(Product).where(
                    Product.keywords != None,
                    Product.is_active == True  # Only fetch for active products
                )
            )
            products = result.scalars().all()
            
            if not products:
                logger.info("No products with keywords found for social mention fetching")
                return {
                    "status": "success",
                    "message": "No products with keywords configured",
                    "products_queued": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            self.update_state(
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
    
    return run_async(_fetch_all())


@celery_app.task(bind=True, name="ingestion.fetch_for_product", track_started=True)
def fetch_for_product(self, product_id: str):
    """
    Fetch social mentions for a specific product using its keywords.
    
    This task is called either:
    - By fetch_all_mentions for scheduled fetching
    - Directly when a user manually triggers a fetch
    """
    from models import Product, SocialMention
    from sqlmodel import select
    
    async def _fetch():
        async with get_session_context() as session:
            self.update_state(state="LOADING_PRODUCT", meta={"product_id": product_id})
            
            # Get product and its keywords
            result = await session.execute(
                select(Product).where(Product.id == product_id)
            )
            product = result.scalar_one_or_none()
            
            if not product:
                logger.error(f"Product not found: {product_id}")
                return {"status": "error", "message": "Product not found"}
            
            keywords = product.keywords or [product.name]
            self.update_state(state="FETCHING", meta={"keywords": keywords})
            
            logger.info(f"Fetching mentions for product '{product.name}' with keywords: {keywords}")
            
            mentions = []
            
            # TODO: Import and use actual services when implemented
            # from services.ingestion.twitter_service import TwitterService
            # from services.ingestion.reddit_service import RedditService
            # 
            # twitter = TwitterService()
            # reddit = RedditService()
            # 
            # for keyword in keywords:
            #     twitter_mentions = await twitter.search(keyword, product_id=product.id)
            #     reddit_mentions = await reddit.search(keyword, product_id=product.id)
            #     mentions.extend(twitter_mentions)
            #     mentions.extend(reddit_mentions)
            
            self.update_state(state="SAVING", meta={"count": len(mentions)})
            
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
    
    return run_async(_fetch())


@celery_app.task(bind=True, name="ingestion.process_pending_mentions", track_started=True)
def process_pending_mentions(self, batch_size: int = 100):
    """
    Process unprocessed social mentions through sentiment analysis.
    
    This task runs every 5 minutes to:
    1. Fetch unprocessed mentions from the database
    2. Run sentiment analysis on each mention
    3. Store the sentiment results
    """
    from models import SocialMention
    from sqlmodel import select
    
    async def _process():
        async with get_session_context() as session:
            self.update_state(state="LOADING", meta={"batch_size": batch_size})
            
            # Get unprocessed mentions
            result = await session.execute(
                select(SocialMention)
                .where(SocialMention.processed == False)
                .order_by(SocialMention.created_at.asc())  # Process oldest first
                .limit(batch_size)
            )
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
            self.update_state(state="PROCESSING", meta={"total": len(mentions)})
            
            # TODO: Import actual analyzer when implemented
            # from services.analysis.sentiment_analyzer import SentimentAnalyzer
            # analyzer = SentimentAnalyzer()
            
            processed_count = 0
            errors = []
            
            for i, mention in enumerate(mentions):
                try:
                    self.update_state(
                        state="PROCESSING", 
                        meta={"current": i + 1, "total": len(mentions)}
                    )
                    
                    # TODO: Actual sentiment analysis
                    # sentiment_result = await analyzer.analyze(mention.content)
                    # 
                    # Create sentiment record
                    # sentiment = Sentiment(
                    #     mention_id=mention.id,
                    #     product_id=mention.product_id,
                    #     score=sentiment_result.score,
                    #     label=sentiment_result.label,
                    #     confidence=sentiment_result.confidence,
                    # )
                    # session.add(sentiment)
                    
                    # Mark mention as processed
                    mention.processed = True
                    mention.processed_at = datetime.now(timezone.utc)
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing mention {mention.id}: {e}")
                    errors.append({
                        "mention_id": str(mention.id),
                        "error": str(e)
                    })
            
            # Commit all changes
            await session.commit()
            
            logger.info(
                f"Processed {processed_count} mentions, {len(errors)} errors"
            )
            
            return {
                "status": "success",
                "processed_count": processed_count,
                "error_count": len(errors),
                "errors": errors[:10],  # Only return first 10 errors
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    return run_async(_process())

