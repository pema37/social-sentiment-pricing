#!/usr/bin/env python3
"""
Seed Mock Sentiment Data for SSP (Social Sentiment Pricing)

This script populates the database with realistic mock sentiment data
for demos and testing. It creates:
- Social mentions from various platforms (Reddit, Twitter, TikTok, News)
- Analyzed sentiment records linked to products

Usage:
    python backend/scripts/seed_sentiment_data.py [--user-email EMAIL] [--days DAYS] [--mentions-per-day N]
    
Example:
    python backend/scripts/seed_sentiment_data.py --user-email demo@example.com --days 30 --mentions-per-day 15
"""

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from db.session import engine
from models.user import User
from models.product import Product
from models.social_mention import SocialMention
from models.sentiment import Sentiment


# =============================================================================
# MOCK DATA TEMPLATES
# =============================================================================

SOURCES = ["reddit", "twitter", "tiktok", "news"]

# Weighted sentiment distribution: 45% positive, 35% neutral, 20% negative
SENTIMENT_WEIGHTS = {
    "positive": 0.45,
    "neutral": 0.35,
    "negative": 0.20,
}

# Reddit-style content templates
REDDIT_TEMPLATES = {
    "positive": [
        "Just got my {product} and I'm blown away! Best purchase I've made this year 🔥",
        "Been using {product} for a week now. Totally worth every penny!",
        "PSA: {product} is on sale and it's absolutely incredible quality",
        "Upgraded to {product} from my old one. Night and day difference!",
        "My {product} arrived today. The build quality is insane for the price",
        "3 months with {product} - still loving it. AMA",
        "Finally pulled the trigger on {product}. No regrets whatsoever",
        "{product} exceeded all my expectations. Highly recommend!",
        "Wife surprised me with {product}. She's a keeper and so is this product!",
        "Return window closed on my {product} but I wouldn't send it back anyway",
    ],
    "neutral": [
        "Anyone else have {product}? Looking for tips and tricks",
        "Thinking about getting {product}. Is it worth the price?",
        "{product} vs competitors - which would you choose?",
        "Question about {product} warranty - anyone dealt with support?",
        "How long does {product} usually last? Planning a purchase",
        "{product} restocked at major retailers FYI",
        "Comparison thread: {product} features breakdown",
        "Is {product} good for beginners or more advanced users?",
        "Looking at {product} specs - seems decent for the category",
        "Weekly {product} discussion thread",
    ],
    "negative": [
        "Disappointed with {product}. Expected better for the price",
        "{product} broke after 2 months. Quality control issues?",
        "Returning my {product} tomorrow. Not what I expected",
        "Anyone else having issues with {product}? Mine keeps malfunctioning",
        "Overpriced IMO. {product} doesn't justify the cost",
        "Warning: {product} customer service is terrible",
        "{product} quality has gone downhill lately",
        "Bought {product} based on reviews but it's underwhelming",
        "Save your money - {product} isn't worth it",
        "Had to replace my {product} twice already. Frustrating",
    ],
}

# Twitter-style content (shorter)
TWITTER_TEMPLATES = {
    "positive": [
        "obsessed with my new {product} 😍",
        "{product} is a game changer fr",
        "best money I ever spent → {product}",
        "the {product} hype is real y'all",
        "{product} supremacy 🙌",
        "lowkey {product} changed my life",
        "if you don't have {product} what are you even doing",
        "{product} worth every single penny",
        "finally got {product} and WOW",
        "10/10 would recommend {product}",
    ],
    "neutral": [
        "thinking about getting {product} 🤔",
        "anyone tried {product}?",
        "{product} opinions? need help deciding",
        "saw {product} at the store today",
        "{product} or save my money...",
        "how's the {product} holding up for everyone?",
        "{product} back in stock btw",
        "comparing {product} options rn",
        "research mode: {product} edition",
        "{product} release date when?",
    ],
    "negative": [
        "{product} ain't it chief 😬",
        "disappointed with {product} ngl",
        "returning my {product} asap",
        "{product} was a waste of money",
        "overhyped: {product}",
        "my {product} already broke lmao",
        "save your coins, skip {product}",
        "{product} quality is trash now",
        "regret buying {product}",
        "{product} fell off hard",
    ],
}

