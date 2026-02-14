"""
Tests for services/ingestion/reddit_service.py — RedditCollector

Covers:
- __init__: mock mode, no credentials, with credentials (praw stubbed)
- source property: returns SocialSource.REDDIT
- collect: delegates to mock or real based on mode/client
- _generate_mock_data: structure, keyword inclusion, limit respected
- _collect_real_data: maps praw submissions to CollectedMention, error handling
- health_check: mock mode, real mode success/failure
- get_reddit_collector: factory function
"""

import sys
import os
from types import ModuleType
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session", "core.logging", "core.config", "praw",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

for _m in ("db.session", "core.logging"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if "core" not in sys.modules:
    _core = ModuleType("core")
    _core.__path__ = [os.path.join(_backend_dir, "core")]
    sys.modules["core"] = _core

_config_stub = ModuleType("core.config")
_fake_settings = MagicMock()
_fake_settings.REDDIT_CLIENT_ID = None
_fake_settings.REDDIT_CLIENT_SECRET = None
_config_stub.settings = _fake_settings
sys.modules["core.config"] = _config_stub

for _pkg, _subdir in [
    ("services", "services"),
    ("services.ingestion", "services/ingestion"),
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# Stub praw so it doesn't need to be installed
_praw_stub = ModuleType("praw")
_praw_stub.Reddit = MagicMock()
sys.modules["praw"] = _praw_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.ingestion.reddit_service import RedditCollector, get_reddit_collector
from services.ingestion.base import SocialSource, CollectedMention

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Helpers
# ===========================================================================

def _make_mock_submission(**overrides):
    """Create a fake praw Submission object."""
    sub = MagicMock()
    sub.id = overrides.get("id", "abc123")
    sub.title = overrides.get("title", "Great product review")
    sub.selftext = overrides.get("selftext", "I love this product")
    sub.author = overrides.get("author", MagicMock(__str__=lambda s: "testuser"))
    sub.score = overrides.get("score", 42)
    sub.num_comments = overrides.get("num_comments", 10)
    sub.permalink = overrides.get("permalink", "/r/test/comments/abc123/great/")
    sub.created_utc = overrides.get("created_utc", 1700000000)
    sub.upvote_ratio = overrides.get("upvote_ratio", 0.95)
    sub.subreddit = overrides.get("subreddit", MagicMock(__str__=lambda s: "gadgets"))
    return sub


# ===========================================================================
# Tests
# ===========================================================================

class TestInit:
    def test_mock_mode(self):
        rc = RedditCollector(mock_mode=True)
        assert rc.mock_mode is True
        assert rc.reddit is None

    def test_no_credentials(self):
        _fake_settings.REDDIT_CLIENT_ID = None
        _fake_settings.REDDIT_CLIENT_SECRET = None
        rc = RedditCollector(mock_mode=False)
        assert rc.reddit is None

    def test_placeholder_credentials_ignored(self):
        _fake_settings.REDDIT_CLIENT_ID = "your_client_id_here"
        _fake_settings.REDDIT_CLIENT_SECRET = "some_secret"
        rc = RedditCollector(mock_mode=False)
        assert rc.reddit is None

    def test_with_valid_credentials(self):
        _fake_settings.REDDIT_CLIENT_ID = "real_id"
        _fake_settings.REDDIT_CLIENT_SECRET = "real_secret"

        mock_praw = MagicMock()
        mock_praw.Reddit.return_value = MagicMock()
        with patch.dict("sys.modules", {"praw": mock_praw}):
            rc = RedditCollector(mock_mode=False)
            assert rc.reddit is not None
            mock_praw.Reddit.assert_called_once()

    def test_explicit_credentials_override_settings(self):
        _fake_settings.REDDIT_CLIENT_ID = None
        _fake_settings.REDDIT_CLIENT_SECRET = None

        mock_praw = MagicMock()
        mock_praw.Reddit.return_value = MagicMock()
        with patch.dict("sys.modules", {"praw": mock_praw}):
            rc = RedditCollector(
                client_id="explicit_id",
                client_secret="explicit_secret",
                mock_mode=False,
            )
            assert rc.reddit is not None


class TestSourceProperty:
    def test_returns_reddit(self):
        rc = RedditCollector(mock_mode=True)
        assert rc.source == SocialSource.REDDIT


class TestCollect:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_mock_data(self):
        rc = RedditCollector(mock_mode=True)
        results = await rc.collect(["widget"], limit=3)
        assert len(results) > 0
        assert all(isinstance(m, CollectedMention) for m in results)
        assert all(m.source == SocialSource.REDDIT for m in results)

    @pytest.mark.asyncio
    async def test_no_client_returns_mock_data(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = None
        results = await rc.collect(["test"])
        assert len(results) > 0  # Falls back to mock

    @pytest.mark.asyncio
    async def test_with_client_calls_real(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()  # Pretend we have a client
        rc._collect_real_data = AsyncMock(return_value=[])

        results = await rc.collect(["test"])
        rc._collect_real_data.assert_awaited_once_with(["test"], 100)


class TestGenerateMockData:
    def test_returns_mentions(self):
        rc = RedditCollector(mock_mode=True)
        results = rc._generate_mock_data(["shoes"], limit=6)
        assert len(results) == 6
        assert all(m.source == SocialSource.REDDIT for m in results)

    def test_keyword_in_content(self):
        rc = RedditCollector(mock_mode=True)
        results = rc._generate_mock_data(["sneakers"], limit=2)
        for m in results:
            assert "sneakers" in m.content

    def test_limit_respected(self):
        rc = RedditCollector(mock_mode=True)
        results = rc._generate_mock_data(["test"], limit=2)
        assert len(results) == 2

    def test_multiple_keywords(self):
        rc = RedditCollector(mock_mode=True)
        results = rc._generate_mock_data(["alpha", "beta"], limit=3)
        # 3 per keyword × 2 keywords = 6
        assert len(results) == 6

    def test_mention_structure(self):
        rc = RedditCollector(mock_mode=True)
        results = rc._generate_mock_data(["widget"], limit=1)
        m = results[0]
        assert m.source_id.startswith("mock_widget_")
        assert m.author.startswith("reddit_user_")
        assert m.url.startswith("https://reddit.com/")
        assert m.language == "en"
        assert m.raw_data["mock"] is True
        assert m.published_at is not None
        assert m.engagement_count > 0


class TestCollectRealData:
    @pytest.mark.asyncio
    async def test_maps_submission_to_mention(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()

        sub = _make_mock_submission()
        rc.reddit.subreddit.return_value.search.return_value = [sub]

        results = await rc._collect_real_data(["test"], limit=10)

        assert len(results) == 1
        m = results[0]
        assert m.source == SocialSource.REDDIT
        assert m.source_id == "abc123"
        assert "Great product review" in m.content
        assert "I love this product" in m.content
        assert m.engagement_count == 52  # score 42 + comments 10
        assert "reddit.com" in m.url
        assert m.raw_data["score"] == 42
        assert m.raw_data["num_comments"] == 10

    @pytest.mark.asyncio
    async def test_no_selftext(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()

        sub = _make_mock_submission(selftext="", title="Title only post")
        rc.reddit.subreddit.return_value.search.return_value = [sub]

        results = await rc._collect_real_data(["test"], limit=10)
        assert results[0].content == "Title only post"

    @pytest.mark.asyncio
    async def test_deleted_author(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()

        sub = _make_mock_submission(author=None)
        rc.reddit.subreddit.return_value.search.return_value = [sub]

        results = await rc._collect_real_data(["test"], limit=10)
        assert results[0].author == "[deleted]"

    @pytest.mark.asyncio
    async def test_error_handling_continues(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()

        # First keyword raises, second succeeds
        def side_effect(keyword, **kwargs):
            if keyword == "bad":
                raise Exception("API error")
            return [_make_mock_submission()]

        rc.reddit.subreddit.return_value.search.side_effect = side_effect

        results = await rc._collect_real_data(["bad", "good"], limit=10)
        assert len(results) == 1  # Only "good" keyword succeeded

    @pytest.mark.asyncio
    async def test_multiple_keywords(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()

        rc.reddit.subreddit.return_value.search.return_value = [_make_mock_submission()]

        results = await rc._collect_real_data(["alpha", "beta"], limit=10)
        assert len(results) == 2


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_mock_mode_returns_true(self):
        rc = RedditCollector(mock_mode=True)
        assert await rc.health_check() is True

    @pytest.mark.asyncio
    async def test_no_client_returns_true(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = None
        assert await rc.health_check() is True

    @pytest.mark.asyncio
    async def test_real_success(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()
        rc.reddit.subreddit.return_value.hot.return_value = iter([MagicMock()])

        assert await rc.health_check() is True

    @pytest.mark.asyncio
    async def test_real_failure(self):
        rc = RedditCollector(mock_mode=False)
        rc.reddit = MagicMock()
        rc.reddit.subreddit.return_value.hot.side_effect = Exception("Connection error")

        assert await rc.health_check() is False


class TestGetRedditCollector:
    def test_returns_collector(self):
        rc = get_reddit_collector(mock_mode=True)
        assert isinstance(rc, RedditCollector)
        assert rc.mock_mode is True

    def test_default_not_mock(self):
        rc = get_reddit_collector()
        assert rc.mock_mode is False

        