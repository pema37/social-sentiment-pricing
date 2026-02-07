"""
Tests for the ActualPrice trust scoring pipeline.
Aligned with actual service signatures:
  - AuthorScorer.score_author(profile: AuthorProfile) → AuthorTrustScore
  - ContentAnalyzer.analyze(content_id, text) → ContentAnalysis (content_quality_score)
  - CampaignDetector.detect(mentions) → CampaignDetectionResult (is_campaign_detected)
  - TrustScoringService.score_author(profile, username, source)
  - TrustScoringService.analyze_content(content_id, text)
"""

import dataclasses
import pytest


def _make_profile(**overrides):
    """Create an AuthorProfile using only fields the dataclass actually has."""
    from services.trust_scoring.models import AuthorProfile
    valid_fields = {f.name for f in dataclasses.fields(AuthorProfile)}

    # Map common test names to possible real field names
    aliases = {
        "karma": ["karma", "karma_score", "total_karma", "comment_karma"],
        "subreddit_diversity": ["subreddit_diversity", "community_diversity", "subreddit_count"],
        "post_count": ["post_count", "total_posts", "posts"],
        "verified_email": ["verified_email", "email_verified", "is_verified"],
        "account_age_days": ["account_age_days", "age_days"],
        "username": ["username", "author_id", "name"],
    }

    kwargs = {}
    for key, value in overrides.items():
        if key in valid_fields:
            kwargs[key] = value
        else:
            # Try aliases
            for alias in aliases.get(key, []):
                if alias in valid_fields:
                    kwargs[alias] = value
                    break

    # Fill required fields with sensible defaults if not provided
    for f in dataclasses.fields(AuthorProfile):
        if f.name not in kwargs and f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            # Provide defaults based on type
            if f.type in ("str", str):
                kwargs[f.name] = "test_user"
            elif f.type in ("int", int):
                kwargs[f.name] = 100
            elif f.type in ("float", float):
                kwargs[f.name] = 0.5
            elif f.type in ("bool", bool):
                kwargs[f.name] = True

    return AuthorProfile(**kwargs)


class TestAuthorScorer:

    def test_profile_creates_successfully(self):
        """AuthorProfile should be constructable with _make_profile helper."""
        profile = _make_profile(username="test", account_age_days=500)
        assert profile is not None

    def test_established_author_scores_high(self):
        from services.trust_scoring.author_scorer import AuthorScorer
        scorer = AuthorScorer()
        profile = _make_profile(
            username="audiofan42", account_age_days=1200,
            karma=15000, post_count=300, subreddit_diversity=12,
        )
        result = scorer.score_author(profile)
        assert result.trust_score >= 0.5

    def test_new_account_scores_low(self):
        from services.trust_scoring.author_scorer import AuthorScorer
        scorer = AuthorScorer()
        profile = _make_profile(
            username="newuser_xyz123", account_age_days=2,
            karma=1, verified_email=False, post_count=1, subreddit_diversity=1,
        )
        result = scorer.score_author(profile)
        assert result.trust_score <= 0.6

    def test_score_always_bounded(self):
        from services.trust_scoring.author_scorer import AuthorScorer
        scorer = AuthorScorer()
        for kwargs in [
            dict(username="x", account_age_days=0),
            dict(username="x", account_age_days=100000),
        ]:
            profile = _make_profile(**kwargs)
            result = scorer.score_author(profile)
            assert 0.0 <= result.trust_score <= 1.0

    def test_result_has_expected_fields(self):
        from services.trust_scoring.author_scorer import AuthorScorer
        scorer = AuthorScorer()
        profile = _make_profile(username="test", account_age_days=100)
        result = scorer.score_author(profile)
        assert hasattr(result, "trust_score")
        assert hasattr(result, "trust_level")


