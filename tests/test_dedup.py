"""Tests for deduplication logic."""

import pytest
from dedup import (
    canonicalize_url,
    normalize_title,
    title_similarity,
    content_hash,
    are_duplicates,
    merge_items,
    calculate_score,
    deduplicate,
    parse_heat,
    normalize_heat,
)


class TestTitleNormalization:
    """Tests for title normalization."""

    def test_lowercases(self):
        """Titles should be lowercased."""
        assert normalize_title("DOOM Ported") == "doom ported"

    def test_strips_source_suffixes(self):
        """Source name suffixes should be stripped."""
        title = "Great Article - Hacker News"
        assert "hacker news" not in normalize_title(title).lower()

    def test_strips_reddit_suffixes(self):
        """Reddit subreddit suffixes should be stripped."""
        title = "Cool Post : r/technology"
        assert "r/technology" not in normalize_title(title)

    def test_strips_bracket_suffixes(self):
        """Bracketed suffixes should be stripped."""
        title = "News Article [Breaking]"
        assert "[" not in normalize_title(title)

    def test_strips_common_prefixes(self):
        """Common prefixes like 'Breaking:' should be stripped."""
        assert "breaking" not in normalize_title("Breaking: Big News")
        assert "update" not in normalize_title("Update: More Info")

    def test_removes_punctuation(self):
        """Punctuation should be removed."""
        result = normalize_title("Hello, World!")
        assert "," not in result
        assert "!" not in result

    def test_normalizes_whitespace(self):
        """Multiple spaces should collapse to single space."""
        result = normalize_title("Hello    World")
        assert "    " not in result

    def test_handles_empty(self):
        """Empty titles should return empty string."""
        assert normalize_title("") == ""
        assert normalize_title(None) == ""


class TestTitleSimilarity:
    """Tests for title similarity calculation."""

    def test_identical_titles(self):
        """Identical titles should have 1.0 similarity."""
        sim = title_similarity("Hello World", "Hello World")
        assert sim == 1.0

    def test_similar_titles_high_score(self):
        """Similar titles should have high similarity."""
        sim = title_similarity(
            "DOOM Ported to an Earbud",
            "DOOM Running on an Earbud"
        )
        assert sim >= 0.7

    def test_different_titles_low_score(self):
        """Different titles should have low similarity."""
        sim = title_similarity(
            "Apple Announces iPhone",
            "Microsoft Releases Windows"
        )
        assert sim < 0.5

    def test_with_source_suffixes(self):
        """Titles with source suffixes should still match."""
        sim = title_similarity(
            "Great Article - Hacker News",
            "Great Article"
        )
        assert sim >= 0.9

    def test_case_insensitive(self):
        """Similarity should be case insensitive."""
        sim = title_similarity("Hello World", "HELLO WORLD")
        assert sim == 1.0

    def test_empty_returns_zero(self):
        """Empty titles should return 0.0 similarity."""
        assert title_similarity("", "Hello") == 0.0
        assert title_similarity("Hello", "") == 0.0


class TestContentHash:
    """Tests for content hashing."""

    def test_same_content_same_hash(self):
        """Same content should produce same hash."""
        content = "This is some article content for testing."
        assert content_hash(content) == content_hash(content)

    def test_different_content_different_hash(self):
        """Different content should produce different hash."""
        hash1 = content_hash("Article about topic A")
        hash2 = content_hash("Article about topic B")
        assert hash1 != hash2

    def test_whitespace_normalized(self):
        """Whitespace should be normalized before hashing."""
        hash1 = content_hash("Hello    World")
        hash2 = content_hash("Hello World")
        assert hash1 == hash2

    def test_case_normalized(self):
        """Case should be normalized before hashing."""
        hash1 = content_hash("Hello World")
        hash2 = content_hash("hello world")
        assert hash1 == hash2

    def test_uses_first_500_chars(self):
        """Only first 500 chars should be used."""
        content1 = "A" * 500 + "DIFFERENT_ENDING"
        content2 = "A" * 500 + "ANOTHER_ENDING"
        assert content_hash(content1) == content_hash(content2)

    def test_empty_returns_empty(self):
        """Empty content should return empty string."""
        assert content_hash("") == ""
        assert content_hash(None) == ""


