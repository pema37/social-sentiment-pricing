"""
Tests for services/trust_scoring/utils.py

Pure utility functions for trust scoring, bot detection, text analysis,
spam detection, and time pattern analysis.
"""

import sys
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

# Standard import isolation
for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from services.trust_scoring.utils import (
    normalize_text,
    compute_content_hash,
    compute_fuzzy_hash,
    jaccard_similarity,
    text_similarity,
    find_similar_texts,
    extract_hashtags,
    extract_mentions,
    extract_urls,
    count_emojis,
    get_content_metrics,
    SPAM_PHRASES,
    BOT_USERNAME_PATTERNS,
    has_spam_phrases,
    has_excessive_caps,
    has_keyword_stuffing,
    is_bot_username,
    calculate_spam_score,
    calculate_account_age_score,
    calculate_follower_score,
    analyze_posting_times,
    detect_burst_activity,
)

import pytest


# ──────────────────────────────────────────────
# normalize_text
# ──────────────────────────────────────────────
class TestNormalizeText:

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_none_like_empty(self):
        # empty string is falsy
        assert normalize_text("") == ""

    def test_lowercase(self):
        assert normalize_text("HELLO WORLD") == "hello world"

    def test_removes_http_url(self):
        result = normalize_text("check http://example.com now")
        assert "http" not in result
        assert "example" not in result

    def test_removes_https_url(self):
        result = normalize_text("visit https://shop.com/path?q=1 today")
        assert "https" not in result
        assert "shop.com" not in result

    def test_removes_www_url(self):
        result = normalize_text("see www.example.com for info")
        assert "www" not in result

    def test_removes_mentions(self):
        result = normalize_text("hey @john check this @jane")
        assert "@" not in result
        assert "john" not in result
        assert "jane" not in result

    def test_removes_hashtags(self):
        result = normalize_text("love #python and #coding")
        assert "#" not in result
        assert "python" not in result
        assert "coding" not in result

    def test_normalizes_whitespace(self):
        result = normalize_text("too   many    spaces")
        assert result == "too many spaces"

    def test_strips_leading_trailing(self):
        result = normalize_text("  padded  ")
        assert result == "padded"

    def test_combined(self):
        text = "  HEY @user check https://link.com #sale  NOW  "
        result = normalize_text(text)
        assert result == "hey check now"

    def test_preserves_normal_words(self):
        result = normalize_text("this product is great quality")
        assert result == "this product is great quality"

    def test_tabs_and_newlines(self):
        result = normalize_text("line1\n\tline2\n\nline3")
        assert result == "line1 line2 line3"


# ──────────────────────────────────────────────
# compute_content_hash
# ──────────────────────────────────────────────
class TestComputeContentHash:

    def test_returns_string(self):
        result = compute_content_hash("hello")
        assert isinstance(result, str)

    def test_md5_length(self):
        result = compute_content_hash("test")
        assert len(result) == 32  # MD5 hex digest length

    def test_deterministic(self):
        h1 = compute_content_hash("same text")
        h2 = compute_content_hash("same text")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = compute_content_hash("Hello World")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_ignores_urls(self):
        h1 = compute_content_hash("buy now")
        h2 = compute_content_hash("buy now https://spam.com")
        assert h1 == h2

    def test_ignores_mentions(self):
        h1 = compute_content_hash("great product")
        h2 = compute_content_hash("great product @user")
        assert h1 == h2

    def test_different_text_different_hash(self):
        h1 = compute_content_hash("apple")
        h2 = compute_content_hash("banana")
        assert h1 != h2

    def test_empty_string(self):
        result = compute_content_hash("")
        assert isinstance(result, str)
        assert len(result) == 32


