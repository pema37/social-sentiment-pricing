# backend/workers/tasks/ingestion_tasks.py

import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlmodel import Session, select

from backend.workers.celery_app import celery_app
from backend.services.ingestion.reddit_service import get_reddit_collector
from backend.services.sentiment_analyzer import sentiment_analyzer
from backend.models.social_mention import SocialMention
from backend.models.product import Product
from backend.db.session import engine


def get_session():
    """Get a database session."""
    return Session(engine)


@celery_app.task(name="backend.workers.tasks.ingestion_tasks.fetch_social_mentions")
def fetch_social_mentions(
    user_id: str = None,
    keywords: List[str] = None,
    mock_mode: bool = True
):
    """
    Fetch social mentions from all configured sources.
    This runs on a schedule (every 30 minutes).
    """
    if keywords is None:
        keywords = ["product review", "just bought", "recommend"]
    
    async def _fetch():
        collector = get_reddit_collector(mock_mode=mock_mode)
        mentions = await collector.collect(keywords, limit=50)
        return mentions
    
    mentions = asyncio.run(_fetch())
    
    saved_count = 0
    skipped_count = 0
    
    if user_id:
        with get_session() as session:
            for mention in mentions:
                # Check if mention already exists (by source + source_id)
                existing = session.exec(
                    select(SocialMention).where(
                        SocialMention.source == mention.source.value,
                        SocialMention.source_id == mention.source_id
                    )
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create new mention
                db_mention = SocialMention(
                    user_id=UUID(user_id),
                    source=mention.source.value,
                    source_id=mention.source_id,
                    content=mention.content,
                    author=mention.author,
                    author_followers=mention.author_followers,
                    engagement_count=mention.engagement_count,
                    url=mention.url,
                    language=mention.language,
                    published_at=mention.published_at,
                    raw_data=mention.raw_data,
                    processed=False,
                )
                session.add(db_mention)
                saved_count += 1
            
            session.commit()
    
    print(f"[{datetime.now(timezone.utc)}] Fetched {len(mentions)}, saved {saved_count}, skipped {skipped_count}")
    
    return {
        "status": "success",
        "fetched_count": len(mentions),
        "saved_count": saved_count,
        "skipped_count": skipped_count,
        "keywords": keywords,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@celery_app.task(name="backend.workers.tasks.ingestion_tasks.process_pending_mentions")
def process_pending_mentions(limit: int = 100):
    """
    Process mentions that haven't been analyzed yet.
    Runs sentiment analysis and updates the database.
    """
    processed_count = 0
    
    with get_session() as session:
        # Get unprocessed mentions
        unprocessed = session.exec(
            select(SocialMention)
            .where(SocialMention.processed == False)
            .limit(limit)
        ).all()
        
        for mention in unprocessed:
            # Run sentiment analysis (prefer OpenAI, fallback to VADER)
            from backend.services.openai_sentiment import openai_sentiment_analyzer
            
            if openai_sentiment_analyzer.is_available():
                sentiment = openai_sentiment_analyzer.analyze(mention.content)
            else:
                sentiment = sentiment_analyzer.analyze(mention.content)
            
            # Update mention with sentiment data
            mention.processed = True
            # Create new dict to trigger SQLModel change detection
            new_raw_data = dict(mention.raw_data) if mention.raw_data else {}
            new_raw_data["sentiment"] = {
                "compound": float(sentiment["compound"]),
                "label": sentiment["label"],
                "positive": float(sentiment["positive"]),
                "negative": float(sentiment["negative"]),
                "neutral": float(sentiment["neutral"]),
            }
            mention.raw_data = new_raw_data
            
            session.add(mention)
            processed_count += 1
        
        session.commit()
    
    print(f"[{datetime.now(timezone.utc)}] Processed {processed_count} mentions")
    
    return {
        "status": "success",
        "processed_count": processed_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@celery_app.task(name="backend.workers.tasks.ingestion_tasks.fetch_for_product")
def fetch_for_product(
    product_id: str,
    user_id: str,
    keywords: List[str] = None,
    mock_mode: bool = True
):
    """
    Fetch social mentions for a specific product.
    Can be triggered manually via API.
    """
    # If no keywords provided, get them from the product
    if keywords is None:
        with get_session() as session:
            product = session.get(Product, UUID(product_id))
            if product:
                keywords = product.keywords or [product.name]
            else:
                return {"status": "error", "message": "Product not found"}
    
    async def _fetch():
        collector = get_reddit_collector(mock_mode=mock_mode)
        mentions = await collector.collect(keywords, limit=100)
        return mentions
    
    mentions = asyncio.run(_fetch())
    
    saved_count = 0
    with get_session() as session:
        for mention in mentions:
            # Check for duplicates
            existing = session.exec(
                select(SocialMention).where(
                    SocialMention.source == mention.source.value,
                    SocialMention.source_id == mention.source_id
                )
            ).first()
            
            if existing:
                continue
            
            db_mention = SocialMention(
                user_id=UUID(user_id),
                product_id=UUID(product_id),
                source=mention.source.value,
                source_id=mention.source_id,
                content=mention.content,
                author=mention.author,
                author_followers=mention.author_followers,
                engagement_count=mention.engagement_count,
                url=mention.url,
                language=mention.language,
                published_at=mention.published_at,
                raw_data=mention.raw_data,
                processed=False,
            )
            session.add(db_mention)
            saved_count += 1
        
        session.commit()
    
    return {
        "status": "success",
        "product_id": product_id,
        "fetched_count": len(mentions),
        "saved_count": saved_count,
        "keywords": keywords
    }