# TikTok-style content
TIKTOK_TEMPLATES = {
    "positive": [
        "POV: you finally got the {product} everyone's been talking about ✨",
        "This {product} is giving everything it was supposed to give 💅",
        "The way {product} changed my whole routine... iconic behavior",
        "No bc why is {product} actually so good??",
        "Run don't walk to get {product} besties",
        "{product} review: it's giving 10/10",
        "Things I bought that were actually worth it: {product}",
        "The {product} girlies are winning rn",
        "Unboxing my {product} and I'm literally screaming",
        "{product} haul and everything is SO good",
    ],
    "neutral": [
        "Should I get {product}? Comment below 👇",
        "{product} honest review - no filter",
        "Testing if {product} lives up to the hype",
        "Day 1 of trying {product}",
        "{product} first impressions...",
        "Is {product} worth it in 2024?",
        "{product} vs dupe - which is better?",
        "Replying to @user about {product}",
        "{product} pros and cons breakdown",
        "POV: researching {product} at 3am",
    ],
    "negative": [
        "The {product} flop era has begun 💀",
        "Not me falling for the {product} marketing...",
        "{product} is NOT worth the hype. Here's why",
        "POV: your {product} broke on day one",
        "Things TikTok made me buy that I regret: {product}",
        "The {product} girlies are NOT gonna like this review",
        "Returning {product} - it's giving scam",
        "Why does my {product} look nothing like the ads??",
        "{product} honest review: save your money bestie",
        "The way I got finessed by {product} 🤡",
    ],
}

# News-style content
NEWS_TEMPLATES = {
    "positive": [
        "{product} sees surge in positive consumer reviews amid market growth",
        "Industry analysts praise {product} innovation and value proposition",
        "{product} leads category in customer satisfaction surveys",
        "Record sales reported for {product} as demand continues to climb",
        "{product} receives Editor's Choice award from leading publication",
        "Consumer Reports rates {product} highly in latest roundup",
        "{product} brand trust scores reach all-time high",
        "Market analysis: {product} positioned for continued success",
        "{product} sustainability initiatives earn consumer praise",
        "Expert review: {product} sets new standard in category",
    ],
    "neutral": [
        "{product} announces updated pricing structure for Q4",
        "Market analysis: {product} maintains steady market position",
        "{product} releases quarterly performance metrics",
        "Industry report examines {product} market share trends",
        "{product} supply chain updates amid global logistics shifts",
        "Retailers report stable {product} inventory levels",
        "{product} competitive landscape analysis published",
        "Consumer spending patterns for {product} category examined",
        "{product} feature comparison guide released",
        "Analysts provide {product} market outlook for coming quarter",
    ],
    "negative": [
        "{product} faces criticism over recent quality concerns",
        "Consumer complaints rise for {product} amid service issues",
        "{product} recalls announced following safety reports",
        "Market share decline noted for {product} in latest analysis",
        "{product} pricing controversy sparks consumer backlash",
        "Industry watchdog investigates {product} claims",
        "{product} customer service ratings drop in annual survey",
        "Analyst downgrades {product} outlook citing competition",
        "{product} faces regulatory scrutiny over marketing practices",
        "Consumer advocacy group raises concerns about {product}",
    ],
}

TEMPLATES_BY_SOURCE = {
    "reddit": REDDIT_TEMPLATES,
    "twitter": TWITTER_TEMPLATES,
    "tiktok": TIKTOK_TEMPLATES,
    "news": NEWS_TEMPLATES,
}

