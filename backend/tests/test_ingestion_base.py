"""
Tests for services/ingestion/base.py — SocialSource, CollectedMention, BaseCollector

Covers:
- SocialSource enum: values, string behavior
- CollectedMention: defaults, full construction, required fields
- BaseCollector: abstract methods enforced, concrete subclass works
"""

import sys
import os
from types import ModuleType
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# sys.modules stubs
# ---------------------------------------------------------------------------
_MOCKED = ["db.session", "core.logging"]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

for _m in _MOCKED:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _pkg, _subdir in [
    ("services", "services"),
    ("services.ingestion", "services/ingestion"),
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

from services.ingestion.base import SocialSource, CollectedMention, BaseCollector

for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Tests
# ===========================================================================

class TestSocialSource:
    def test_values(self):
        assert SocialSource.TWITTER == "twitter"
        assert SocialSource.REDDIT == "reddit"
        assert SocialSource.TIKTOK == "tiktok"
        assert SocialSource.AGGREGATOR == "aggregator"

    def test_is_string(self):
        assert isinstance(SocialSource.TWITTER, str)

    def test_membership(self):
        assert "twitter" in [s.value for s in SocialSource]


class TestCollectedMention:
    def test_required_fields(self):
        m = CollectedMention(
            source=SocialSource.REDDIT,
            source_id="abc123",
            content="Great product!",
            author="user1",
        )
        assert m.source == SocialSource.REDDIT
        assert m.source_id == "abc123"
        assert m.content == "Great product!"
        assert m.author == "user1"

    def test_defaults(self):
        m = CollectedMention(
            source=SocialSource.TWITTER,
            source_id="t1",
            content="text",
            author="u",
        )
        assert m.author_followers is None
        assert m.engagement_count == 0
        assert m.url is None
        assert m.published_at is None
        assert m.language is None
        assert m.raw_data is None

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        m = CollectedMention(
            source=SocialSource.TIKTOK,
            source_id="tk_99",
            content="Amazing!",
            author="creator",
            author_followers=50000,
            engagement_count=12000,
            url="https://tiktok.com/v/99",
            published_at=now,
            language="en",
            raw_data={"likes": 10000},
        )
        assert m.author_followers == 50000
        assert m.engagement_count == 12000
        assert m.url == "https://tiktok.com/v/99"
        assert m.published_at == now
        assert m.language == "en"
        assert m.raw_data == {"likes": 10000}


class TestBaseCollector:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseCollector()

    def test_concrete_subclass_works(self):
        class FakeCollector(BaseCollector):
            @property
            def source(self):
                return SocialSource.AGGREGATOR

            async def collect(self, keywords, limit=100):
                return []

            async def health_check(self):
                return True

        fc = FakeCollector()
        assert fc.source == SocialSource.AGGREGATOR

    def test_missing_method_raises(self):
        with pytest.raises(TypeError):
            class Incomplete(BaseCollector):
                @property
                def source(self):
                    return SocialSource.TWITTER
                # Missing collect and health_check
            Incomplete()

    @pytest.mark.asyncio
    async def test_collect_callable(self):
        class FakeCollector(BaseCollector):
            @property
            def source(self):
                return SocialSource.REDDIT

            async def collect(self, keywords, limit=100):
                return [CollectedMention(
                    source=self.source,
                    source_id="1",
                    content="test",
                    author="bot",
                )]

            async def health_check(self):
                return True

        fc = FakeCollector()
        results = await fc.collect(["test"])
        assert len(results) == 1
        assert results[0].source == SocialSource.REDDIT

    @pytest.mark.asyncio
    async def test_health_check_callable(self):
        class FakeCollector(BaseCollector):
            @property
            def source(self):
                return SocialSource.TWITTER

            async def collect(self, keywords, limit=100):
                return []

            async def health_check(self):
                return False

        fc = FakeCollector()
        assert await fc.health_check() is False


        