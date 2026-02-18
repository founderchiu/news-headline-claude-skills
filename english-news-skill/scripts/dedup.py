#!/usr/bin/env python3
"""
Smart Deduplication Module for English News Skill

Detects and merges duplicate stories across multiple sources using:
1. URL canonicalization (exact match after normalization)
2. Title fuzzy matching (70% similarity threshold)
3. Content hash matching (for --deep mode)

Ranks merged stories by: (source_count * 100) + normalized_heat + recency_bonus
"""

import re
import hashlib
from enum import Enum
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Import centralized time parsing
from utils.time_parser import parse_time, recency_bonus, parse_to_iso8601


class DupConfidence(Enum):
    """Confidence level for duplicate detection."""
    HIGH = "high"      # Same URL or same content hash
    MEDIUM = "medium"  # Title similarity + time proximity
    LOW = "low"        # Only title similarity (may be false positive)
    NONE = "none"      # Not duplicates

# Tracking params to strip from URLs
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'ref', 'source', 'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid',
    'share', 'share_id', 'via', 'from'
}

# Common suffixes to strip from titles
TITLE_SUFFIXES = [
    r'\s*[-–—|]\s*(Hacker News|Reddit|BBC.*|Reuters|AP News|TechCrunch|'
    r'Ars Technica|The Verge|Bloomberg|Yahoo Finance|CNBC|GitHub|Product Hunt).*$',
    r'\s*:\s*r/\w+$',
    r'\s*\[.*?\]$',
]

# Heat normalization factors
HEAT_NORMALIZERS = {
    'hackernews': lambda x: min(100, x / 10),      # 1000 pts = 100
    'reddit': lambda x: min(100, x / 500),          # 50K upvotes = 100
    'github': lambda x: min(100, x / 1000),         # 100K stars = 100
    'default': lambda x: 50,                         # RSS sources baseline
}


def canonicalize_url(url: str) -> str:
    """
    Normalize URL for comparison:
    - Strip tracking parameters
    - Normalize www vs non-www
    - Detect and normalize AMP URLs
    - Detect and normalize mobile URLs
    - Remove trailing slashes
    - Lowercase domain
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        # Lowercase domain
        netloc = parsed.netloc.lower()

        # Strip www prefix
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # Normalize AMP URLs
        # amp.example.com -> example.com
        if netloc.startswith('amp.'):
            netloc = netloc[4:]

        # Normalize mobile URLs
        # m.example.com -> example.com
        # mobile.example.com -> example.com
        if netloc.startswith('m.'):
            netloc = netloc[2:]
        elif netloc.startswith('mobile.'):
            netloc = netloc[7:]

        # Handle Google AMP cache URLs
        # example-com.cdn.ampproject.org -> example.com
        if '.cdn.ampproject.org' in netloc:
            # Extract original domain from subdomain
            # Format: example-com.cdn.ampproject.org
            subdomain = netloc.split('.cdn.ampproject.org')[0]
            # Convert hyphens back to dots (but be careful with compound domains)
            # This is a heuristic - may not always be perfect
            netloc = subdomain.replace('-', '.')

        # Normalize path
        path = parsed.path

        # Remove /amp/ from path
        if path.startswith('/amp/'):
            path = path[4:]  # Remove /amp prefix
        elif path.startswith('/amp'):
            path = path[4:] if len(path) > 4 else ''

        # Remove trailing /amp
        if path.endswith('/amp'):
            path = path[:-4]
        elif path.endswith('/amp/'):
            path = path[:-5]

        # Filter out tracking params
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in params.items()
                       if k.lower() not in TRACKING_PARAMS}
            query = urlencode(filtered, doseq=True) if filtered else ''
        else:
            query = ''

        # Remove trailing slash from path
        path = path.rstrip('/')
        if not path:
            path = ''

        # Reconstruct URL
        canonical = urlunparse((
            parsed.scheme,
            netloc,
            path,
            '',  # params
            query,
            ''   # fragment
        ))

        return canonical
    except Exception:
        return url


def normalize_title(title: str) -> str:
    """
    Normalize title for comparison:
    - Lowercase
    - Remove punctuation
    - Strip source name suffixes
    - Strip common prefixes
    """
    if not title:
        return ""

    normalized = title.lower()

    # Strip source suffixes
    for pattern in TITLE_SUFFIXES:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

    # Strip common prefixes
    prefixes = ['breaking:', 'update:', 'exclusive:', 'live:', 'watch:']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]

    # Remove punctuation and extra whitespace
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = ' '.join(normalized.split())

    return normalized.strip()


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity ratio between two titles (0.0 to 1.0)."""
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if not norm1 or not norm2:
        return 0.0

    return SequenceMatcher(None, norm1, norm2).ratio()