class TestContentAnalyzer:

    def test_genuine_review_scores_high(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.analyze(
            "test-001",
            "I've been using these headphones for 3 months. The sound quality is "
            "excellent for the price range - clear highs and decent bass. Battery "
            "lasts about 18 hours. Only downside is ear cups get warm after 2 hours. 8/10.",
        )
        assert result.content_quality_score >= 0.4

    def test_spam_review_scores_low(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.analyze(
            "test-002",
            "BUY NOW!!! BEST DEAL EVER!!! CLICK HERE!!! AMAZING PRODUCT BUY BUY BUY!!!",
        )
        assert result.content_quality_score <= 0.5

    def test_empty_content_scores_low(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.analyze("test-003", "")
        assert result.content_quality_score <= 0.6

    def test_short_vs_detailed_content(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        short = analyzer.analyze("t4", "Good.")
        detailed = analyzer.analyze(
            "t5",
            "After 3 months of daily use, the 40mm drivers still deliver clear audio. "
            "Battery lasts 18.5 hours. The 250g weight is comfortable for 2-hour sessions.",
        )
        assert detailed.content_quality_score >= short.content_quality_score

    def test_caps_text_penalized(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        caps = analyzer.analyze("t6", "THIS IS THE BEST PRODUCT EVER MADE I LOVE IT SO MUCH")
        normal = analyzer.analyze("t7", "This is the best product ever made, I love it so much.")
        assert caps.content_quality_score <= normal.content_quality_score

    def test_url_heavy_penalized(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.analyze(
            "t8",
            "Check https://spam1.com https://spam2.com https://spam3.com https://spam4.com!!!",
        )
        assert result.content_quality_score <= 0.6

    def test_promotional_language_low(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.analyze(
            "t9",
            "USE CODE SAVE20 FOR 20% OFF! Limited time offer! Shop now at our store!",
        )
        assert result.content_quality_score <= 0.6

    def test_legitimate_negative_review_decent(self):
        from services.trust_scoring.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        result = analyzer.analyze(
            "t10",
            "I'm disappointed with these headphones. After 2 weeks, the left ear cup "
            "stopped working. Bluetooth range is only 10 feet, not the advertised 30. "
            "Returning for a refund.",
        )
        assert result.content_quality_score >= 0.3


class TestCampaignDetector:

    def test_empty_mentions_no_campaign(self):
        from services.trust_scoring.campaign_detector import CampaignDetector
        detector = CampaignDetector()
        result = detector.detect([])
        assert result.is_campaign_detected is False

    def test_detector_initializes(self):
        from services.trust_scoring.campaign_detector import CampaignDetector
        detector = CampaignDetector()
        assert detector is not None

    def test_result_has_fields(self):
        from services.trust_scoring.campaign_detector import CampaignDetector
        detector = CampaignDetector()
        result = detector.detect([])
        assert hasattr(result, "is_campaign_detected")
        assert hasattr(result, "campaign_confidence")


class TestTrustScoringService:

    def test_service_initializes(self):
        from services.trust_scoring.service import TrustScoringService
        service = TrustScoringService()
        assert service is not None

    def test_has_score_author(self):
        from services.trust_scoring.service import TrustScoringService
        service = TrustScoringService()
        assert callable(getattr(service, "score_author", None))

    def test_has_analyze_content(self):
        from services.trust_scoring.service import TrustScoringService
        service = TrustScoringService()
        assert callable(getattr(service, "analyze_content", None))

    def test_has_detect_campaign(self):
        from services.trust_scoring.service import TrustScoringService
        service = TrustScoringService()
        assert callable(getattr(service, "detect_campaign", None))

    def test_score_author_returns_result(self):
        from services.trust_scoring.service import TrustScoringService
        service = TrustScoringService()
        profile = _make_profile(username="test_user", account_age_days=500)
        result = service.score_author(profile, "test_user", "reddit")
        assert result is not None
        assert 0.0 <= result.trust_score <= 1.0

    def test_analyze_content_returns_result(self):
        from services.trust_scoring.service import TrustScoringService
        service = TrustScoringService()
        result = service.analyze_content(
            "svc-001",
            "Great product, been using it for weeks.",
        )
        assert result is not None
        assert hasattr(result, "content_quality_score")


        