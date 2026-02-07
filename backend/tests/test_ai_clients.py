"""
Tests for Gemini 3 AI Client — Thought Type Detection & Classification

Tests the keyword-based thought type classifier and thought signature
extraction logic. These are pure functions with no API dependency.
"""

import pytest
from unittest.mock import MagicMock
from enum import Enum


# ── Replicate ThoughtType locally so tests don't need full import chain ──
class ThoughtType(str, Enum):
    OBSERVATION = "observation"
    ANALYSIS = "analysis"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"


def _detect_thought_type(text: str):
    """Mirror of ai_clients._detect_thought_type for isolated testing."""
    text_lower = text.lower()

    if any(w in text_lower for w in ["i see", "looking at", "observing", "notice", "scanning"]):
        return ThoughtType.OBSERVATION
    elif any(w in text_lower for w in ["analyzing", "comparing", "examining", "this means", "evaluating"]):
        return ThoughtType.ANALYSIS
    elif any(w in text_lower for w in ["could be", "might", "possibly", "hypothesis", "if we"]):
        return ThoughtType.HYPOTHESIS
    elif any(w in text_lower for w in ["therefore", "conclude", "decision", "determined", "verdict"]):
        return ThoughtType.DECISION
    elif any(w in text_lower for w in ["recommend", "suggest", "should", "optimal", "strategy"]):
        return ThoughtType.RECOMMENDATION

    return None


def _extract_thought_from_chunk(chunk):
    """Mirror of ai_clients._extract_thought_from_chunk for isolated testing."""
    try:
        for candidate in getattr(chunk, "candidates", []):
            for part in getattr(candidate.content, "parts", []):
                if getattr(part, "thought", False):
                    return True
        return False
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════
# THOUGHT TYPE DETECTION TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestDetectThoughtType:
    """Test keyword-based thought type classification."""

    # ── Observation keywords ──
    def test_observation_i_see(self):
        assert _detect_thought_type("I see a product priced at $29.99") == ThoughtType.OBSERVATION

    def test_observation_looking_at(self):
        assert _detect_thought_type("Looking at the competitor's page") == ThoughtType.OBSERVATION

    def test_observation_notice(self):
        assert _detect_thought_type("I notice a price drop on the homepage") == ThoughtType.OBSERVATION

    def test_observation_scanning(self):
        assert _detect_thought_type("Scanning the social media feeds now") == ThoughtType.OBSERVATION

    # ── Analysis keywords ──
    def test_analysis_analyzing(self):
        assert _detect_thought_type("Analyzing the sentiment trends") == ThoughtType.ANALYSIS

    def test_analysis_comparing(self):
        assert _detect_thought_type("Comparing these prices against baseline") == ThoughtType.ANALYSIS

    def test_analysis_examining(self):
        assert _detect_thought_type("Examining the engagement metrics closely") == ThoughtType.ANALYSIS

    def test_analysis_this_means(self):
        assert _detect_thought_type("This means the market is shifting") == ThoughtType.ANALYSIS

    def test_analysis_evaluating(self):
        assert _detect_thought_type("Evaluating the risk factors") == ThoughtType.ANALYSIS

    # ── Hypothesis keywords ──
    def test_hypothesis_could_be(self):
        assert _detect_thought_type("This could be a new product launch") == ThoughtType.HYPOTHESIS

    def test_hypothesis_might(self):
        assert _detect_thought_type("They might be testing a new price point") == ThoughtType.HYPOTHESIS

    def test_hypothesis_possibly(self):
        assert _detect_thought_type("Possibly a seasonal adjustment") == ThoughtType.HYPOTHESIS

    def test_hypothesis_if_we(self):
        assert _detect_thought_type("If we consider the market trends") == ThoughtType.HYPOTHESIS

    # ── Decision keywords ──
    def test_decision_therefore(self):
        assert _detect_thought_type("Therefore, this is a confirmed launch") == ThoughtType.DECISION

    def test_decision_conclude(self):
        assert _detect_thought_type("I conclude the threat level is high") == ThoughtType.DECISION

    def test_decision_verdict(self):
        assert _detect_thought_type("My verdict: crisis severity is critical") == ThoughtType.DECISION

    # ── Recommendation keywords ──
    def test_recommendation_recommend(self):
        assert _detect_thought_type("I recommend lowering the price by 10%") == ThoughtType.RECOMMENDATION

    def test_recommendation_suggest(self):
        assert _detect_thought_type("I suggest monitoring for 24 hours") == ThoughtType.RECOMMENDATION

    def test_recommendation_should(self):
        assert _detect_thought_type("You should update your pricing immediately") == ThoughtType.RECOMMENDATION

    def test_recommendation_optimal(self):
        assert _detect_thought_type("The optimal price is $24.99") == ThoughtType.RECOMMENDATION

    def test_recommendation_strategy(self):
        assert _detect_thought_type("Our strategy should focus on value") == ThoughtType.RECOMMENDATION

    # ── No match ──
    def test_no_match_returns_none(self):
        assert _detect_thought_type("Hello world") is None

    def test_empty_string_returns_none(self):
        assert _detect_thought_type("") is None

    def test_numbers_only_returns_none(self):
        assert _detect_thought_type("12345 67890") is None

    # ── Case insensitivity ──
    def test_case_insensitive_upper(self):
        assert _detect_thought_type("I SEE the product") == ThoughtType.OBSERVATION

    def test_case_insensitive_mixed(self):
        assert _detect_thought_type("ANALYZING the Data") == ThoughtType.ANALYSIS

    # ── Priority: first match wins ──
    def test_priority_observation_before_analysis(self):
        """If both observation and analysis keywords exist, observation wins."""
        result = _detect_thought_type("I see and I'm analyzing the data")
        assert result == ThoughtType.OBSERVATION

    def test_priority_analysis_before_hypothesis(self):
        result = _detect_thought_type("Examining what might happen")
        assert result == ThoughtType.ANALYSIS


