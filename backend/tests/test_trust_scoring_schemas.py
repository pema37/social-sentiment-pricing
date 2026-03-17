"""
Test Suite: backend/schemas/trust_scoring.py
Covers: AuthorScoreRequest/Response, ComponentScores, BatchAuthorScore*,
        ContentAnalysisRequest/Response, SpamIndicators, BatchContentAnalysis*,
        MentionInput, CampaignDetectionRequest/Response, CampaignSignalResponse,
        WeightedSentimentRequest/Response, RawSentimentStats, AdjustedSentimentStats,
        QualityMetrics, QuickSpamCheck*, QuickTrustCheck*, TrustScoringStatsResponse.

Place this file at: backend/tests/test_trust_scoring_schemas.py
Run with: pytest backend/tests/test_trust_scoring_schemas.py -v
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.trust_scoring import (
    AdjustedSentimentStats,
    AuthorScoreRequest,
    AuthorScoreResponse,
    BatchAuthorScoreRequest,
    BatchAuthorScoreResponse,
    BatchContentAnalysisRequest,
    BatchContentAnalysisResponse,
    CampaignDetectionRequest,
    CampaignDetectionResponse,
    CampaignSignalResponse,
    ComponentScores,
    ContentAnalysisRequest,
    ContentAnalysisResponse,
    MentionInput,
    QualityMetrics,
    QuickSpamCheckRequest,
    QuickSpamCheckResponse,
    QuickTrustCheckRequest,
    QuickTrustCheckResponse,
    RawSentimentStats,
    RiskFlagEnum,
    SpamIndicators,
    TrustLevelEnum,
    TrustScoringStatsResponse,
    WeightedSentimentRequest,
    WeightedSentimentResponse,
)

NOW = datetime.now(UTC)


# =====================================================================
# Enums
# =====================================================================


class TestEnums:
    def test_all_trust_levels(self):
        expected = {"verified", "high", "medium", "low", "untrusted", "blocked"}
        assert {t.value for t in TrustLevelEnum} == expected

    def test_risk_flag_count(self):
        assert len(RiskFlagEnum) == 12


# =====================================================================
# AuthorScoreRequest
# =====================================================================


class TestAuthorScoreRequest:
    def test_valid_minimal(self):
        r = AuthorScoreRequest(
            author_id="user_123",
            username="testuser",
            source="twitter",
        )
        assert r.author_id == "user_123"
        assert r.is_verified is False
        assert r.follower_count is None

    def test_valid_full(self):
        r = AuthorScoreRequest(
            author_id="user_456",
            username="reviewer",
            source="reddit",
            follower_count=5000,
            following_count=200,
            post_count=1500,
            account_created_at=NOW,
            is_verified=True,
        )
        assert r.follower_count == 5000
        assert r.is_verified is True

    def test_missing_author_id_raises(self):
        with pytest.raises(ValidationError):
            AuthorScoreRequest(username="test", source="twitter")

    def test_missing_username_raises(self):
        with pytest.raises(ValidationError):
            AuthorScoreRequest(author_id="u1", source="twitter")

    def test_missing_source_raises(self):
        with pytest.raises(ValidationError):
            AuthorScoreRequest(author_id="u1", username="test")

    def test_negative_follower_count_raises(self):
        with pytest.raises(ValidationError):
            AuthorScoreRequest(
                author_id="u1",
                username="t",
                source="x",
                follower_count=-1,
            )

    def test_negative_post_count_raises(self):
        with pytest.raises(ValidationError):
            AuthorScoreRequest(
                author_id="u1",
                username="t",
                source="x",
                post_count=-1,
            )


# =====================================================================
# ComponentScores
# =====================================================================


class TestComponentScores:
    def test_valid(self):
        c = ComponentScores(
            account_age=0.85,
            followers=0.65,
            engagement=0.70,
            history=0.50,
            verification_bonus=0.0,
        )
        assert c.account_age == 0.85

    def test_below_zero_raises(self):
        with pytest.raises(ValidationError):
            ComponentScores(
                account_age=-0.1,
                followers=0,
                engagement=0,
                history=0,
                verification_bonus=0,
            )

    def test_above_one_raises(self):
        with pytest.raises(ValidationError):
            ComponentScores(
                account_age=1.1,
                followers=0,
                engagement=0,
                history=0,
                verification_bonus=0,
            )

    def test_boundary_values(self):
        c = ComponentScores(
            account_age=0.0,
            followers=1.0,
            engagement=0.0,
            history=1.0,
            verification_bonus=0.0,
        )
        assert c.followers == 1.0


# =====================================================================
# AuthorScoreResponse
# =====================================================================


class TestAuthorScoreResponse:
    @pytest.fixture
    def valid_data(self):
        return {
            "author_id": "user_123",
            "source": "twitter",
            "trust_score": 0.72,
            "trust_level": TrustLevelEnum.HIGH,
            "risk_flags": [],
            "risk_score": 0.1,
            "component_scores": ComponentScores(
                account_age=0.85,
                followers=0.65,
                engagement=0.70,
                history=0.50,
                verification_bonus=0.0,
            ),
            "confidence": 0.75,
            "calculated_at": NOW,
        }

    def test_valid(self, valid_data):
        r = AuthorScoreResponse(**valid_data)
        assert r.trust_level == TrustLevelEnum.HIGH

    def test_with_risk_flags(self, valid_data):
        valid_data["risk_flags"] = [RiskFlagEnum.NEW_ACCOUNT, RiskFlagEnum.LOW_FOLLOWERS]
        r = AuthorScoreResponse(**valid_data)
        assert len(r.risk_flags) == 2

    def test_trust_score_above_one_raises(self, valid_data):
        valid_data["trust_score"] = 1.5
        with pytest.raises(ValidationError):
            AuthorScoreResponse(**valid_data)

    def test_all_trust_levels(self, valid_data):
        for level in TrustLevelEnum:
            valid_data["trust_level"] = level
            r = AuthorScoreResponse(**valid_data)
            assert r.trust_level == level


# =====================================================================
# BatchAuthorScore
# =====================================================================


class TestBatchAuthorScore:
    def test_batch_request(self):
        r = BatchAuthorScoreRequest(
            authors=[
                AuthorScoreRequest(author_id="u1", username="a", source="x"),
                AuthorScoreRequest(author_id="u2", username="b", source="x"),
            ]
        )
        assert len(r.authors) == 2

    def test_batch_response(self):
        r = BatchAuthorScoreResponse(
            scores=[],
            total=0,
            avg_trust_score=0.0,
        )
        assert r.total == 0


# =====================================================================
# ContentAnalysisRequest
# =====================================================================


class TestContentAnalysisRequest:
    def test_valid_minimal(self):
        r = ContentAnalysisRequest(
            content_id="post_123",
            text="This product is great!",
        )
        assert r.author_username is None

    def test_valid_full(self):
        r = ContentAnalysisRequest(
            content_id="post_456",
            text="Amazing product, highly recommend",
            author_username="reviewer42",
        )
        assert r.author_username == "reviewer42"

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError):
            ContentAnalysisRequest(content_id="p1", text="")

    def test_text_max_length(self):
        with pytest.raises(ValidationError):
            ContentAnalysisRequest(content_id="p1", text="x" * 10001)

    def test_missing_content_id_raises(self):
        with pytest.raises(ValidationError):
            ContentAnalysisRequest(text="test")


# =====================================================================
# SpamIndicators
# =====================================================================


class TestSpamIndicators:
    def test_valid(self):
        s = SpamIndicators(
            excessive_hashtags=False,
            excessive_links=False,
            keyword_stuffing=True,
            all_caps=False,
            spam_phrases=True,
        )
        assert s.keyword_stuffing is True
        assert s.spam_phrases is True

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            SpamIndicators(
                excessive_hashtags=False,
                excessive_links=False,
                # missing keyword_stuffing
                all_caps=False,
                spam_phrases=False,
            )


# =====================================================================
# ContentAnalysisResponse
# =====================================================================


class TestContentAnalysisResponse:
    @pytest.fixture
    def valid_data(self):
        return {
            "content_id": "post_123",
            "word_count": 12,
            "is_duplicate": False,
            "duplicate_count": 0,
            "content_quality_score": 0.75,
            "originality_score": 1.0,
            "risk_flags": [],
            "spam_indicators": SpamIndicators(
                excessive_hashtags=False,
                excessive_links=False,
                keyword_stuffing=False,
                all_caps=False,
                spam_phrases=False,
            ),
            "is_spam": False,
        }

    def test_valid(self, valid_data):
        r = ContentAnalysisResponse(**valid_data)
        assert r.is_spam is False

    def test_quality_score_range(self, valid_data):
        valid_data["content_quality_score"] = 1.5
        with pytest.raises(ValidationError):
            ContentAnalysisResponse(**valid_data)

    def test_with_risk_flags(self, valid_data):
        valid_data["risk_flags"] = [RiskFlagEnum.KEYWORD_STUFFING, RiskFlagEnum.LINK_SPAM]
        valid_data["is_spam"] = True
        r = ContentAnalysisResponse(**valid_data)
        assert r.is_spam is True
        assert len(r.risk_flags) == 2


# =====================================================================
# BatchContentAnalysis
# =====================================================================


class TestBatchContentAnalysis:
    def test_batch_request(self):
        r = BatchContentAnalysisRequest(
            contents=[
                ContentAnalysisRequest(content_id="p1", text="Good"),
                ContentAnalysisRequest(content_id="p2", text="Bad"),
            ]
        )
        assert len(r.contents) == 2

    def test_batch_response(self):
        r = BatchContentAnalysisResponse(
            analyses=[],
            total=0,
            spam_count=0,
            duplicate_count=0,
        )
        assert r.spam_count == 0


# =====================================================================
# MentionInput
# =====================================================================


class TestMentionInput:
    def test_valid_minimal(self):
        m = MentionInput(
            mention_id="m1",
            author_id="a1",
            content="Great product!",
            published_at=NOW,
        )
        assert m.source == "unknown"
        assert m.sentiment_score is None

    def test_valid_full(self):
        m = MentionInput(
            mention_id="m2",
            author_id="a2",
            content="Terrible",
            published_at=NOW,
            sentiment_score=-0.8,
            source="reddit",
        )
        assert m.sentiment_score == -0.8

    def test_sentiment_score_above_range(self):
        with pytest.raises(ValidationError):
            MentionInput(
                mention_id="m",
                author_id="a",
                content="x",
                published_at=NOW,
                sentiment_score=1.5,
            )

    def test_sentiment_score_below_range(self):
        with pytest.raises(ValidationError):
            MentionInput(
                mention_id="m",
                author_id="a",
                content="x",
                published_at=NOW,
                sentiment_score=-1.5,
            )


# =====================================================================
# CampaignDetection
# =====================================================================


def _mentions(n):
    """Helper to build N valid mentions."""
    return [
        MentionInput(
            mention_id=f"m{i}",
            author_id=f"a{i}",
            content=f"Content {i}",
            published_at=NOW,
        )
        for i in range(n)
    ]


class TestCampaignDetectionRequest:
    def test_valid(self):
        r = CampaignDetectionRequest(mentions=_mentions(5))
        assert r.time_window_hours == 24
        assert r.product_id is None

    def test_min_mentions(self):
        with pytest.raises(ValidationError):
            CampaignDetectionRequest(mentions=_mentions(4))

    def test_time_window_min(self):
        with pytest.raises(ValidationError):
            CampaignDetectionRequest(
                mentions=_mentions(5),
                time_window_hours=0,
            )

    def test_time_window_max(self):
        with pytest.raises(ValidationError):
            CampaignDetectionRequest(
                mentions=_mentions(5),
                time_window_hours=169,
            )


class TestCampaignSignalResponse:
    def test_valid(self):
        s = CampaignSignalResponse(
            signal_type="timing_cluster",
            strength=0.85,
            description="Detected synchronized posting",
        )
        assert s.strength == 0.85

    def test_strength_above_one_raises(self):
        with pytest.raises(ValidationError):
            CampaignSignalResponse(
                signal_type="test",
                strength=1.5,
                description="x",
            )


class TestCampaignDetectionResponse:
    def test_valid(self):
        r = CampaignDetectionResponse(
            product_id="prod_123",
            time_window_hours=24,
            is_campaign_detected=True,
            campaign_confidence=0.78,
            signals=[],
            metrics={"posts_analyzed": 50},
            suspicious_author_count=8,
            suspicious_content_count=12,
            analyzed_at=NOW,
        )
        assert r.is_campaign_detected is True

    def test_no_campaign(self):
        r = CampaignDetectionResponse(
            product_id=None,
            time_window_hours=24,
            is_campaign_detected=False,
            campaign_confidence=0.05,
            signals=[],
            metrics={},
            suspicious_author_count=0,
            suspicious_content_count=0,
            analyzed_at=NOW,
        )
        assert r.campaign_confidence == 0.05


# =====================================================================
# WeightedSentiment
# =====================================================================


class TestWeightedSentimentRequest:
    def test_valid_minimal(self):
        r = WeightedSentimentRequest(
            mentions=[
                MentionInput(
                    mention_id="m1",
                    author_id="a1",
                    content="Good stuff",
                    published_at=NOW,
                )
            ]
        )
        assert r.period_hours == 24
        assert r.check_campaign is True
        assert r.author_metadata is None

    def test_min_mentions(self):
        with pytest.raises(ValidationError):
            WeightedSentimentRequest(mentions=[])

    def test_period_hours_range(self):
        with pytest.raises(ValidationError):
            WeightedSentimentRequest(
                mentions=[
                    MentionInput(
                        mention_id="m1",
                        author_id="a1",
                        content="x",
                        published_at=NOW,
                    )
                ],
                period_hours=0,
            )


class TestRawSentimentStats:
    def test_valid(self):
        r = RawSentimentStats(sentiment=0.45, mention_count=100)
        assert r.sentiment == 0.45


class TestAdjustedSentimentStats:
    def test_valid(self):
        a = AdjustedSentimentStats(sentiment=0.32, effective_mentions=67.5)
        assert a.effective_mentions == 67.5


class TestQualityMetrics:
    def test_valid(self):
        q = QualityMetrics(
            high_trust_ratio=0.35,
            filtered_count=15,
            confidence=0.72,
        )
        assert q.confidence == 0.72


class TestWeightedSentimentResponse:
    def test_valid(self):
        r = WeightedSentimentResponse(
            product_id="prod_123",
            period_hours=24,
            raw=RawSentimentStats(sentiment=0.45, mention_count=100),
            adjusted=AdjustedSentimentStats(sentiment=0.32, effective_mentions=67.5),
            quality=QualityMetrics(high_trust_ratio=0.35, filtered_count=15, confidence=0.72),
            trust_breakdown={"verified": 5, "high": 30, "medium": 40},
            campaign_detected=False,
        )
        assert r.campaign_detected is False


# =====================================================================
# Quick Check Endpoints
# =====================================================================


class TestQuickSpamCheck:
    def test_request_valid(self):
        r = QuickSpamCheckRequest(text="Test product review")
        assert r.username is None

    def test_request_empty_text_raises(self):
        with pytest.raises(ValidationError):
            QuickSpamCheckRequest(text="")

    def test_request_text_max_length(self):
        with pytest.raises(ValidationError):
            QuickSpamCheckRequest(text="x" * 5001)

    def test_response_valid(self):
        r = QuickSpamCheckResponse(
            is_spam=False,
            spam_score=0.1,
            reasons=[],
        )
        assert r.is_spam is False

    def test_response_spam_detected(self):
        r = QuickSpamCheckResponse(
            is_spam=True,
            spam_score=0.95,
            reasons=["keyword_stuffing", "link_spam"],
        )
        assert len(r.reasons) == 2

    def test_response_score_range(self):
        with pytest.raises(ValidationError):
            QuickSpamCheckResponse(is_spam=False, spam_score=1.5, reasons=[])


class TestQuickTrustCheck:
    def test_request_valid(self):
        r = QuickTrustCheckRequest(
            author_id="u1",
            username="test",
            source="twitter",
        )
        assert r.follower_count is None
        assert r.account_age_days is None

    def test_request_missing_required(self):
        with pytest.raises(ValidationError):
            QuickTrustCheckRequest(author_id="u1")

    def test_response_valid(self):
        r = QuickTrustCheckResponse(
            is_trustworthy=True,
            trust_score=0.8,
            trust_level=TrustLevelEnum.HIGH,
            risk_flags=[],
        )
        assert r.is_trustworthy is True

    def test_response_untrusted(self):
        r = QuickTrustCheckResponse(
            is_trustworthy=False,
            trust_score=0.15,
            trust_level=TrustLevelEnum.UNTRUSTED,
            risk_flags=["new_account", "low_followers"],
        )
        assert r.trust_level == TrustLevelEnum.UNTRUSTED
        assert len(r.risk_flags) == 2

    def test_response_score_range(self):
        with pytest.raises(ValidationError):
            QuickTrustCheckResponse(
                is_trustworthy=True,
                trust_score=-0.1,
                trust_level=TrustLevelEnum.HIGH,
                risk_flags=[],
            )


# =====================================================================
# TrustScoringStatsResponse
# =====================================================================


class TestTrustScoringStatsResponse:
    def test_valid(self):
        r = TrustScoringStatsResponse(
            content_analyzer={"analyzed": 500, "spam_detected": 25},
            config={"min_trust_threshold": 0.3},
            cache_stats={"hits": 1200, "misses": 300},
        )
        assert r.content_analyzer["analyzed"] == 500

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            TrustScoringStatsResponse(
                content_analyzer={"analyzed": 500},
            )