def content_hash(content: str) -> str:
    """Generate hash from first 500 chars of content."""
    if not content:
        return ""

    # Normalize: lowercase, remove extra whitespace
    normalized = ' '.join(content[:500].lower().split())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def parse_heat(heat_str: str, source: str) -> int:
    """Extract numeric heat value from string."""
    if not heat_str:
        return 0

    # Extract numbers from string like "529 points" or "11.3K upvotes"
    match = re.search(r'([\d,.]+)\s*([kKmM])?', heat_str)
    if not match:
        return 0

    try:
        value = float(match.group(1).replace(',', ''))
        multiplier = match.group(2)

        if multiplier and multiplier.lower() == 'k':
            value *= 1000
        elif multiplier and multiplier.lower() == 'm':
            value *= 1000000

        return int(value)
    except (ValueError, AttributeError):
        return 0


def normalize_heat(heat_value: int, source_type: str) -> float:
    """Normalize heat value to 0-100 scale based on source type."""
    source_lower = source_type.lower()

    if 'hacker' in source_lower or 'hn' in source_lower:
        return HEAT_NORMALIZERS['hackernews'](heat_value)
    elif 'reddit' in source_lower:
        return HEAT_NORMALIZERS['reddit'](heat_value)
    elif 'github' in source_lower:
        return HEAT_NORMALIZERS['github'](heat_value)
    else:
        return HEAT_NORMALIZERS['default'](heat_value)


def classify_duplicate(item1: Dict, item2: Dict) -> DupConfidence:
    """
    Classify the confidence level of a potential duplicate match.

    Two-stage matching:
    - HIGH: Same canonical URL OR same content hash
    - MEDIUM: Title similarity >= 80% AND time within 24 hours
    - LOW: Title similarity >= 70% only (potential false positive)
    - NONE: Not duplicates

    Returns:
        DupConfidence enum value
    """
    # Stage 1: HIGH confidence - exact matches
    url1 = canonicalize_url(item1.get('url', ''))
    url2 = canonicalize_url(item2.get('url', ''))

    if url1 and url2 and url1 == url2:
        return DupConfidence.HIGH

    # Content hash match (for --deep mode)
    content1 = item1.get('content', '')
    content2 = item2.get('content', '')

    if content1 and content2:
        hash1 = content_hash(content1)
        hash2 = content_hash(content2)
        if hash1 and hash2 and hash1 == hash2:
            return DupConfidence.HIGH

    # Stage 2: Title similarity
    title_sim = title_similarity(item1.get('title', ''), item2.get('title', ''))

    if title_sim >= 0.80:
        # High title similarity - check time proximity for MEDIUM confidence
        time1 = parse_time(item1.get('time', '') or item1.get('time_iso', ''))
        time2 = parse_time(item2.get('time', '') or item2.get('time_iso', ''))

        if time1 and time2:
            # Ensure both are timezone-aware
            if time1.tzinfo is None:
                time1 = time1.replace(tzinfo=timezone.utc)
            if time2.tzinfo is None:
                time2 = time2.replace(tzinfo=timezone.utc)

            time_diff = abs((time1 - time2).total_seconds())
            # Within 24 hours = MEDIUM confidence
            if time_diff <= 86400:
                return DupConfidence.MEDIUM

        # High title similarity but no time proximity = still MEDIUM
        # (better safe than sorry for clear title matches)
        return DupConfidence.MEDIUM

    elif title_sim >= 0.70:
        # Lower title similarity - only LOW confidence
        return DupConfidence.LOW

    return DupConfidence.NONE


def are_duplicates(item1: Dict, item2: Dict, title_threshold: float = 0.70) -> bool:
    """
    Check if two items are duplicates.

    Uses two-stage matching with confidence levels.
    Only HIGH and MEDIUM confidence matches are considered duplicates.

    Args:
        item1: First news item
        item2: Second news item
        title_threshold: Minimum title similarity (default: 0.70)

    Returns:
        True if items are duplicates (HIGH or MEDIUM confidence)
    """
    confidence = classify_duplicate(item1, item2)

    # HIGH and MEDIUM confidence are considered duplicates
    # LOW confidence (only title similarity) is excluded to prevent false positives
    return confidence in (DupConfidence.HIGH, DupConfidence.MEDIUM)


