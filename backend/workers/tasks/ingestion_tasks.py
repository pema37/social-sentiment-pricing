# backend/workers/tasks/ingestion_tasks.py

from datetime import datetime, timezone
from workers.celery_app import celery_app

from db.session import run_async, get_session_context


@celery_app.task(bind=True, name="ingestion.fetch_for_product", track_started=True)
def fetch_for_product(self, product_id: str):
    """Fetch social mentions for a specific product using its keywords."""
    from models import Product
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
                return {"status": "error", "message": "Product not found"}
            
            keywords = product.keywords or [product.name]
            self.update_state(state="FETCHING", meta={"keywords": keywords})
            
            mentions = []
            
            # TODO: Import and use actual services
            # from services.ingestion.twitter_service import TwitterService
            # from services.ingestion.reddit_service import RedditService
            
            self.update_state(state="SAVING", meta={"count": len(mentions)})
            
            for mention in mentions:
                session.add(mention)
            
            return {
                "status": "success",
                "product_id": product_id,
                "product_name": product.name,
                "mentions_fetched": len(mentions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    return run_async(_fetch())


@celery_app.task(bind=True, name="ingestion.process_pending_mentions", track_started=True)
def process_pending_mentions(self, batch_size: int = 100):
    """Process unprocessed social mentions through sentiment analysis."""
    from models import SocialMention, Sentiment
    from sqlmodel import select
    
    async def _process():
        async with get_session_context() as session:
            self.update_state(state="LOADING", meta={"batch_size": batch_size})
            
            # Get unprocessed mentions
            result = await session.execute(
                select(SocialMention)
                .where(SocialMention.processed == False)
                .limit(batch_size)
            )
            mentions = result.scalars().all()
            
            if not mentions:
                return {
                    "status": "success",
                    "message": "No pending mentions to process",
                    "processed_count": 0
                }
            
            self.update_state(state="PROCESSING", meta={"total": len(mentions)})
            
            # TODO: Import actual analyzer
            # from services.analysis.sentiment_analyzer import SentimentAnalyzer
            # analyzer = SentimentAnalyzer()
            
            processed_count = 0
            errors = []
            
            for mention in mentions:
                try:
                    # TODO: Actual sentiment analysis
                    # sentiment_result = await analyzer.analyze(mention.content)
                    
                    mention.processed = True
                    processed_count += 1
                    
                except Exception as e:
                    errors.append({"mention_id": str(mention.id), "error": str(e)})
            
            return {
                "status": "success",
                "processed_count": processed_count,
                "error_count": len(errors),
                "errors": errors[:10],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    return run_async(_process())
