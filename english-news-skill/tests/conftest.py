"""Pytest configuration and fixtures for english-news-skill tests."""

import pytest
import sys
from pathlib import Path

# Add scripts directory to path for imports
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


@pytest.fixture
def sample_items():
    """Sample news items for testing."""
    return [
        {
            "source": "Hacker News",
            "source_type": "aggregator",
            "title": "DOOM Ported to an Earbud",
            "url": "https://doombuds.com/article",
            "discussion_url": "https://news.ycombinator.com/item?id=12345",
            "heat": "529 points",
            "time": "2 hours ago",
            "time_iso": "2026-01-25T08:00:00+00:00",
        },
        {
            "source": "Reddit r/technology",
            "source_type": "aggregator",
            "title": "DOOM Running on an Earbud - Full Article",
            "url": "https://doombuds.com/article",
            "discussion_url": "https://reddit.com/r/technology/comments/abc123",
            "heat": "5200 upvotes",
            "time": "2026-01-25 07:30",
            "time_iso": "2026-01-25T07:30:00+00:00",
        },
        {
            "source": "BBC News",
            "source_type": "wire",
            "title": "Tech Breakthrough: Gaming on Earbuds",
            "url": "https://bbc.co.uk/news/tech-12345",
            "heat": "",
            "time": "Sat, 25 Jan 2026 06:00:00 GMT",
            "time_iso": "2026-01-25T06:00:00+00:00",
        },
        {
            "source": "TechCrunch",
            "source_type": "original_reporting",
            "title": "OpenAI Announces GPT-5",
            "url": "https://techcrunch.com/openai-gpt5",
            "heat": "",
            "time": "Sat, 25 Jan 2026 10:00:00 GMT",
            "time_iso": "2026-01-25T10:00:00+00:00",
        },
    ]


@pytest.fixture
def sample_urls():
    """Sample URLs for canonicalization testing."""
    return {
        # Standard URL with tracking params
        "tracking": "https://example.com/article?utm_source=twitter&utm_medium=social&id=123",
        "tracking_clean": "https://example.com/article?id=123",

        # AMP URLs
        "amp_subdomain": "https://amp.example.com/article",
        "amp_path": "https://example.com/amp/article",
        "amp_clean": "https://example.com/article",

        # Mobile URLs
        "mobile_m": "https://m.example.com/article",
        "mobile_full": "https://mobile.example.com/article",
        "mobile_clean": "https://example.com/article",

        # www normalization
        "www": "https://www.example.com/article",
        "no_www": "https://example.com/article",

        # Trailing slash
        "trailing_slash": "https://example.com/article/",
        "no_trailing_slash": "https://example.com/article",
    }


@pytest.fixture
def sample_titles():
    """Sample titles for similarity testing."""
    return [
        # Should match (same story, different wording)
        ("DOOM Ported to an Earbud", "DOOM Running on an Earbud", True),
        ("OpenAI Releases GPT-5", "OpenAI Announces GPT-5 Model", True),
        ("Apple Stock Falls 5%", "Apple Shares Drop 5% Today", True),

        # Should NOT match (different stories)
        ("Tesla Stock Up 10%", "Tesla Stock Down 10%", False),
        ("Google Acquires Startup", "Microsoft Acquires Startup", False),
        ("Breaking: Fire in New York", "Breaking: Fire in Los Angeles", False),

        # Edge cases
        ("DOOM Ported to an Earbud - Hacker News", "DOOM Ported to an Earbud", True),
        ("Breaking: Important News", "Update: Important News", True),
    ]
