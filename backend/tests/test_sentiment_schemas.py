"""
Test Suite: backend/schemas/sentiment.py
Covers: SentimentAnalyzeRequest, SentimentBulkItem, SentimentBulkRequest,
        SentimentScores, SentimentRead, SentimentAnalyzeResponse,
        SentimentSummary, SentimentResponse, SocialMentionResponse, AIStatusResponse.

Place this file at: backend/tests/test_sentiment_schemas.py
Run with: pytest backend/tests/test_sentiment_schemas.py -v
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.sentiment import (
    AIStatusResponse,
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
    SentimentBulkItem,
    SentimentBulkRequest,
    SentimentRead,
    SentimentResponse,
    SentimentScores,
    SentimentSummary,
    SocialMentionResponse,
)

# =====================================================================
# SentimentAnalyzeRequest
# =====================================================================


class TestSentimentAnalyzeRequest:
    def test_valid_minimal(self):
        r = SentimentAnalyzeRequest(text="Great product!")
        assert r.text == "Great product!"
        assert r.source == "manual"
        assert r.author is None
        assert r.url is None

    def test_valid_full(self):
        r = SentimentAnalyzeRequest(
            text="Amazing headphones",
            source="reddit",
            author="user123",
            url="https://reddit.com/r/headphones/123",
        )
        assert r.source == "reddit"
        assert r.author == "user123"

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError):
            SentimentAnalyzeRequest(text="")

    def test_missing_text_raises(self):
        with pytest.raises(ValidationError):
            SentimentAnalyzeRequest()

    def test_source_max_length(self):
        with pytest.raises(ValidationError):
            SentimentAnalyzeRequest(text="test", source="x" * 51)

    def test_source_default(self):
        r = SentimentAnalyzeRequest(text="test")
        assert r.source == "manual"


# =====================================================================
# SentimentBulkItem / SentimentBulkRequest
# =====================================================================


class TestSentimentBulkItem:
    def test_valid_minimal(self):
        item = SentimentBulkItem(text="Good stuff")
        assert item.text == "Good stuff"
        assert item.source is None

    def test_valid_full(self):
        item = SentimentBulkItem(
            text="Great product",
            source="twitter",
            author="@user",
            url="https://twitter.com/status/123",
        )
        assert item.source == "twitter"

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError):
            SentimentBulkItem(text="")


class TestSentimentBulkRequest:
    def test_valid(self):
        r = SentimentBulkRequest(
            items=[
                SentimentBulkItem(text="Great"),
                SentimentBulkItem(text="Terrible"),
            ]
        )
        assert len(r.items) == 2

    def test_empty_items(self):
        """Empty list is technically valid per schema."""
        r = SentimentBulkRequest(items=[])
        assert r.items == []

    def test_missing_items_raises(self):
        with pytest.raises(ValidationError):
            SentimentBulkRequest()


# =====================================================================
# SentimentScores
# =====================================================================


class TestSentimentScores:
    def test_valid(self):
        s = SentimentScores(
            compound=Decimal("0.75"),
            positive=Decimal("0.8"),
            negative=Decimal("0.05"),
            neutral=Decimal("0.15"),
        )
        assert s.compound == Decimal("0.75")

    def test_compound_range_negative(self):
        s = SentimentScores(
            compound=Decimal("-1.0"),
            positive=Decimal("0"),
            negative=Decimal("1.0"),
            neutral=Decimal("0"),
        )
        assert s.compound == Decimal("-1.0")

    def test_compound_below_minus_one_raises(self):
        with pytest.raises(ValidationError):
            SentimentScores(
                compound=Decimal("-1.1"),
                positive=Decimal("0"),
                negative=Decimal("0"),
                neutral=Decimal("0"),
            )

    def test_compound_above_one_raises(self):
        with pytest.raises(ValidationError):
            SentimentScores(
                compound=Decimal("1.1"),
                positive=Decimal("0"),
                negative=Decimal("0"),
                neutral=Decimal("0"),
            )

    def test_positive_below_zero_raises(self):
        with pytest.raises(ValidationError):
            SentimentScores(
                compound=Decimal("0"),
                positive=Decimal("-0.1"),
                negative=Decimal("0"),
                neutral=Decimal("0"),
            )

    def test_positive_above_one_raises(self):
        with pytest.raises(ValidationError):
            SentimentScores(
                compound=Decimal("0"),
                positive=Decimal("1.1"),
                negative=Decimal("0"),
                neutral=Decimal("0"),
            )

    def test_negative_below_zero_raises(self):
        with pytest.raises(ValidationError):
            SentimentScores(
                compound=Decimal("0"),
                positive=Decimal("0"),
                negative=Decimal("-0.1"),
                neutral=Decimal("0"),
            )

    def test_neutral_below_zero_raises(self):
        with pytest.raises(ValidationError):
            SentimentScores(
                compound=Decimal("0"),
                positive=Decimal("0"),
                negative=Decimal("0"),
                neutral=Decimal("-0.1"),
            )

    def test_boundary_values(self):
        """All scores at their boundaries."""
        s = SentimentScores(
            compound=Decimal("1"),
            positive=Decimal("1"),
            negative=Decimal("0"),
            neutral=Decimal("0"),
        )
        assert s.compound == Decimal("1")
        assert s.positive == Decimal("1")


# =====================================================================
# SentimentRead
# =====================================================================


class TestSentimentRead:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "product_id": uuid.uuid4(),
            "source": "reddit",
            "raw_text": "These headphones are amazing!",
            "compound_score": Decimal("0.85"),
            "positive_score": Decimal("0.9"),
            "negative_score": Decimal("0.02"),
            "neutral_score": Decimal("0.08"),
            "author": "user123",
            "url": "https://reddit.com/r/test/123",
            "analyzed_at": datetime.now(UTC),
        }

    def test_valid(self, valid_data):
        r = SentimentRead(**valid_data)
        assert r.source == "reddit"
        assert r.compound_score == Decimal("0.85")

    def test_nullable_author_url(self, valid_data):
        valid_data["author"] = None
        valid_data["url"] = None
        r = SentimentRead(**valid_data)
        assert r.author is None

    def test_missing_id_raises(self, valid_data):
        del valid_data["id"]
        with pytest.raises(ValidationError):
            SentimentRead(**valid_data)

    def test_missing_product_id_raises(self, valid_data):
        del valid_data["product_id"]
        with pytest.raises(ValidationError):
            SentimentRead(**valid_data)

    def test_missing_raw_text_raises(self, valid_data):
        del valid_data["raw_text"]
        with pytest.raises(ValidationError):
            SentimentRead(**valid_data)


# =====================================================================
# SentimentAnalyzeResponse
# =====================================================================


class TestSentimentAnalyzeResponse:
    def test_valid(self):
        r = SentimentAnalyzeResponse(
            text="Great product",
            scores=SentimentScores(
                compound=Decimal("0.8"),
                positive=Decimal("0.85"),
                negative=Decimal("0.03"),
                neutral=Decimal("0.12"),
            ),
            label="positive",
        )
        assert r.label == "positive"
        assert r.saved is False
        assert r.sentiment_id is None

    def test_with_saved(self):
        r = SentimentAnalyzeResponse(
            text="Test",
            scores=SentimentScores(
                compound=Decimal("0"),
                positive=Decimal("0"),
                negative=Decimal("0"),
                neutral=Decimal("1"),
            ),
            label="neutral",
            saved=True,
            sentiment_id=uuid.uuid4(),
        )
        assert r.saved is True
        assert r.sentiment_id is not None

    def test_missing_scores_raises(self):
        with pytest.raises(ValidationError):
            SentimentAnalyzeResponse(text="Test", label="positive")


# =====================================================================
# SentimentSummary
# =====================================================================


class TestSentimentSummary:
    def test_valid_minimal(self):
        s = SentimentSummary(product_id=uuid.uuid4())
        assert s.total_mentions == 0
        assert s.total_records == 0
        assert s.average_compound is None
        assert s.positive_count == 0
        assert s.trend is None

    def test_valid_full(self):
        s = SentimentSummary(
            product_id=uuid.uuid4(),
            total_mentions=100,
            total_records=95,
            average_compound=Decimal("0.42"),
            average_score=Decimal("0.55"),
            positive_count=60,
            negative_count=15,
            neutral_count=20,
            label_distribution={"positive": 60, "negative": 15, "neutral": 20},
            trend="improving",
            period_start=datetime(2026, 1, 1, tzinfo=UTC),
            period_end=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert s.total_mentions == 100
        assert s.trend == "improving"

    def test_missing_product_id_raises(self):
        with pytest.raises(ValidationError):
            SentimentSummary()


# =====================================================================
# SentimentResponse
# =====================================================================


class TestSentimentResponse:
    def test_valid_minimal(self):
        r = SentimentResponse(
            sentiment_score=0.5,
            sentiment_label="positive",
            confidence=0.9,
        )
        assert r.sentiment_score == 0.5
        assert r.ai_powered is False
        assert r.topics is None
        assert r.is_sarcastic is None

    def test_valid_ai_powered(self):
        r = SentimentResponse(
            sentiment_score=-0.3,
            sentiment_label="negative",
            confidence=0.85,
            emotions={"anger": 0.4, "sadness": 0.3},
            topics=["quality", "durability"],
            is_sarcastic=False,
            ai_powered=True,
        )
        assert r.ai_powered is True
        assert len(r.topics) == 2
        assert r.is_sarcastic is False

    def test_sentiment_score_range(self):
        with pytest.raises(ValidationError):
            SentimentResponse(
                sentiment_score=1.5,
                sentiment_label="positive",
                confidence=0.9,
            )

    def test_sentiment_score_below_range(self):
        with pytest.raises(ValidationError):
            SentimentResponse(
                sentiment_score=-1.5,
                sentiment_label="negative",
                confidence=0.9,
            )

    def test_confidence_range(self):
        with pytest.raises(ValidationError):
            SentimentResponse(
                sentiment_score=0.5,
                sentiment_label="positive",
                confidence=1.5,
            )

    def test_confidence_below_zero(self):
        with pytest.raises(ValidationError):
            SentimentResponse(
                sentiment_score=0.5,
                sentiment_label="positive",
                confidence=-0.1,
            )

    def test_boundary_values(self):
        r = SentimentResponse(
            sentiment_score=-1.0,
            sentiment_label="negative",
            confidence=0.0,
        )
        assert r.sentiment_score == -1.0
        assert r.confidence == 0.0


# =====================================================================
# SocialMentionResponse
# =====================================================================


class TestSocialMentionResponse:
    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "product_id": uuid.uuid4(),
            "source": "reddit",
            "content": "This product is great!",
            "collected_at": datetime.now(UTC),
        }

    def test_valid_minimal(self, valid_data):
        r = SocialMentionResponse(**valid_data)
        assert r.source == "reddit"
        assert r.processed is False
        assert r.source_id is None
        assert r.author is None

    def test_valid_full(self, valid_data):
        data = {
            **valid_data,
            "source_id": "t3_abc123",
            "author": "reddit_user",
            "author_followers": 5000,
            "engagement_count": 250,
            "url": "https://reddit.com/r/test/abc123",
            "published_at": datetime.now(UTC),
            "processed": True,
        }
        r = SocialMentionResponse(**data)
        assert r.author_followers == 5000
        assert r.processed is True

    def test_missing_content_raises(self, valid_data):
        del valid_data["content"]
        with pytest.raises(ValidationError):
            SocialMentionResponse(**valid_data)

    def test_missing_source_raises(self, valid_data):
        del valid_data["source"]
        with pytest.raises(ValidationError):
            SocialMentionResponse(**valid_data)


# =====================================================================
# AIStatusResponse
# =====================================================================


class TestAIStatusResponse:
    def test_valid_unavailable(self):
        r = AIStatusResponse(openai_available=False)
        assert r.openai_available is False
        assert r.model is None
        assert r.features == []

    def test_valid_available(self):
        r = AIStatusResponse(
            openai_available=True,
            model="gpt-4",
            features=["emotion_detection", "sarcasm_detection", "topic_extraction"],
        )
        assert r.openai_available is True
        assert r.model == "gpt-4"
        assert len(r.features) == 3

    def test_missing_openai_available_raises(self):
        with pytest.raises(ValidationError):
            AIStatusResponse()