# Author name generators
REDDIT_AUTHORS = [
    "ThrowawayUser{n}", "ProductEnthusiast{n}", "BargainHunter{n}",
    "TechReviewer{n}", "RandomBuyer{n}", "CasualConsumer{n}",
    "DealSeeker{n}", "QualityMatters{n}", "ValueShopper{n}",
    "SmartPurchaser{n}", "ReviewKing{n}", "HonestOpinion{n}",
]

TWITTER_AUTHORS = [
    "@user{n}", "@shopper{n}", "@reviewer{n}", "@deals{n}",
    "@lifestyle{n}", "@trending{n}", "@vibes{n}", "@thoughts{n}",
]

TIKTOK_AUTHORS = [
    "@tiktokuser{n}", "@reviewqueen{n}", "@haultime{n}",
    "@producttest{n}", "@dailyfinds{n}", "@shopwithme{n}",
]

NEWS_AUTHORS = [
    "MarketWatch Staff", "Consumer Reports", "Reuters",
    "Industry Insider", "Tech Analysis Weekly", "Market Pulse",
    "Consumer Trends Daily", "Retail Observer", "Business Wire",
]


# =============================================================================
# SENTIMENT SCORE GENERATION
# =============================================================================

def generate_sentiment_scores(sentiment_type: str) -> dict:
    """
    Generate realistic VADER-style sentiment scores.
    
    Returns dict with: compound, positive, negative, neutral scores
    All scores are Decimal with 3 decimal places.
    """
    if sentiment_type == "positive":
        compound = Decimal(str(round(random.uniform(0.3, 0.95), 3)))
        positive = Decimal(str(round(random.uniform(0.4, 0.8), 3)))
        negative = Decimal(str(round(random.uniform(0.0, 0.15), 3)))
    elif sentiment_type == "negative":
        compound = Decimal(str(round(random.uniform(-0.95, -0.3), 3)))
        positive = Decimal(str(round(random.uniform(0.0, 0.15), 3)))
        negative = Decimal(str(round(random.uniform(0.4, 0.8), 3)))
    else:  # neutral
        compound = Decimal(str(round(random.uniform(-0.25, 0.25), 3)))
        positive = Decimal(str(round(random.uniform(0.1, 0.35), 3)))
        negative = Decimal(str(round(random.uniform(0.1, 0.35), 3)))
    
    # Neutral score fills the remainder (roughly)
    neutral = Decimal(str(round(max(0, 1 - float(positive) - float(negative)), 3)))
    
    return {
        "compound_score": compound,
        "positive_score": positive,
        "negative_score": negative,
        "neutral_score": neutral,
    }


def pick_sentiment_type() -> str:
    """Pick a sentiment type based on weighted distribution."""
    r = random.random()
    if r < SENTIMENT_WEIGHTS["positive"]:
        return "positive"
    elif r < SENTIMENT_WEIGHTS["positive"] + SENTIMENT_WEIGHTS["neutral"]:
        return "neutral"
    else:
        return "negative"


# =============================================================================
# MENTION GENERATION
# =============================================================================

def generate_author(source: str) -> tuple[str, Optional[int]]:
    """Generate author name and follower count for a source."""
    n = random.randint(100, 99999)
    
    if source == "reddit":
        author = random.choice(REDDIT_AUTHORS).format(n=n)
        followers = None  # Reddit doesn't show followers prominently
    elif source == "twitter":
        author = random.choice(TWITTER_AUTHORS).format(n=n)
        followers = random.choice([
            random.randint(50, 500),      # Small account
            random.randint(500, 5000),    # Medium account
            random.randint(5000, 50000),  # Large account
            random.randint(50000, 500000), # Very large
        ])
    elif source == "tiktok":
        author = random.choice(TIKTOK_AUTHORS).format(n=n)
        followers = random.choice([
            random.randint(100, 1000),
            random.randint(1000, 10000),
            random.randint(10000, 100000),
            random.randint(100000, 1000000),
        ])
    else:  # news
        author = random.choice(NEWS_AUTHORS)
        followers = None
    
    return author, followers