class TestAreDuplicates:
    """Tests for duplicate detection."""

    def test_same_url_is_duplicate(self):
        """Items with same URL should be duplicates."""
        item1 = {"url": "https://example.com/article", "title": "Title A"}
        item2 = {"url": "https://example.com/article", "title": "Title B"}
        assert are_duplicates(item1, item2)

    def test_same_url_different_tracking_params(self):
        """Same URL with different tracking params should be duplicates."""
        item1 = {"url": "https://example.com/article?utm_source=a", "title": "Title"}
        item2 = {"url": "https://example.com/article?utm_source=b", "title": "Title"}
        assert are_duplicates(item1, item2)

    def test_similar_titles_are_duplicates(self):
        """Items with similar titles should be duplicates."""
        item1 = {"url": "https://a.com", "title": "DOOM Ported to an Earbud"}
        item2 = {"url": "https://b.com", "title": "DOOM Running on an Earbud"}
        assert are_duplicates(item1, item2)

    def test_different_titles_not_duplicates(self):
        """Items with different titles and URLs should not be duplicates."""
        item1 = {"url": "https://a.com", "title": "Apple Announces iPhone"}
        item2 = {"url": "https://b.com", "title": "Microsoft Releases Windows"}
        assert not are_duplicates(item1, item2)

    def test_same_content_is_duplicate(self):
        """Items with same content hash should be duplicates."""
        content = "This is the article content " * 50  # Long enough
        item1 = {"url": "https://a.com", "title": "Title A", "content": content}
        item2 = {"url": "https://b.com", "title": "Title B", "content": content}
        assert are_duplicates(item1, item2)

    def test_threshold_parameter(self):
        """Custom threshold should be respected."""
        item1 = {"url": "https://a.com", "title": "DOOM Ported"}
        item2 = {"url": "https://b.com", "title": "DOOM Running"}

        # With default threshold (0.70), these might match
        # With very high threshold, they shouldn't
        assert not are_duplicates(item1, item2, title_threshold=0.95)


class TestMergeItems:
    """Tests for merging duplicate items."""

    def test_single_item_returns_same(self):
        """Single item should return with sources array."""
        item = {"source": "HN", "title": "Test", "url": "https://a.com", "heat": "100"}
        result = merge_items([item])
        assert result["sources"] == ["HN"]
        assert result["source_count"] == 1

    def test_merges_sources(self):
        """Multiple items should merge sources."""
        items = [
            {"source": "HN", "title": "Test", "url": "https://a.com", "heat": "100"},
            {"source": "Reddit", "title": "Test", "url": "https://a.com", "heat": "200"},
        ]
        result = merge_items(items)
        assert len(result["sources"]) == 2
        assert "HN" in result["sources"]
        assert "Reddit" in result["sources"]
        assert result["source_count"] == 2

    def test_keeps_longest_title(self):
        """Longest title should be kept."""
        items = [
            {"source": "A", "title": "Short", "url": "https://a.com", "heat": ""},
            {"source": "B", "title": "This is a much longer title", "url": "https://b.com", "heat": ""},
        ]
        result = merge_items(items)
        assert result["title"] == "This is a much longer title"

    def test_prefers_original_url_over_aggregator(self):
        """Original source URL should be preferred over aggregator."""
        items = [
            {"source": "HN", "title": "Test", "url": "https://news.ycombinator.com/item?id=123", "heat": ""},
            {"source": "TechCrunch", "title": "Test", "url": "https://techcrunch.com/article", "heat": ""},
        ]
        result = merge_items(items)
        assert "techcrunch.com" in result["url"]

    def test_keeps_heat_per_source(self):
        """Heat should be stored per source."""
        items = [
            {"source": "Hacker News", "title": "Test", "url": "https://a.com", "heat": "529 points"},
            {"source": "Reddit r/tech", "title": "Test", "url": "https://a.com", "heat": "5200 upvotes"},
        ]
        result = merge_items(items)
        assert "hacker_news" in result["heat"]
        assert "reddit_r_tech" in result["heat"]