def _generate_dedup_group_id(items: List[Dict]) -> str:
    """Generate a unique group ID for a set of deduplicated items."""
    # Use hash of sorted canonical URLs
    urls = sorted(canonicalize_url(item.get('url', '')) for item in items)
    combined = '|'.join(urls)
    return hashlib.md5(combined.encode('utf-8')).hexdigest()[:12]


def _select_best_representative(items: List[Dict]) -> Dict:
    """
    Select the best representative item from a group.
    Prefers original_reporting > wire > aggregator.
    """
    # Source type priority (higher = better)
    source_priority = {
        'original_reporting': 3,
        'wire': 2,
        'aggregator': 1,
        'unknown': 0,
    }

    def get_priority(item):
        source_type = item.get('source_type', 'unknown')
        return source_priority.get(source_type, 0)

    # Sort by priority, then by title length (as tiebreaker)
    return max(items, key=lambda x: (get_priority(x), len(x.get('title', ''))))


def merge_items(items: List[Dict]) -> Dict:
    """
    Merge duplicate items into single entry:
    - title: longest title
    - url: prefer original source over aggregator
    - time: earliest timestamp
    - sources: list of all sources
    - heat: dict with per-source metrics
    - dedup_group_id: unique ID for this merge group
    - best_representative: the best source item
    - alternates: list of alternate sources with their URLs/titles
    """
    if not items:
        return {}

    if len(items) == 1:
        item = items[0].copy()
        item['sources'] = [item.get('source', 'Unknown')]
        item['source_count'] = 1
        item['heat'] = {item.get('source', 'unknown').lower().replace(' ', '_'): item.get('heat', '')}
        item['dedup_group_id'] = _generate_dedup_group_id([item])
        item['alternates'] = []
        return item

    # Find best title (longest)
    best_title = max(items, key=lambda x: len(x.get('title', '')))['title']

    # Find best URL (prefer original source over reddit/HN discussion links)
    aggregator_domains = ['reddit.com', 'news.ycombinator.com', 'lobste.rs']

    # Also prefer original_reporting source type
    def url_priority(item):
        url = item.get('url', '')
        is_aggregator = any(domain in url for domain in aggregator_domains)
        source_type = item.get('source_type', 'unknown')

        # Priority: original_reporting non-aggregator > wire > aggregator
        if source_type == 'original_reporting' and not is_aggregator:
            return 4
        elif source_type == 'wire':
            return 3
        elif not is_aggregator:
            return 2
        else:
            return 1

    best_item_for_url = max(items, key=url_priority)
    best_url = best_item_for_url.get('url', '')

    # Find earliest time
    times_parsed = []
    for item in items:
        parsed = parse_time(item.get('time', ''))
        if parsed:
            # Ensure all datetimes are timezone-aware for comparison
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            times_parsed.append((item.get('time', ''), item.get('time_iso', ''), parsed))

    if times_parsed:
        earliest = min(times_parsed, key=lambda x: x[2])
        earliest_time = earliest[0]
        earliest_time_iso = earliest[1]
    else:
        earliest_time = items[0].get('time', '')
        earliest_time_iso = items[0].get('time_iso', '')

    # Collect sources and heat
    sources = []
    heat_dict = {}

    for item in items:
        source = item.get('source', 'Unknown')
        if source not in sources:
            sources.append(source)

        source_key = source.lower().replace(' ', '_').replace('/', '_')
        heat_dict[source_key] = item.get('heat', '')

    # Get best content (longest)
    contents = [item.get('content', '') for item in items if item.get('content')]
    best_content = max(contents, key=len) if contents else ''

    # Select best representative and build alternates
    best_rep = _select_best_representative(items)
    alternates = [
        {
            'source': item.get('source', 'Unknown'),
            'source_type': item.get('source_type', 'unknown'),
            'url': item.get('url', ''),
            'title': item.get('title', ''),
        }
        for item in items if item != best_rep
    ]

    merged = {
        'title': best_title,
        'url': best_url,
        'sources': sources,
        'source_count': len(sources),
        'heat': heat_dict,
        'time': earliest_time,
        'dedup_group_id': _generate_dedup_group_id(items),
        'alternates': alternates,
    }

    # Add time_iso if available
    if earliest_time_iso:
        merged['time_iso'] = earliest_time_iso

    if best_content:
        merged['content'] = best_content

    return merged