def generate_engagement(source: str, sentiment_type: str) -> int:
    """Generate engagement count based on source and sentiment."""
    # Controversial/negative content sometimes gets more engagement
    multiplier = 1.0
    if sentiment_type == "negative":
        multiplier = random.uniform(1.0, 1.5)
    elif sentiment_type == "positive":
        multiplier = random.uniform(0.8, 1.3)
    
    if source == "reddit":
        base = random.choice([
            random.randint(1, 50),
            random.randint(50, 500),
            random.randint(500, 5000),
        ])
    elif source == "twitter":
        base = random.choice([
            random.randint(0, 20),
            random.randint(20, 200),
            random.randint(200, 2000),
        ])
    elif source == "tiktok":
        base = random.choice([
            random.randint(100, 1000),
            random.randint(1000, 10000),
            random.randint(10000, 100000),
        ])
    else:  # news
        base = random.randint(0, 100)
    
    return int(base * multiplier)


def generate_url(source: str, source_id: str) -> str:
    """Generate a realistic-looking URL for the mention."""
    if source == "reddit":
        subreddit = random.choice(["products", "BuyItForLife", "deals", "reviews", "gadgets"])
        return f"https://reddit.com/r/{subreddit}/comments/{source_id}"
    elif source == "twitter":
        return f"https://twitter.com/user/status/{source_id}"
    elif source == "tiktok":
        return f"https://tiktok.com/@user/video/{source_id}"
    else:  # news
        domain = random.choice(["marketwatch.com", "reuters.com", "consumerreports.org"])
        return f"https://{domain}/article/{source_id}"


def create_mention_and_sentiment(
    session: Session,
    user_id: uuid.UUID,
    product: Product,
    published_at: datetime,
) -> tuple[SocialMention, Sentiment]:
    """Create a social mention and its corresponding sentiment record."""
    
    source = random.choice(SOURCES)
    sentiment_type = pick_sentiment_type()
    
    # Get content template
    templates = TEMPLATES_BY_SOURCE[source][sentiment_type]
    content = random.choice(templates).format(product=product.name)
    
    # Generate metadata
    author, author_followers = generate_author(source)
    engagement = generate_engagement(source, sentiment_type)
    source_id = str(random.randint(1000000000, 9999999999))
    url = generate_url(source, source_id)
    
    # Create social mention
    mention = SocialMention(
        id=uuid.uuid4(),
        user_id=user_id,
        product_id=product.id,
        source=source,
        source_id=source_id,
        content=content,
        author=author,
        author_followers=author_followers,
        engagement_count=engagement,
        url=url,
        language="en",
        published_at=published_at,
        processed=True,  # Mark as processed since we're also creating sentiment
        collected_at=published_at + timedelta(minutes=random.randint(5, 60)),
    )
    
    # Generate sentiment scores
    scores = generate_sentiment_scores(sentiment_type)
    
    # Create sentiment record
    sentiment = Sentiment(
        id=uuid.uuid4(),
        product_id=product.id,
        source=source,
        raw_text=content,
        compound_score=scores["compound_score"],
        positive_score=scores["positive_score"],
        negative_score=scores["negative_score"],
        neutral_score=scores["neutral_score"],
        author=author,
        url=url,
        analyzed_at=mention.collected_at + timedelta(seconds=random.randint(1, 30)),
    )
    
    return mention, sentiment


# =============================================================================
# MAIN SEEDING LOGIC
# =============================================================================

