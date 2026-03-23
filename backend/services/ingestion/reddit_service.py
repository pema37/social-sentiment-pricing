# backend/services/ingestion/reddit_service.py


import asyncio
from datetime import UTC, datetime

from core.config import settings
from services.ingestion.base import BaseCollector, CollectedMention, SocialSource


class RedditCollector(BaseCollector):
    """
    Reddit data collector using PRAW.
    Searches subreddits for mentions matching product keywords.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = "SocialSentimentPricing/1.0",
        mock_mode: bool = False,
    ):
        self.mock_mode = mock_mode
        self.reddit = None

        if not mock_mode:
            cid = client_id or settings.REDDIT_CLIENT_ID
            secret = client_secret or settings.REDDIT_CLIENT_SECRET

            if cid and secret and cid != "your_client_id_here":
                import praw

                self.reddit = praw.Reddit(
                    client_id=cid,
                    client_secret=secret,
                    user_agent=user_agent,
                )

    @property
    def source(self) -> SocialSource:
        return SocialSource.REDDIT

    async def collect(self, keywords: list[str], limit: int = 100) -> list[CollectedMention]:
        if self.mock_mode or self.reddit is None:
            return self._generate_mock_data(keywords, limit)
        return await self._collect_real_data(keywords, limit)

    def _search_sync(self, keyword: str, limit: int):
        """Run synchronous PRAW search in a thread-safe way."""
        return list(self.reddit.subreddit("all").search(keyword, limit=limit, sort="new"))

    async def _collect_real_data(self, keywords: list[str], limit: int) -> list[CollectedMention]:
        mentions = []
        for keyword in keywords:
            try:
                submissions = await asyncio.to_thread(self._search_sync, keyword, limit)
                for submission in submissions:
                    mention = CollectedMention(
                        source=SocialSource.REDDIT,
                        source_id=submission.id,
                        content=f"{submission.title}\n\n{submission.selftext}"
                        if submission.selftext
                        else submission.title,
                        author=str(submission.author) if submission.author else "[deleted]",
                        author_followers=None,
                        engagement_count=submission.score + submission.num_comments,
                        url=f"https://reddit.com{submission.permalink}",
                        published_at=datetime.fromtimestamp(submission.created_utc, tz=UTC),
                        language=None,
                        raw_data={
                            "subreddit": str(submission.subreddit),
                            "score": submission.score,
                            "num_comments": submission.num_comments,
                            "upvote_ratio": submission.upvote_ratio,
                        },
                    )
                    mentions.append(mention)
            except Exception as e:
                print(f"Error collecting Reddit data for keyword '{keyword}': {e}")
        return mentions

    def _generate_mock_data(self, keywords: list[str], limit: int) -> list[CollectedMention]:
        mock_posts = [
            {"title": "This product is amazing!", "score": 150, "comments": 23},
            {"title": "Not worth the price, very disappointed", "score": 89, "comments": 45},
            {"title": "Just bought this, seems okay so far", "score": 34, "comments": 12},
            {"title": "Best purchase I've made this year!", "score": 230, "comments": 67},
            {"title": "Broke after 2 weeks, terrible quality", "score": 456, "comments": 123},
            {"title": "Exceeded my expectations, highly recommend", "score": 189, "comments": 34},
        ]

        mentions = []
        for keyword in keywords:
            for j, post in enumerate(mock_posts[:limit]):
                mentions.append(
                    CollectedMention(
                        source=SocialSource.REDDIT,
                        source_id=f"mock_{keyword}_{j}",
                        content=f"{post['title']} - discussing {keyword}",
                        author=f"reddit_user_{j}",
                        author_followers=None,
                        engagement_count=post["score"] + post["comments"],
                        url=f"https://reddit.com/r/test/comments/mock_{j}",
                        published_at=datetime.now(UTC),
                        language="en",
                        raw_data={
                            "subreddit": "test",
                            "score": post["score"],
                            "num_comments": post["comments"],
                            "mock": True,
                        },
                    )
                )
        return mentions

    async def health_check(self) -> bool:
        if self.mock_mode or self.reddit is None:
            return True
        try:
            await asyncio.to_thread(lambda: list(self.reddit.subreddit("test").hot(limit=1)))
            return True
        except Exception:
            return False


def get_reddit_collector(mock_mode: bool = False) -> RedditCollector:
    return RedditCollector(mock_mode=mock_mode)
