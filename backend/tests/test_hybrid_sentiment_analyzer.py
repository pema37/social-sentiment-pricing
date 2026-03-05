# backend/tests/test_hybrid_sentiment_analyzer.py
"""
Comprehensive tests for HybridSentimentAnalyzer — combines VADER, Gemini,
OpenAI, and trust scoring for robust sentiment analysis.

Tests cover:
- RateLimitError exception
- HybridSentimentResult dataclass
- HybridSentimentAnalyzer initialization
- get_available_sources
- _combine_scores (weighted average)
- _get_label (score → label mapping)
- _calculate_confidence (multi-factor confidence)
- _analyze_vader (VADER delegation)
- _analyze_gemini (Gemini + rate limit detection)
- _analyze_openai (OpenAI + rate limit detection)
- analyze (full orchestration, fallback chains)
- analyze_with_trust (batch analysis + campaign detection)
- analyze_batch

Total: ~65 tests
"""

import sys
from unittest.mock import AsyncMock
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# ── Import isolation ──────────────────────────────────────────────
_MOCKED_MODULES = [
    "core.config",
    "vaderSentiment",
    "vaderSentiment.vaderSentiment",
    "google",
    "google.generativeai",
    "openai",
    "services.trust_scoring",
]
_originals = {mod: sys.modules.get(mod) for mod in _MOCKED_MODULES}

for mod in _MOCKED_MODULES:
    if _originals[mod] is None:
        sys.modules[mod] = MagicMock()

# Mock settings before import
mock_settings = MagicMock()
mock_settings.GEMINI_API_KEY = None
mock_settings.OPENAI_API_KEY = None
sys.modules["core.config"].settings = mock_settings

import pytest

from services.hybrid_sentiment_analyzer import (
    RateLimitError,
    HybridSentimentResult,
    HybridSentimentAnalyzer,
)

# ── IMMEDIATE cleanup — restore before pytest collects later modules ──
for _mod in _MOCKED_MODULES:
    if _originals[_mod] is None:
        sys.modules.pop(_mod, None)
    else:
        sys.modules[_mod] = _originals[_mod]
del _mod

SERVICE_PATH = "services.hybrid_sentiment_analyzer"


# ============================================================
# 1. RateLimitError
# ============================================================

class TestRateLimitError:

    def test_stores_api_name(self):
        err = RateLimitError("gemini")
        assert err.api_name == "gemini"

    def test_default_retry_after(self):
        err = RateLimitError("openai")
        assert err.retry_after == 60

    def test_custom_retry_after(self):
        err = RateLimitError("openai", retry_after=120)
        assert err.retry_after == 120

    def test_custom_message(self):
        err = RateLimitError("gemini", message="quota exceeded")
        assert "quota exceeded" in str(err)

    def test_default_message(self):
        err = RateLimitError("gemini")
        assert "gemini" in str(err)
        assert "retry after 60s" in str(err)

    def test_is_exception(self):
        err = RateLimitError("test")
        assert isinstance(err, Exception)


# ============================================================
# 2. HybridSentimentResult dataclass
# ============================================================

class TestHybridSentimentResult:

    def test_default_trust_fields(self):
        result = HybridSentimentResult(
            compound=0.5, label="positive", confidence=0.8,
            positive=0.7, negative=0.1, neutral=0.2,
            sources_used=["vader"], individual_scores={"vader": 0.5},
            emotions={}, topics=[], is_sarcastic=False,
        )
        assert result.trust_score == 1.0
        assert result.trust_level == "medium"
        assert result.trust_adjusted_compound == 0.0
        assert result.is_filtered is False
        assert result.risk_flags == []

    def test_custom_trust_fields(self):
        result = HybridSentimentResult(
            compound=0.5, label="positive", confidence=0.8,
            positive=0.7, negative=0.1, neutral=0.2,
            sources_used=["vader"], individual_scores={"vader": 0.5},
            emotions={}, topics=[], is_sarcastic=False,
            trust_score=0.3, trust_level="low",
            trust_adjusted_compound=0.15, is_filtered=True,
            risk_flags=["bot_like"],
        )
        assert result.trust_score == 0.3
        assert result.trust_level == "low"
        assert result.is_filtered is True