class TestCalculateScore:
    """Tests for score calculation."""

    def test_source_count_weight(self):
        """More sources should mean higher score."""
        item1 = {"source_count": 1, "heat": {}, "time": ""}
        item2 = {"source_count": 3, "heat": {}, "time": ""}

        score1 = calculate_score(item1)
        score2 = calculate_score(item2)

        assert score2 > score1
        assert score2 - score1 >= 200  # At least 200 points difference

    def test_heat_affects_score(self):
        """Heat should increase score."""
        item1 = {"source_count": 1, "heat": {"hn": "100 points"}, "time": ""}
        item2 = {"source_count": 1, "heat": {"hn": "1000 points"}, "time": ""}

        score1 = calculate_score(item1)
        score2 = calculate_score(item2)

        assert score2 > score1

    def test_recency_bonus_applied(self):
        """Recent items should get bonus."""
        from datetime import datetime, timezone, timedelta

        recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

        item_recent = {"source_count": 1, "heat": {}, "time": recent_time}
        item_old = {"source_count": 1, "heat": {}, "time": old_time}

        score_recent = calculate_score(item_recent)
        score_old = calculate_score(item_old)

        assert score_recent > score_old


class TestDeduplicate:
    """Tests for the main deduplication function."""

    def test_returns_tuple(self):
        """Should return tuple of (items, meta)."""
        result = deduplicate([])
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_meta_contains_stats(self):
        """Meta should contain dedup statistics."""
        items = [
            {"source": "A", "title": "Test", "url": "https://a.com", "heat": ""},
        ]
        _, meta = deduplicate(items)

        assert "raw_items" in meta
        assert "after_dedup" in meta
        assert "duplicates_merged" in meta

    def test_merges_duplicates(self):
        """Duplicate items should be merged."""
        items = [
            {"source": "HN", "title": "DOOM on Earbud", "url": "https://a.com", "heat": "100"},
            {"source": "Reddit", "title": "DOOM on Earbud", "url": "https://a.com", "heat": "200"},
        ]
        deduped, meta = deduplicate(items)

        assert len(deduped) == 1
        assert deduped[0]["source_count"] == 2
        assert meta["duplicates_merged"] == 1

    def test_sorts_by_score(self):
        """Results should be sorted by score (descending)."""
        items = [
            {"source": "A", "title": "Low Score", "url": "https://a.com", "heat": "10"},
            {"source": "B", "title": "High Score", "url": "https://b.com", "heat": "1000"},
            {"source": "C", "title": "High Score", "url": "https://b.com", "heat": "1000"},
        ]
        deduped, _ = deduplicate(items)

        # Multi-source item should be first
        assert deduped[0]["source_count"] == 2


class TestHeatParsing:
    """Tests for heat value parsing."""

    def test_parses_points(self):
        """'529 points' should parse to 529."""
        assert parse_heat("529 points", "hn") == 529

    def test_parses_upvotes(self):
        """'5200 upvotes' should parse to 5200."""
        assert parse_heat("5200 upvotes", "reddit") == 5200

    def test_parses_k_suffix(self):
        """'5.2K upvotes' should parse to 5200."""
        assert parse_heat("5.2K upvotes", "reddit") == 5200

    def test_parses_m_suffix(self):
        """'1.5M' should parse to 1500000."""
        assert parse_heat("1.5M stars", "github") == 1500000

    def test_handles_empty(self):
        """Empty heat should return 0."""
        assert parse_heat("", "any") == 0
        assert parse_heat(None, "any") == 0


class TestHeatNormalization:
    """Tests for heat normalization."""

    def test_hackernews_normalization(self):
        """HN heat should normalize correctly."""
        # 1000 points = 100 normalized
        assert normalize_heat(1000, "hackernews") == 100

    def test_reddit_normalization(self):
        """Reddit heat should normalize correctly."""
        # 50000 upvotes = 100 normalized
        assert normalize_heat(50000, "reddit") == 100

    def test_caps_at_100(self):
        """Normalized heat should cap at 100."""
        assert normalize_heat(999999, "hackernews") == 100
        assert normalize_heat(999999, "reddit") == 100

    def test_default_for_unknown(self):
        """Unknown sources should get default value."""
        result = normalize_heat(100, "unknown_source")
        assert result == 50  # Default baseline