# Credible sources for signal ranking
CREDIBLE_SOURCES = {
    'bbc', 'bbc news', 'reuters', 'ap news', 'bloomberg',
    'techcrunch', 'ars technica', 'the verge', 'cnbc', 'yahoo finance'
}


def calculate_scores(item: Dict) -> Dict[str, float]:
    """
    Calculate multiple ranking scores for different strategies.

    Returns dict with:
    - trending_score: Social heat-heavy (viral on Reddit/HN)
    - signal_score: Credibility-weighted (multi-source + wire services)
    - combined_score: Balanced (default)
    """
    source_count = item.get('source_count', 1)
    sources = item.get('sources', [item.get('source', '')])

    # Calculate normalized heat
    heat_dict = item.get('heat', {})
    if isinstance(heat_dict, str):
        heat_value = parse_heat(heat_dict, item.get('source', ''))
        normalized_heat = normalize_heat(heat_value, item.get('source', ''))
    else:
        heat_values = []
        for source_key, heat_str in heat_dict.items():
            heat_value = parse_heat(heat_str, source_key)
            normalized = normalize_heat(heat_value, source_key)
            heat_values.append(normalized)
        normalized_heat = max(heat_values) if heat_values else 0

    # Count credible sources
    credible_count = sum(
        1 for s in sources
        if any(c in s.lower() for c in CREDIBLE_SOURCES)
    )

    # Recency bonus
    bonus = recency_bonus(item.get('time', ''))

    return {
        # Trending: Social heat dominates
        'trending_score': normalized_heat + bonus,

        # Signal: Multi-source + credible outlets
        'signal_score': (source_count * 100) + (credible_count * 50) + bonus,

        # Combined: Balanced approach (default)
        'combined_score': (source_count * 50) + normalized_heat + (credible_count * 30) + bonus,
    }


def calculate_score(item: Dict) -> float:
    """
    Calculate default ranking score (combined strategy).

    For backward compatibility - uses combined_score from calculate_scores().
    """
    scores = calculate_scores(item)
    return scores['combined_score']


def deduplicate(
    items: List[Dict],
    title_threshold: float = 0.70,
    rank_by: str = "combined"
) -> Tuple[List[Dict], Dict]:
    """
    Main deduplication function.

    Args:
        items: List of news items to deduplicate
        title_threshold: Similarity threshold for title matching (0.0-1.0)
        rank_by: Ranking strategy - "trending", "signals", or "combined" (default)

    Returns:
        Tuple of (deduplicated_items, meta_stats)
    """
    if not items:
        return [], {'raw_items': 0, 'after_dedup': 0, 'duplicates_merged': 0}

    # Group duplicates
    groups = []  # List of lists, each inner list contains duplicate items
    used = set()

    for i, item in enumerate(items):
        if i in used:
            continue

        group = [item]
        used.add(i)

        for j, other in enumerate(items[i+1:], start=i+1):
            if j in used:
                continue

            if are_duplicates(item, other, title_threshold):
                group.append(other)
                used.add(j)

        groups.append(group)

    # Merge each group
    merged_items = [merge_items(group) for group in groups]

    # Calculate scores based on ranking strategy
    score_key = f"{rank_by}_score"
    for item in merged_items:
        scores = calculate_scores(item)
        item['_score'] = scores.get(score_key, scores['combined_score'])

    merged_items.sort(key=lambda x: x.get('_score', 0), reverse=True)

    # Remove internal score field
    for item in merged_items:
        item.pop('_score', None)

    # Calculate stats
    meta = {
        'raw_items': len(items),
        'after_dedup': len(merged_items),
        'duplicates_merged': len(items) - len(merged_items),
        'sources_scanned': len(set(item.get('source', '') for item in items)),
    }

    return merged_items, meta


# CLI for testing
if __name__ == '__main__':
    import json
    import sys

    # Read JSON from stdin
    data = json.load(sys.stdin)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and 'stories' in data:
        items = data['stories']
    else:
        print("Error: Expected list of items or dict with 'stories' key", file=sys.stderr)
        sys.exit(1)

    deduped, meta = deduplicate(items)

    output = {
        'meta': meta,
        'stories': deduped
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))