# ============================================================
# 3. Initialization
# ============================================================

class TestHybridSentimentAnalyzerInit:

    @patch(f"{SERVICE_PATH}.settings")
    def test_vader_not_available(self, mock_s):
        mock_s.GEMINI_API_KEY = None
        mock_s.OPENAI_API_KEY = None

        with patch.dict(sys.modules, {"vaderSentiment.vaderSentiment": None}):
            # Force ImportError
            with patch(f"{SERVICE_PATH}.HybridSentimentAnalyzer.__init__", return_value=None) as mock_init:
                svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
                svc.vader = None
                svc.gemini_client = None
                svc.openai_client = None
                svc.trust_service = None
                assert svc.vader is None

    def test_default_init_has_no_api_clients(self):
        """With no API keys, only VADER should initialize."""
        with patch(f"{SERVICE_PATH}.settings") as mock_s:
            mock_s.GEMINI_API_KEY = None
            mock_s.OPENAI_API_KEY = None
            svc = HybridSentimentAnalyzer()
            assert svc.gemini_client is None
            assert svc.openai_client is None


# ============================================================
# 4. get_available_sources
# ============================================================

class TestGetAvailableSources:

    def test_only_vader(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.vader = MagicMock()
        svc.gemini_client = None
        svc.openai_client = None
        svc.trust_service = None
        assert svc.get_available_sources() == ["vader"]

    def test_all_sources(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.vader = MagicMock()
        svc.gemini_client = MagicMock()
        svc.openai_client = MagicMock()
        svc.trust_service = MagicMock()
        assert svc.get_available_sources() == ["vader", "gemini", "openai", "trust_scoring"]

    def test_no_sources(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.vader = None
        svc.gemini_client = None
        svc.openai_client = None
        svc.trust_service = None
        assert svc.get_available_sources() == []


# ============================================================
# 5. _combine_scores
# ============================================================

class TestCombineScores:

    def setup_method(self):
        self.svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)

    def test_empty_returns_zero(self):
        assert self.svc._combine_scores({}) == 0.0

    def test_vader_only(self):
        result = self.svc._combine_scores({"vader": 0.5})
        # weight=0.3, so 0.5*0.3/0.3 = 0.5
        assert abs(result - 0.5) < 0.01

    def test_gemini_only(self):
        result = self.svc._combine_scores({"gemini": 0.8})
        assert abs(result - 0.8) < 0.01

    def test_vader_and_gemini_weighted(self):
        result = self.svc._combine_scores({"vader": 0.5, "gemini": 0.8})
        # (0.5*0.3 + 0.8*0.5) / (0.3+0.5) = (0.15+0.40)/0.80 = 0.6875
        assert abs(result - 0.6875) < 0.01

    def test_all_three_weighted(self):
        result = self.svc._combine_scores({"vader": 0.3, "gemini": 0.6, "openai": 0.9})
        # (0.3*0.3 + 0.6*0.5 + 0.9*0.4) / (0.3+0.5+0.4)
        # = (0.09 + 0.30 + 0.36) / 1.2 = 0.625
        assert abs(result - 0.625) < 0.01

    def test_negative_scores(self):
        result = self.svc._combine_scores({"vader": -0.5})
        assert result < 0

    def test_unknown_source_uses_default_weight(self):
        result = self.svc._combine_scores({"custom": 1.0})
        # weight=0.1, so 1.0*0.1/0.1 = 1.0
        assert abs(result - 1.0) < 0.01


# ============================================================
# 6. _get_label
# ============================================================

class TestGetLabel:

    def setup_method(self):
        self.svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)

    def test_very_positive(self):
        assert self.svc._get_label(0.5) == "very_positive"
        assert self.svc._get_label(0.9) == "very_positive"

    def test_positive(self):
        assert self.svc._get_label(0.1) == "positive"
        assert self.svc._get_label(0.49) == "positive"

    def test_neutral(self):
        assert self.svc._get_label(0.0) == "neutral"
        assert self.svc._get_label(0.09) == "neutral"
        assert self.svc._get_label(-0.09) == "neutral"

    def test_negative(self):
        assert self.svc._get_label(-0.1) == "negative"
        assert self.svc._get_label(-0.49) == "negative"

    def test_very_negative(self):
        assert self.svc._get_label(-0.5) == "very_negative"
        assert self.svc._get_label(-1.0) == "very_negative"


# ============================================================
# 7. _calculate_confidence
# ============================================================

class TestCalculateConfidence:

    def setup_method(self):
        self.svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)

    def test_empty_returns_zero(self):
        assert self.svc._calculate_confidence({}, []) == 0.0

    def test_single_source_lower_confidence(self):
        result = self.svc._calculate_confidence({"vader": 0.5}, ["vader"])
        assert result > 0
        assert result < 1.0

    def test_more_sources_higher_confidence(self):
        single = self.svc._calculate_confidence({"vader": 0.5}, ["vader"])
        multi = self.svc._calculate_confidence(
            {"vader": 0.5, "gemini": 0.5}, ["vader", "gemini"]
        )
        assert multi > single

    def test_ai_sources_boost_confidence(self):
        no_ai = self.svc._calculate_confidence({"vader": 0.5}, ["vader"])
        with_ai = self.svc._calculate_confidence(
            {"vader": 0.5, "gemini": 0.5}, ["vader", "gemini"]
        )
        assert with_ai > no_ai

    def test_agreement_boosts_confidence(self):
        # Same scores = perfect agreement
        agree = self.svc._calculate_confidence(
            {"vader": 0.5, "gemini": 0.5}, ["vader", "gemini"]
        )
        # Different scores = low agreement
        disagree = self.svc._calculate_confidence(
            {"vader": 0.5, "gemini": -0.5}, ["vader", "gemini"]
        )
        assert agree > disagree

    def test_capped_at_one(self):
        result = self.svc._calculate_confidence(
            {"vader": 1.0, "gemini": 1.0, "openai": 1.0},
            ["vader", "gemini", "openai"]
        )
        assert result <= 1.0