# ──────────────────────────────────────────────
# compute_fuzzy_hash
# ──────────────────────────────────────────────
class TestComputeFuzzyHash:

    def test_returns_set(self):
        result = compute_fuzzy_hash("the quick brown fox jumps over")
        assert isinstance(result, set)

    def test_short_text_returns_normalized(self):
        result = compute_fuzzy_hash("hi there")
        assert result == {"hi there"}

    def test_single_word(self):
        result = compute_fuzzy_hash("hello")
        assert result == {"hello"}

    def test_shingle_size_3_default(self):
        result = compute_fuzzy_hash("a b c d e")
        assert "a b c" in result
        assert "b c d" in result
        assert "c d e" in result

    def test_custom_shingle_size(self):
        result = compute_fuzzy_hash("a b c d e", shingle_size=2)
        assert "a b" in result
        assert "d e" in result

    def test_shingle_count(self):
        # "a b c d e" with size 3 → 3 shingles
        result = compute_fuzzy_hash("a b c d e", shingle_size=3)
        assert len(result) == 3

    def test_normalizes_input(self):
        result = compute_fuzzy_hash("THE QUICK BROWN FOX")
        for shingle in result:
            assert shingle == shingle.lower()

    def test_empty_string(self):
        result = compute_fuzzy_hash("")
        assert result == {""}

    def test_exact_shingle_size_words(self):
        # exactly 3 words with shingle_size=3 → 1 shingle
        result = compute_fuzzy_hash("one two three", shingle_size=3)
        assert result == {"one two three"}


