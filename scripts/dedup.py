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
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

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
    - Remove trailing slashes
    - Lowercase domain
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        # Lowercase domain, strip www
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # Filter out tracking params
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in params.items()
                       if k.lower() not in TRACKING_PARAMS}
            query = urlencode(filtered, doseq=True) if filtered else ''
        else:
            query = ''

        # Remove trailing slash from path
        path = parsed.path.rstrip('/')
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


def parse_time(time_str: str) -> Optional[datetime]:
    """Parse time string to datetime object."""
    if not time_str:
        return None

    time_lower = time_str.lower()
    now = datetime.now(timezone.utc)

    # Handle relative times like "2 hours ago"
    match = re.search(r'(\d+)\s*(minute|hour|day|week|month)s?\s*ago', time_lower)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        from datetime import timedelta
        if unit == 'minute':
            return now - timedelta(minutes=value)
        elif unit == 'hour':
            return now - timedelta(hours=value)
        elif unit == 'day':
            return now - timedelta(days=value)
        elif unit == 'week':
            return now - timedelta(weeks=value)
        elif unit == 'month':
            return now - timedelta(days=value * 30)

    # Try ISO format
    try:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        pass

    # Try common formats
    formats = [
        '%Y-%m-%d %H:%M',
        '%Y-%m-%dT%H:%M:%S',
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S GMT',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    return None


def recency_bonus(time_str: str) -> int:
    """Calculate recency bonus: +20 if <2h, +10 if <6h, 0 otherwise."""
    parsed = parse_time(time_str)
    if not parsed:
        return 0

    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    hours_ago = (now - parsed).total_seconds() / 3600

    if hours_ago < 2:
        return 20
    elif hours_ago < 6:
        return 10
    else:
        return 0


def are_duplicates(item1: Dict, item2: Dict, title_threshold: float = 0.70) -> bool:
    """
    Check if two items are duplicates using:
    1. URL match (after canonicalization)
    2. Title similarity (above threshold)
    3. Content hash match (if both have content)
    """
    # URL match
    url1 = canonicalize_url(item1.get('url', ''))
    url2 = canonicalize_url(item2.get('url', ''))

    if url1 and url2 and url1 == url2:
        return True

    # Title similarity
    title_sim = title_similarity(item1.get('title', ''), item2.get('title', ''))
    if title_sim >= title_threshold:
        return True

    # Content hash (for --deep mode)
    content1 = item1.get('content', '')
    content2 = item2.get('content', '')

    if content1 and content2:
        hash1 = content_hash(content1)
        hash2 = content_hash(content2)
        if hash1 and hash2 and hash1 == hash2:
            return True

    return False


def merge_items(items: List[Dict]) -> Dict:
    """
    Merge duplicate items into single entry:
    - title: longest title
    - url: prefer original source over aggregator
    - time: earliest timestamp
    - sources: list of all sources
    - heat: dict with per-source metrics
    """
    if not items:
        return {}

    if len(items) == 1:
        item = items[0].copy()
        item['sources'] = [item.get('source', 'Unknown')]
        item['source_count'] = 1
        item['heat'] = {item.get('source', 'unknown').lower().replace(' ', '_'): item.get('heat', '')}
        return item

    # Find best title (longest)
    best_title = max(items, key=lambda x: len(x.get('title', '')))['title']

    # Find best URL (prefer original source over reddit/HN discussion links)
    aggregator_domains = ['reddit.com', 'news.ycombinator.com', 'lobste.rs']

    urls_with_priority = []
    for item in items:
        url = item.get('url', '')
        is_aggregator = any(domain in url for domain in aggregator_domains)
        urls_with_priority.append((url, 0 if is_aggregator else 1))

    best_url = max(urls_with_priority, key=lambda x: x[1])[0]

    # Find earliest time
    times_parsed = []
    for item in items:
        parsed = parse_time(item.get('time', ''))
        if parsed:
            # Ensure all datetimes are timezone-aware for comparison
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            times_parsed.append((item.get('time', ''), parsed))

    earliest_time = min(times_parsed, key=lambda x: x[1])[0] if times_parsed else items[0].get('time', '')

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

    merged = {
        'title': best_title,
        'url': best_url,
        'sources': sources,
        'source_count': len(sources),
        'heat': heat_dict,
        'time': earliest_time,
    }

    if best_content:
        merged['content'] = best_content

    return merged


def calculate_score(item: Dict) -> float:
    """
    Calculate ranking score:
    score = (source_count * 100) + normalized_heat + recency_bonus
    """
    source_count = item.get('source_count', 1)

    # Calculate normalized heat (average across sources)
    heat_dict = item.get('heat', {})
    if isinstance(heat_dict, str):
        # Single source format
        heat_value = parse_heat(heat_dict, item.get('source', ''))
        normalized = normalize_heat(heat_value, item.get('source', ''))
    else:
        # Multi-source format
        heat_values = []
        for source_key, heat_str in heat_dict.items():
            heat_value = parse_heat(heat_str, source_key)
            normalized = normalize_heat(heat_value, source_key)
            heat_values.append(normalized)

        normalized = max(heat_values) if heat_values else 0

    # Recency bonus
    bonus = recency_bonus(item.get('time', ''))

    return (source_count * 100) + normalized + bonus


def deduplicate(items: List[Dict], title_threshold: float = 0.70) -> Tuple[List[Dict], Dict]:
    """
    Main deduplication function.

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

    # Calculate scores and sort
    for item in merged_items:
        item['_score'] = calculate_score(item)

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