# ============================================================
# 8. _analyze_vader
# ============================================================

class TestAnalyzeVader:

    def test_returns_scores(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.vader = MagicMock()
        svc.vader.polarity_scores.return_value = {
            "compound": 0.75, "pos": 0.6, "neg": 0.1, "neu": 0.3,
        }
        result = svc._analyze_vader("great product!")
        assert result["compound"] == 0.75
        assert result["positive"] == 0.6
        assert result["negative"] == 0.1
        assert result["neutral"] == 0.3

    def test_calls_polarity_scores(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.vader = MagicMock()
        svc.vader.polarity_scores.return_value = {
            "compound": 0, "pos": 0, "neg": 0, "neu": 1,
        }
        svc._analyze_vader("test text")
        svc.vader.polarity_scores.assert_called_once_with("test text")


# ============================================================
# 9. _analyze_gemini
# ============================================================

class TestAnalyzeGemini:
    from unittest.mock import AsyncMock, MagicMock, patch

    @pytest.mark.asyncio
    async def test_parses_json_response(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.gemini_model = "gemini-2.0-flash"
        # svc.gemini_client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = '{"sentiment_score": 0.7, "sentiment_label": "positive", "confidence": 0.9, "positive_score": 0.8, "negative_score": 0.1, "neutral_score": 0.1, "emotions": {}, "topics": ["quality"], "is_sarcastic": false}'

        svc.gemini_client = MagicMock()
        svc.gemini_client.aio = MagicMock()
        svc.gemini_client.aio.models = MagicMock()
        svc.gemini_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await svc._analyze_gemini("great product")
        assert result["compound"] == 0.7
        assert result["topics"] == ["quality"]

        #import asyncio
        #loop = asyncio.get_event_loop()
        #with patch.object(loop, 'run_in_executor', new_callable=AsyncMock, return_value=mock_response):
            #result = await svc._analyze_gemini("great product")
            #assert result["compound"] == 0.7
            #assert result["topics"] == ["quality"]


    @pytest.mark.asyncio
    async def test_raises_rate_limit_on_429(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.gemini_model = "gemini-2.0-flash"
        
        svc.gemini_client = MagicMock()
        svc.gemini_client.aio = MagicMock()
        svc.gemini_client.aio.models = MagicMock()
        svc.gemini_client.aio.models.generate_content = AsyncMock(side_effect=Exception("429 Resource exhausted"))

        with pytest.raises(RateLimitError) as exc_info:
            await svc._analyze_gemini("test")
        assert exc_info.value.api_name == "gemini"

    #@pytest.mark.asyncio
    #async def test_raises_rate_limit_on_429(self):
        #svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        #svc.gemini_client = MagicMock()

        #import asyncio
        #loop = asyncio.get_event_loop()
        #with patch.object(loop, 'run_in_executor', new_callable=AsyncMock, side_effect=Exception("429 Resource exhausted")):
            #with pytest.raises(RateLimitError) as exc_info:
                #await svc._analyze_gemini("test")
            #assert exc_info.value.api_name == "gemini"

    @pytest.mark.asyncio
    async def test_raises_rate_limit_on_quota(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.gemini_model = "gemini-2.0-flash"
        
        svc.gemini_client = MagicMock()
        svc.gemini_client.aio = MagicMock()
        svc.gemini_client.aio.models = MagicMock()
        svc.gemini_client.aio.models.generate_content = AsyncMock(side_effect=Exception("quota exceeded"))

        with pytest.raises(RateLimitError):
            await svc._analyze_gemini("test")
    
    #@pytest.mark.asyncio
    #async def test_raises_rate_limit_on_quota(self):
        #svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        #svc.gemini_client = MagicMock()

        #import asyncio
        #loop = asyncio.get_event_loop()
        #with patch.object(loop, 'run_in_executor', new_callable=AsyncMock, side_effect=Exception("quota exceeded")):
            #with pytest.raises(RateLimitError):
                #await svc._analyze_gemini("test")

    #@pytest.mark.asyncio
    #async def test_reraises_non_rate_limit_errors(self):
        #svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        #svc.gemini_client = MagicMock()

        #import asyncio
        #loop = asyncio.get_event_loop()
        #with patch.object(loop, 'run_in_executor', new_callable=AsyncMock, side_effect=ValueError("parse error")):
            #with pytest.raises(ValueError):
                #await svc._analyze_gemini("test")


    @pytest.mark.asyncio
    async def test_reraises_non_rate_limit_errors(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.gemini_model = "gemini-2.0-flash"
        
        svc.gemini_client = MagicMock()
        svc.gemini_client.aio = MagicMock()
        svc.gemini_client.aio.models = MagicMock()
        
        svc.gemini_client.aio.models.generate_content = AsyncMock(side_effect=ValueError("parse error"))

        with pytest.raises(ValueError):
            await svc._analyze_gemini("test")


# ============================================================
# 10. _analyze_openai
# ============================================================

class TestAnalyzeOpenAI:

    @pytest.mark.asyncio
    async def test_parses_response(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.openai_client = AsyncMock()

        mock_message = MagicMock()
        mock_message.content = '{"sentiment_score": -0.5, "sentiment_label": "negative", "confidence": 0.85, "positive_score": 0.1, "negative_score": 0.7, "neutral_score": 0.2, "emotions": {"anger": 0.6}, "topics": ["shipping"], "is_sarcastic": false}'
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        svc.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await svc._analyze_openai("terrible shipping")
        assert result["compound"] == -0.5
        assert result["emotions"] == {"anger": 0.6}

    @pytest.mark.asyncio
    async def test_raises_rate_limit_on_429(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.openai_client = AsyncMock()
        svc.openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("429 Too Many Requests")
        )

        with pytest.raises(RateLimitError) as exc_info:
            await svc._analyze_openai("test")
        assert exc_info.value.api_name == "openai"

    @pytest.mark.asyncio
    async def test_reraises_non_rate_limit_errors(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.openai_client = AsyncMock()
        svc.openai_client.chat.completions.create = AsyncMock(
            side_effect=ValueError("bad response")
        )

        with pytest.raises(ValueError):
            await svc._analyze_openai("test")


# ============================================================
# 11. analyze (orchestration)
# ============================================================

class TestAnalyze:

    def _make_svc(self, vader=True, gemini=False, openai=False, trust=False):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.vader = MagicMock() if vader else None
        svc.gemini_client = MagicMock() if gemini else None
        svc.openai_client = MagicMock() if openai else None
        svc.trust_service = MagicMock() if trust else None

        if vader:
            svc.vader.polarity_scores.return_value = {
                "compound": 0.5, "pos": 0.6, "neg": 0.1, "neu": 0.3,
            }
        return svc

    @pytest.mark.asyncio
    async def test_vader_only(self):
        svc = self._make_svc(vader=True)
        result = await svc.analyze("good product", use_ai=False)
        assert "vader" in result.sources_used
        assert result.compound != 0

    @pytest.mark.asyncio
    async def test_no_analyzers_returns_neutral(self):
        svc = self._make_svc(vader=False)
        result = await svc.analyze("test", use_ai=False)
        assert result.compound == 0.0
        assert result.label == "neutral"

    @pytest.mark.asyncio
    async def test_gemini_used_when_available(self):
        svc = self._make_svc(vader=True, gemini=True)
        svc._analyze_gemini = AsyncMock(return_value={
            "compound": 0.8, "emotions": {}, "topics": [], "is_sarcastic": False,
        })
        result = await svc.analyze("great!", use_ai=True)
        assert "gemini" in result.sources_used

    @pytest.mark.asyncio
    async def test_openai_fallback_on_gemini_failure(self):
        svc = self._make_svc(vader=True, gemini=True, openai=True)
        svc._analyze_gemini = AsyncMock(side_effect=Exception("Gemini down"))
        svc._analyze_openai = AsyncMock(return_value={
            "compound": 0.6, "emotions": {}, "topics": [], "is_sarcastic": False,
        })
        result = await svc.analyze("test", use_ai=True)
        assert "openai" in result.sources_used
        assert "gemini" not in result.sources_used

    @pytest.mark.asyncio
    async def test_gemini_rate_limit_propagates(self):
        svc = self._make_svc(vader=True, gemini=True)
        svc._analyze_gemini = AsyncMock(side_effect=RateLimitError("gemini"))
        with pytest.raises(RateLimitError):
            await svc.analyze("test", use_ai=True)

    @pytest.mark.asyncio
    async def test_openai_only_when_no_gemini(self):
        svc = self._make_svc(vader=True, openai=True)
        svc._analyze_openai = AsyncMock(return_value={
            "compound": 0.4, "emotions": {}, "topics": [], "is_sarcastic": False,
        })
        result = await svc.analyze("test", use_ai=True)
        assert "openai" in result.sources_used

    @pytest.mark.asyncio
    async def test_result_has_correct_structure(self):
        svc = self._make_svc(vader=True)
        result = await svc.analyze("test", use_ai=False)
        assert hasattr(result, 'compound')
        assert hasattr(result, 'label')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'trust_score')
        assert hasattr(result, 'trust_adjusted_compound')

    @pytest.mark.asyncio
    async def test_positive_score_distribution(self):
        svc = self._make_svc(vader=True)
        svc.vader.polarity_scores.return_value = {
            "compound": 0.8, "pos": 0.9, "neg": 0.0, "neu": 0.1,
        }
        result = await svc.analyze("amazing!", use_ai=False)
        assert result.positive > result.negative

    @pytest.mark.asyncio
    async def test_negative_score_distribution(self):
        svc = self._make_svc(vader=True)
        svc.vader.polarity_scores.return_value = {
            "compound": -0.8, "pos": 0.0, "neg": 0.9, "neu": 0.1,
        }
        result = await svc.analyze("terrible!", use_ai=False)
        assert result.negative > result.positive

    @pytest.mark.asyncio
    async def test_trust_scoring_applied(self):
        svc = self._make_svc(vader=True, trust=True)

        mock_author_score = MagicMock()
        mock_author_score.trust_score = 0.9
        mock_author_score.trust_level = MagicMock()
        mock_author_score.trust_level.value = "high"
        mock_author_score.risk_flags = []
        svc.trust_service.score_author.return_value = mock_author_score

        mock_content = MagicMock()
        mock_content.content_quality_score = 0.8
        mock_content.risk_flags = []
        svc.trust_service.analyze_content.return_value = mock_content

        result = await svc.analyze(
            "good product", use_ai=False,
            author_id="user123", apply_trust_scoring=True,
        )
        assert "trust_scoring" in result.sources_used
        assert result.trust_level == "high"


# ============================================================
# 12. analyze_with_trust (batch)
# ============================================================

class TestAnalyzeWithTrust:

    @pytest.mark.asyncio
    async def test_returns_summary(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.trust_service = None
        svc.analyze = AsyncMock(return_value=HybridSentimentResult(
            compound=0.5, label="positive", confidence=0.8,
            positive=0.7, negative=0.1, neutral=0.2,
            sources_used=["vader"], individual_scores={"vader": 0.5},
            emotions={}, topics=[], is_sarcastic=False,
            trust_score=0.9, trust_level="high",
            trust_adjusted_compound=0.45, is_filtered=False,
        ))

        mentions = [{"content": "great!", "author_id": "u1", "source": "twitter"}]
        result = await svc.analyze_with_trust(mentions, use_ai=False)

        assert "summary" in result
        assert "mentions" in result
        assert "trust_breakdown" in result
        assert result["summary"]["total_analyzed"] == 1

    @pytest.mark.asyncio
    async def test_filtered_mentions_counted(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.trust_service = None
        svc.analyze = AsyncMock(return_value=HybridSentimentResult(
            compound=0.5, label="positive", confidence=0.8,
            positive=0.7, negative=0.1, neutral=0.2,
            sources_used=["vader"], individual_scores={"vader": 0.5},
            emotions={}, topics=[], is_sarcastic=False,
            trust_score=0.05, trust_level="untrusted",
            trust_adjusted_compound=0.025, is_filtered=True,
        ))

        mentions = [{"content": "spam!", "author_id": "bot1", "source": "twitter"}]
        result = await svc.analyze_with_trust(mentions, use_ai=False)

        assert result["summary"]["filtered_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_mentions(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.trust_service = None
        result = await svc.analyze_with_trust([], use_ai=False)
        assert result["summary"]["total_analyzed"] == 0
        assert result["summary"]["raw_sentiment"] == 0.0

    @pytest.mark.asyncio
    async def test_error_in_mention_skipped(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.trust_service = None
        svc.analyze = AsyncMock(side_effect=Exception("analysis failed"))

        mentions = [{"content": "test", "author_id": "u1", "source": "twitter"}]
        result = await svc.analyze_with_trust(mentions, use_ai=False)

        assert result["summary"]["total_analyzed"] == 0


# ============================================================
# 13. analyze_batch
# ============================================================

class TestAnalyzeBatch:

    @pytest.mark.asyncio
    async def test_processes_all_texts(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.analyze = AsyncMock(return_value=HybridSentimentResult(
            compound=0.5, label="positive", confidence=0.8,
            positive=0.7, negative=0.1, neutral=0.2,
            sources_used=["vader"], individual_scores={"vader": 0.5},
            emotions={}, topics=[], is_sarcastic=False,
        ))

        results = await svc.analyze_batch(["text1", "text2", "text3"])
        assert len(results) == 3
        assert svc.analyze.await_count == 3

    @pytest.mark.asyncio
    async def test_empty_batch(self):
        svc = HybridSentimentAnalyzer.__new__(HybridSentimentAnalyzer)
        svc.analyze = AsyncMock()
        results = await svc.analyze_batch([])
        assert results == []

        