def seed_sentiment_data(
    user_email: Optional[str] = None,
    days: int = 30,
    mentions_per_day: int = 10,
    dry_run: bool = False,
) -> dict:
    """
    Seed the database with mock sentiment data.
    
    Args:
        user_email: Email of user whose products to seed. If None, seeds all users.
        days: Number of days of historical data to generate.
        mentions_per_day: Average mentions per product per day.
        dry_run: If True, don't commit to database.
    
    Returns:
        Dict with counts of created records.
    """
    stats = {
        "users_processed": 0,
        "products_processed": 0,
        "mentions_created": 0,
        "sentiments_created": 0,
        "errors": [],
    }
    
    with Session(engine) as session:
        # Get users
        if user_email:
            user = session.exec(select(User).where(User.email == user_email)).first()
            if not user:
                stats["errors"].append(f"User not found: {user_email}")
                return stats
            users = [user]
        else:
            users = session.exec(select(User)).all()
        
        if not users:
            stats["errors"].append("No users found in database")
            return stats
        
        print(f"Processing {len(users)} user(s)...")
        
        for user in users:
            stats["users_processed"] += 1
            
            # Get user's products
            products = session.exec(
                select(Product).where(Product.user_id == user.id)
            ).all()
            
            if not products:
                print(f"  No products for user {user.email}, skipping...")
                continue
            
            print(f"  User {user.email}: {len(products)} product(s)")
            
            for product in products:
                stats["products_processed"] += 1
                print(f"    Seeding data for: {product.name}")
                
                # Generate mentions for each day
                now = datetime.now(timezone.utc)
                
                for day_offset in range(days, 0, -1):
                    # Calculate base date for this day
                    base_date = now - timedelta(days=day_offset)
                    
                    # Vary mentions per day (±50%)
                    day_mentions = random.randint(
                        max(1, mentions_per_day // 2),
                        int(mentions_per_day * 1.5)
                    )
                    
                    for _ in range(day_mentions):
                        # Random time during the day
                        published_at = base_date + timedelta(
                            hours=random.randint(0, 23),
                            minutes=random.randint(0, 59),
                        )
                        
                        try:
                            mention, sentiment = create_mention_and_sentiment(
                                session=session,
                                user_id=user.id,
                                product=product,
                                published_at=published_at,
                            )
                            
                            if not dry_run:
                                session.add(mention)
                                session.add(sentiment)
                            
                            stats["mentions_created"] += 1
                            stats["sentiments_created"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Error creating mention: {e}")
                
                # Commit per product to avoid huge transactions
                if not dry_run:
                    session.commit()
                    print(f"      ✓ Committed data for {product.name}")
        
        print("\n" + "=" * 50)
        print("SEEDING COMPLETE")
        print("=" * 50)
        print(f"Users processed:     {stats['users_processed']}")
        print(f"Products processed:  {stats['products_processed']}")
        print(f"Mentions created:    {stats['mentions_created']}")
        print(f"Sentiments created:  {stats['sentiments_created']}")
        
        if stats["errors"]:
            print(f"\nErrors ({len(stats['errors'])}):")
            for err in stats["errors"][:10]:
                print(f"  - {err}")
        
        if dry_run:
            print("\n⚠️  DRY RUN - No data was committed to database")
    
    return stats


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Seed mock sentiment data for SSP demos and testing"
    )
    parser.add_argument(
        "--user-email",
        type=str,
        default=None,
        help="Specific user email to seed data for (default: all users)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of historical data to generate (default: 30)",
    )
    parser.add_argument(
        "--mentions-per-day",
        type=int,
        default=10,
        help="Average mentions per product per day (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without committing",
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("SSP SENTIMENT DATA SEEDER")
    print("=" * 50)
    print(f"User filter:      {args.user_email or 'ALL USERS'}")
    print(f"Days of data:     {args.days}")
    print(f"Mentions/day:     {args.mentions_per_day}")
    print(f"Dry run:          {args.dry_run}")
    print("=" * 50 + "\n")
    
    seed_sentiment_data(
        user_email=args.user_email,
        days=args.days,
        mentions_per_day=args.mentions_per_day,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()




    