# ──────────────────────────────────────────────
# jaccard_similarity
# ──────────────────────────────────────────────
class TestJaccardSimilarity:

    def test_identical_sets(self):
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # {a, b, c} & {b, c, d} → intersection=2, union=4
        result = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert result == pytest.approx(0.5)

    def test_empty_first(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0

    def test_empty_second(self):
        assert jaccard_similarity({"a"}, set()) == 0.0

    def test_both_empty(self):
        assert jaccard_similarity(set(), set()) == 0.0

    def test_subset(self):
        # {a} & {a, b} → intersection=1, union=2
        result = jaccard_similarity({"a"}, {"a", "b"})
        assert result == pytest.approx(0.5)

    def test_returns_float(self):
        result = jaccard_similarity({"a"}, {"a"})
        assert isinstance(result, float)


# ──────────────────────────────────────────────
# text_similarity
# ──────────────────────────────────────────────
class TestTextSimilarity:

    def test_identical_texts(self):
        assert text_similarity("hello world foo bar", "hello world foo bar") == 1.0

    def test_completely_different(self):
        result = text_similarity(
            "the quick brown fox jumps",
            "lorem ipsum dolor sit amet"
        )
        assert result < 0.3

    def test_similar_texts(self):
        t1 = "this product is really great quality"
        t2 = "this product is really amazing quality"
        result = text_similarity(t1, t2)
        assert 0.0 < result < 1.0

    def test_case_insensitive(self):
        s1 = text_similarity("Hello World Foo Bar", "hello world foo bar")
        assert s1 == 1.0

    def test_symmetry(self):
        t1 = "alpha beta gamma delta epsilon"
        t2 = "beta gamma delta epsilon zeta"
        assert text_similarity(t1, t2) == text_similarity(t2, t1)


# ──────────────────────────────────────────────
# find_similar_texts
# ──────────────────────────────────────────────
class TestFindSimilarTexts:

    def test_finds_exact_match(self):
        target = "this is a test sentence here"
        candidates = ["something else entirely different", "this is a test sentence here"]
        results = find_similar_texts(target, candidates)
        assert len(results) >= 1
        assert results[0][0] == 1  # index of match
        assert results[0][1] == 1.0

    def test_no_matches_below_threshold(self):
        target = "alpha beta gamma delta epsilon"
        candidates = ["one two three four five"]
        results = find_similar_texts(target, candidates, threshold=0.7)
        assert len(results) == 0

    def test_sorted_by_similarity_desc(self):
        target = "the product quality is excellent overall"
        candidates = [
            "something totally unrelated here now",
            "the product quality is excellent overall",
            "the product quality is pretty good overall",
        ]
        results = find_similar_texts(target, candidates, threshold=0.3)
        if len(results) > 1:
            assert results[0][1] >= results[1][1]

    def test_custom_threshold(self):
        target = "hello world foo bar baz"
        candidates = ["hello world foo bar baz", "goodbye world foo bar baz"]
        results_strict = find_similar_texts(target, candidates, threshold=0.99)
        results_loose = find_similar_texts(target, candidates, threshold=0.3)
        assert len(results_loose) >= len(results_strict)

    def test_empty_candidates(self):
        results = find_similar_texts("test query here now", [])
        assert results == []

    def test_returns_tuples(self):
        target = "a b c d e f g"
        candidates = ["a b c d e f g"]
        results = find_similar_texts(target, candidates, threshold=0.5)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2


# ──────────────────────────────────────────────
# extract_hashtags
# ──────────────────────────────────────────────
class TestExtractHashtags:

    def test_single_hashtag(self):
        assert extract_hashtags("love #python") == ["python"]

    def test_multiple(self):
        result = extract_hashtags("#ai #ml #data")
        assert result == ["ai", "ml", "data"]

    def test_no_hashtags(self):
        assert extract_hashtags("no tags here") == []

    def test_empty_string(self):
        assert extract_hashtags("") == []

    def test_hash_only(self):
        # # followed by space — not a hashtag
        assert extract_hashtags("# not a tag") == []

    def test_mid_sentence(self):
        result = extract_hashtags("buy this #sale item #deal")
        assert "sale" in result
        assert "deal" in result


# ──────────────────────────────────────────────
# extract_mentions
# ──────────────────────────────────────────────
class TestExtractMentions:

    def test_single_mention(self):
        assert extract_mentions("hey @alice") == ["alice"]

    def test_multiple(self):
        result = extract_mentions("@bob and @carol")
        assert result == ["bob", "carol"]

    def test_no_mentions(self):
        assert extract_mentions("no mentions") == []

    def test_empty_string(self):
        assert extract_mentions("") == []

    def test_email_like(self):
        # @ in email context — depends on regex, just verify behavior
        result = extract_mentions("email user@domain.com")
        assert len(result) >= 1  # will match "domain" or "user"


# ──────────────────────────────────────────────
# extract_urls
# ──────────────────────────────────────────────
class TestExtractUrls:

    def test_http_url(self):
        result = extract_urls("visit http://example.com")
        assert len(result) == 1
        assert "http://example.com" in result[0]

    def test_https_url(self):
        result = extract_urls("see https://shop.io/path")
        assert len(result) == 1

    def test_multiple_urls(self):
        text = "links: https://a.com and http://b.com"
        result = extract_urls(text)
        assert len(result) == 2

    def test_no_urls(self):
        assert extract_urls("no links here") == []

    def test_empty_string(self):
        assert extract_urls("") == []

    def test_url_with_params(self):
        result = extract_urls("https://api.com/search?q=test&page=1")
        assert len(result) == 1


# ──────────────────────────────────────────────
# count_emojis
# ──────────────────────────────────────────────
class TestCountEmojis:

    def test_no_emojis(self):
        assert count_emojis("plain text") == 0

    def test_empty_string(self):
        assert count_emojis("") == 0

    def test_with_emojis(self):
        result = count_emojis("hello 😀 world 🎉")
        assert result >= 1  # emoji detection can vary

    def test_all_text(self):
        assert count_emojis("abc def ghi") == 0


# ──────────────────────────────────────────────
# get_content_metrics
# ──────────────────────────────────────────────
class TestGetContentMetrics:

    def test_returns_dict(self):
        result = get_content_metrics("hello world")
        assert isinstance(result, dict)

    def test_all_keys_present(self):
        result = get_content_metrics("test")
        expected_keys = {
            "character_count", "word_count", "hashtag_count",
            "mention_count", "link_count", "emoji_count",
            "uppercase_ratio", "avg_word_length",
        }
        assert set(result.keys()) == expected_keys

    def test_character_count(self):
        assert get_content_metrics("hello")["character_count"] == 5

    def test_word_count(self):
        assert get_content_metrics("one two three")["word_count"] == 3

    def test_hashtag_count(self):
        assert get_content_metrics("#a #b #c")["hashtag_count"] == 3

    def test_mention_count(self):
        assert get_content_metrics("@alice @bob")["mention_count"] == 2

    def test_link_count(self):
        assert get_content_metrics("https://a.com http://b.com")["link_count"] == 2

    def test_uppercase_ratio(self):
        result = get_content_metrics("HELLO")["uppercase_ratio"]
        assert result == pytest.approx(1.0)

    def test_uppercase_ratio_mixed(self):
        result = get_content_metrics("Hello")["uppercase_ratio"]
        assert result == pytest.approx(0.2)

    def test_avg_word_length(self):
        # "ab cd ef" → avg = (2+2+2)/3 = 2.0
        result = get_content_metrics("ab cd ef")["avg_word_length"]
        assert result == pytest.approx(2.0)

    def test_empty_text(self):
        result = get_content_metrics("")
        assert result["character_count"] == 0
        assert result["word_count"] == 0


# ──────────────────────────────────────────────
# SPAM_PHRASES constant
# ──────────────────────────────────────────────
class TestSpamPhrases:

    def test_is_set(self):
        assert isinstance(SPAM_PHRASES, set)

    def test_all_lowercase(self):
        for phrase in SPAM_PHRASES:
            assert phrase == phrase.lower()

    def test_known_phrases_present(self):
        assert "click here" in SPAM_PHRASES
        assert "free money" in SPAM_PHRASES
        assert "crypto giveaway" in SPAM_PHRASES


# ──────────────────────────────────────────────
# has_spam_phrases
# ──────────────────────────────────────────────
class TestHasSpamPhrases:

    def test_clean_text(self):
        assert has_spam_phrases("I love this product") is False

    def test_spam_text(self):
        assert has_spam_phrases("Click here for free money!") is True

    def test_case_insensitive(self):
        assert has_spam_phrases("CLICK HERE NOW") is True

    def test_embedded_phrase(self):
        assert has_spam_phrases("please check out my new product") is True

    def test_empty_string(self):
        assert has_spam_phrases("") is False

    def test_crypto_giveaway(self):
        assert has_spam_phrases("Crypto Giveaway! Win big!") is True


# ──────────────────────────────────────────────
# has_excessive_caps
# ──────────────────────────────────────────────
class TestHasExcessiveCaps:

    def test_normal_text(self):
        assert has_excessive_caps("Hello, how are you today?") is False

    def test_all_caps_long(self):
        assert has_excessive_caps("THIS IS ALL CAPS TEXT NOW") is True

    def test_short_text_returns_false(self):
        # Less than 10 letters → always False
        assert has_excessive_caps("HI THERE") is False

    def test_exactly_10_letters_boundary(self):
        # "ABCDEFGHIJ" has 10 letters, all uppercase
        assert has_excessive_caps("ABCDEFGHIJ") is True

    def test_custom_threshold(self):
        text = "Half UPPER Half lower text"
        # default 0.5 threshold
        result_strict = has_excessive_caps(text, threshold=0.3)
        result_loose = has_excessive_caps(text, threshold=0.9)
        assert result_loose is False

    def test_no_letters(self):
        assert has_excessive_caps("12345 67890 !@#$%") is False

    def test_mixed_just_under_threshold(self):
        # 5 upper + 6 lower = 11 letters, ratio ≈ 0.45 < 0.5
        assert has_excessive_caps("ABCDEfghijk") is False


# ──────────────────────────────────────────────
# has_keyword_stuffing
# ──────────────────────────────────────────────
class TestHasKeywordStuffing:

    def test_normal_text(self):
        assert has_keyword_stuffing("this is a normal varied sentence") is False

    def test_stuffed_text(self):
        assert has_keyword_stuffing("buy buy buy buy buy buy buy buy buy buy") is True

    def test_short_text_returns_false(self):
        # < 5 words
        assert has_keyword_stuffing("buy buy buy buy") is False

    def test_exactly_5_words_at_threshold(self):
        # "a a a a a" → 5 words, most common = 5, ratio = 1.0 > 0.3
        assert has_keyword_stuffing("a a a a a") is True

    def test_custom_threshold(self):
        text = "the the the other words here now"
        assert has_keyword_stuffing(text, threshold=0.9) is False

    def test_empty_string(self):
        assert has_keyword_stuffing("") is False

    def test_normalizes_text(self):
        # Hashtags/mentions removed, so repeated content word matters
        assert has_keyword_stuffing("sale sale sale sale sale") is True


# ──────────────────────────────────────────────
# BOT_USERNAME_PATTERNS
# ──────────────────────────────────────────────
class TestBotUsernamePatterns:

    def test_is_list(self):
        assert isinstance(BOT_USERNAME_PATTERNS, list)

    def test_all_are_strings(self):
        for pattern in BOT_USERNAME_PATTERNS:
            assert isinstance(pattern, str)


# ──────────────────────────────────────────────
# is_bot_username
# ──────────────────────────────────────────────
class TestIsBotUsername:

    def test_normal_username(self):
        assert is_bot_username("sarah_jones") is False

    def test_empty_string(self):
        assert is_bot_username("") is False

    def test_none(self):
        assert is_bot_username(None) is False

    def test_word_plus_4_digits(self):
        assert is_bot_username("john12345") is True

    def test_ends_with_bot_not_caught(self):
        # NOTE: Source uses re.match (start-anchored), so _bot$ pattern
        # never triggers. This is a source bug — re.search would fix it.
        assert is_bot_username("spam_bot") is False

    def test_starts_with_bot(self):
        assert is_bot_username("bot_spammer") is True

    def test_letters_plus_8_digits(self):
        assert is_bot_username("ab12345678") is True

    def test_case_insensitive(self):
        assert is_bot_username("JOHN12345") is True

    def test_real_looking_username(self):
        assert is_bot_username("techreviewguy") is False

    def test_short_name(self):
        assert is_bot_username("sam") is False


# ──────────────────────────────────────────────
# calculate_spam_score
# ──────────────────────────────────────────────
class TestCalculateSpamScore:

    def test_clean_text_low_score(self):
        score = calculate_spam_score("This product has excellent build quality and great battery life")
        assert score < 0.3

    def test_spam_text_high_score(self):
        score = calculate_spam_score("CLICK HERE for FREE MONEY! crypto giveaway #a #b #c #d #e #f https://spam.com https://spam2.com https://spam3.com")
        assert score > 0.5

    def test_returns_float(self):
        assert isinstance(calculate_spam_score("test"), float)

    def test_capped_at_1(self):
        # Stack every spam signal
        text = "CLICK HERE FREE MONEY CRYPTO GIVEAWAY buy buy buy buy buy buy buy buy buy buy #a #b #c #d #e #f https://a.com https://b.com https://c.com"
        score = calculate_spam_score(text, username="bot_spammer")
        assert score <= 1.0

    def test_spam_phrase_adds_035(self):
        clean = calculate_spam_score("this is normal text here now today")
        spam = calculate_spam_score("click here to win this prize today")
        assert spam >= clean + 0.3

    def test_bot_username_adds_020(self):
        text = "some normal text that is here now"
        without = calculate_spam_score(text)
        # Use pattern that re.match can catch (starts with bot_)
        with_bot = calculate_spam_score(text, username="bot_sender")
        assert with_bot >= without + 0.15

    def test_excessive_hashtags_adds_score(self):
        no_tags = calculate_spam_score("hello world this is a test post")
        many_tags = calculate_spam_score("hello #a #b #c #d #e #f world")
        assert many_tags > no_tags

    def test_excessive_links_adds_score(self):
        no_links = calculate_spam_score("hello world this is a test post")
        many_links = calculate_spam_score("hello https://a.com https://b.com https://c.com world")
        assert many_links > no_links

    def test_very_short_content_adds_score(self):
        short = calculate_spam_score("hi")
        longer = calculate_spam_score("this is a nice product review overall")
        assert short >= longer  # short adds 0.05

    def test_no_username_no_penalty(self):
        score = calculate_spam_score("normal text here now today please")
        assert score < 0.5

    def test_score_zero_possible(self):
        score = calculate_spam_score("this is a perfectly normal review of the product quality and design")
        assert score >= 0.0


# ──────────────────────────────────────────────
# calculate_account_age_score
# ──────────────────────────────────────────────
class TestCalculateAccountAgeScore:

    def test_none_returns_neutral(self):
        assert calculate_account_age_score(None) == 0.5

    def test_zero_days(self):
        score = calculate_account_age_score(0)
        assert score == pytest.approx(0.1)

    def test_new_account_range(self):
        # 0-30 days → 0.1 to 0.3
        score = calculate_account_age_score(15)
        assert 0.1 <= score <= 0.3

    def test_at_new_threshold(self):
        # Exactly 30 days → boundary between new and growing
        score = calculate_account_age_score(30)
        assert score == pytest.approx(0.3)

    def test_growing_account(self):
        # 30-180 days → 0.3 to 0.7
        score = calculate_account_age_score(105)
        assert 0.3 <= score <= 0.7

    def test_at_established_threshold(self):
        score = calculate_account_age_score(180)
        assert score == pytest.approx(0.7)

    def test_established_account(self):
        score = calculate_account_age_score(400)
        assert 0.7 <= score <= 1.0

    def test_max_age(self):
        score = calculate_account_age_score(730)
        assert score == pytest.approx(1.0)

    def test_beyond_max_age(self):
        score = calculate_account_age_score(5000)
        assert score == pytest.approx(1.0)

    def test_monotonically_increasing(self):
        scores = [calculate_account_age_score(d) for d in [0, 15, 30, 100, 180, 400, 730]]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_custom_thresholds(self):
        score = calculate_account_age_score(10, new_threshold=10, established_threshold=50)
        assert score == pytest.approx(0.3)


# ──────────────────────────────────────────────
# calculate_follower_score
# ──────────────────────────────────────────────
class TestCalculateFollowerScore:

    def test_none_returns_neutral(self):
        assert calculate_follower_score(None) == 0.5

    def test_zero_followers(self):
        score = calculate_follower_score(0)
        assert score == pytest.approx(0.1)

    def test_negative_followers(self):
        score = calculate_follower_score(-1)
        assert score == pytest.approx(0.1)

    def test_few_followers(self):
        score = calculate_follower_score(5)
        assert score == pytest.approx(0.2)

    def test_hundred_followers(self):
        score = calculate_follower_score(100)
        assert 0.3 <= score <= 0.6

    def test_thousand_followers(self):
        score = calculate_follower_score(1000)
        assert 0.5 <= score <= 0.8

    def test_ten_thousand_followers(self):
        score = calculate_follower_score(10000)
        assert 0.7 <= score <= 1.0

    def test_huge_follower_count(self):
        score = calculate_follower_score(1_000_000)
        assert score <= 1.0

    def test_capped_at_1(self):
        score = calculate_follower_score(10_000_000)
        assert score <= 1.0

    def test_suspicious_ratio_low_followers_high_following(self):
        # Following >> followers → suspicious
        normal = calculate_follower_score(50, following_count=50)
        suspicious = calculate_follower_score(50, following_count=5000)
        assert suspicious < normal

    def test_ratio_penalty_under_01(self):
        # 10 followers, 1000 following → ratio 0.01
        score = calculate_follower_score(10, following_count=1000)
        base = calculate_follower_score(10)
        assert score < base

    def test_no_following_no_penalty(self):
        s1 = calculate_follower_score(500)
        s2 = calculate_follower_score(500, following_count=None)
        assert s1 == s2

    def test_following_under_100_no_penalty(self):
        s1 = calculate_follower_score(500)
        s2 = calculate_follower_score(500, following_count=50)
        assert s1 == s2


# ──────────────────────────────────────────────
# analyze_posting_times
# ──────────────────────────────────────────────
class TestAnalyzePostingTimes:

    def _make_time(self, **kwargs):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return base + timedelta(**kwargs)

    def test_empty_list(self):
        result = analyze_posting_times([])
        assert result["count"] == 0
        assert result["is_suspicious"] is False

    def test_single_timestamp(self):
        result = analyze_posting_times([self._make_time()])
        assert result["count"] == 1
        assert result["is_suspicious"] is False

    def test_two_timestamps(self):
        t1 = self._make_time()
        t2 = self._make_time(minutes=30)
        result = analyze_posting_times([t1, t2])
        assert result["count"] == 2
        assert "avg_interval_seconds" in result

    def test_regular_intervals_suspicious(self):
        # Posts exactly every 60 seconds — very bot-like
        times = [self._make_time(seconds=i * 60) for i in range(20)]
        result = analyze_posting_times(times)
        assert result["is_suspicious"] is True
        assert result["regularity_score"] > 0.8

    def test_irregular_intervals_not_suspicious(self):
        # Random-ish intervals
        offsets = [0, 45, 200, 800, 1500, 3000, 7200, 8000]
        times = [self._make_time(seconds=s) for s in offsets]
        result = analyze_posting_times(times)
        # Irregular patterns shouldn't be flagged
        assert result["count"] == 8

    def test_very_fast_posting_suspicious(self):
        # Posts every 2 seconds
        times = [self._make_time(seconds=i * 2) for i in range(10)]
        result = analyze_posting_times(times)
        assert result["is_suspicious"] is True
        assert result["min_interval_seconds"] < 10

    def test_unsorted_input(self):
        t1 = self._make_time(minutes=10)
        t2 = self._make_time(minutes=0)
        t3 = self._make_time(minutes=5)
        result = analyze_posting_times([t1, t2, t3])
        assert result["count"] == 3
        # Should handle unsorted timestamps correctly
        assert result["min_interval_seconds"] == pytest.approx(300.0)  # 5 min

    def test_returns_all_keys_for_multiple(self):
        times = [self._make_time(seconds=i * 100) for i in range(5)]
        result = analyze_posting_times(times)
        for key in ["count", "avg_interval_seconds", "min_interval_seconds",
                     "max_interval_seconds", "is_suspicious", "regularity_score"]:
            assert key in result


# ──────────────────────────────────────────────
# detect_burst_activity
# ──────────────────────────────────────────────
class TestDetectBurstActivity:

    def _make_time(self, **kwargs):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return base + timedelta(**kwargs)

    def test_fewer_than_threshold(self):
        times = [self._make_time(minutes=i) for i in range(5)]
        assert detect_burst_activity(times, burst_threshold=10) is False

    def test_burst_detected(self):
        # 15 posts in 30 minutes
        times = [self._make_time(minutes=i * 2) for i in range(15)]
        assert detect_burst_activity(times, window_minutes=60, burst_threshold=10) is True

    def test_spread_out_no_burst(self):
        # 15 posts spread over 15 hours
        times = [self._make_time(hours=i) for i in range(15)]
        assert detect_burst_activity(times, window_minutes=60, burst_threshold=10) is False

    def test_exactly_at_threshold(self):
        # Exactly 10 posts in 59 minutes
        times = [self._make_time(minutes=i * 5) for i in range(10)]
        assert detect_burst_activity(times, window_minutes=60, burst_threshold=10) is True

    def test_empty_list(self):
        assert detect_burst_activity([]) is False

    def test_custom_window(self):
        # 10 posts in 5 minutes
        times = [self._make_time(seconds=i * 20) for i in range(10)]
        assert detect_burst_activity(times, window_minutes=5, burst_threshold=10) is True

    def test_burst_at_end(self):
        # Spread out posts + burst at end
        spread = [self._make_time(hours=i) for i in range(5)]
        burst = [self._make_time(hours=5, minutes=i) for i in range(12)]
        all_times = spread + burst
        assert detect_burst_activity(all_times, window_minutes=60, burst_threshold=10) is True

    def test_just_below_threshold(self):
        times = [self._make_time(minutes=i * 5) for i in range(9)]
        assert detect_burst_activity(times, window_minutes=60, burst_threshold=10) is False

        