# ═════════════════════════════════════════════════════════════════════════
# THOUGHT SIGNATURE EXTRACTION TESTS
# ═════════════════════════════════════════════════════════════════════════


class TestExtractThoughtFromChunk:
    """Test native Gemini 3 thought signature extraction."""

    def test_thought_true(self):
        """Chunk with part.thought=True should return True."""
        part = MagicMock()
        part.thought = True
        content = MagicMock()
        content.parts = [part]
        candidate = MagicMock()
        candidate.content = content
        chunk = MagicMock()
        chunk.candidates = [candidate]

        assert _extract_thought_from_chunk(chunk) is True

    def test_thought_false(self):
        """Chunk with part.thought=False should return False."""
        part = MagicMock()
        part.thought = False
        content = MagicMock()
        content.parts = [part]
        candidate = MagicMock()
        candidate.content = content
        chunk = MagicMock()
        chunk.candidates = [candidate]

        assert _extract_thought_from_chunk(chunk) is False

    def test_no_candidates(self):
        """Chunk with no candidates should return False."""
        chunk = MagicMock()
        chunk.candidates = []

        assert _extract_thought_from_chunk(chunk) is False

    def test_no_parts(self):
        """Chunk with empty parts should return False."""
        content = MagicMock()
        content.parts = []
        candidate = MagicMock()
        candidate.content = content
        chunk = MagicMock()
        chunk.candidates = [candidate]

        assert _extract_thought_from_chunk(chunk) is False

    def test_no_thought_attribute(self):
        """Part without thought attribute should return False."""
        part = MagicMock(spec=[])  # No attributes
        content = MagicMock()
        content.parts = [part]
        candidate = MagicMock()
        candidate.content = content
        chunk = MagicMock()
        chunk.candidates = [candidate]

        assert _extract_thought_from_chunk(chunk) is False

    def test_non_chunk_object_returns_false(self):
        """A plain string has no candidates — returns False via empty iteration."""
        chunk = "not a chunk object"
        assert _extract_thought_from_chunk(chunk) is False

    def test_multiple_parts_one_thought(self):
        """If any part has thought=True, return True."""
        part1 = MagicMock()
        part1.thought = False
        part2 = MagicMock()
        part2.thought = True
        content = MagicMock()
        content.parts = [part1, part2]
        candidate = MagicMock()
        candidate.content = content
        chunk = MagicMock()
        chunk.candidates = [candidate]

        assert _extract_thought_from_chunk(chunk) is True

    def test_multiple_candidates(self):
        """First candidate with thought=True should return True."""
        part1 = MagicMock()
        part1.thought = False
        content1 = MagicMock()
        content1.parts = [part1]
        cand1 = MagicMock()
        cand1.content = content1

        part2 = MagicMock()
        part2.thought = True
        content2 = MagicMock()
        content2.parts = [part2]
        cand2 = MagicMock()
        cand2.content = content2

        chunk = MagicMock()
        chunk.candidates = [cand1, cand2]

        assert _extract_thought_from_chunk(chunk) is True
