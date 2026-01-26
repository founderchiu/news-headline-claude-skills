# Smart Deduplication Design

**Date**: 2026-01-25
**Status**: Approved
**Goal**: Improve content quality by merging duplicate stories across sources

---

## Problem Statement

The english-news-skill fetches from 14 sources, often returning the same story multiple times (e.g., a breaking story appears on HN, Reddit, BBC, and The Verge). This creates:
- Redundant output (same story repeated 4x)
- Harder to identify truly important stories
- No credibility signal from multi-source coverage

## Solution Overview

Add a post-processing deduplication layer that:
1. Detects duplicate stories across sources
2. Merges them into single entries with source attribution
3. Uses multi-source coverage as a ranking signal

---

## Architecture

### Deduplication Pipeline

```
Fetch All Sources → Collect Raw Items → Deduplicate → Rank → Output JSON
                                            ↓
                              ┌─────────────────────────┐
                              │  1. URL Canonicalization │
                              │  2. Title Fuzzy Match    │
                              │  3. Content Hash (deep)  │
                              └─────────────────────────┘
```

### Detection Methods

Stories are considered duplicates if ANY of these match:

| Method | Description | Threshold |
|--------|-------------|-----------|
| URL Match | Canonical URLs match (stripped of tracking params) | Exact |
| Title Similarity | Fuzzy match after normalization | 70% ratio |
| Content Hash | First 500 chars hash (--deep mode only) | Exact |

### URL Canonicalization

```python
def canonicalize_url(url):
    # Remove tracking parameters
    strip_params = ['utm_source', 'utm_medium', 'utm_campaign', 'ref', 'source']
    # Normalize www vs non-www
    # Resolve common redirects
    return normalized_url
```

### Title Normalization

```python
def normalize_title(title):
    # Lowercase
    # Remove punctuation
    # Strip " - Source Name" suffixes
    # Strip common prefixes like "Breaking:"
    return normalized_title
```

---

## Merge Strategy

When duplicates are detected, merge into single entry:

| Field | Selection Rule |
|-------|----------------|
| `title` | Longest title (usually most descriptive) |
| `url` | Prefer original source over discussion links (reddit, HN) |
| `time` | Earliest timestamp (first to report) |
| `sources` | Array of all source names |
| `source_count` | Length of sources array |
| `heat` | Dictionary with per-source metrics |

---

## Output Format

### New JSON Structure

```json
{
  "meta": {
    "fetched_at": "2026-01-25T10:30:00Z",
    "sources_scanned": 14,
    "raw_items": 156,
    "after_dedup": 89,
    "duplicates_merged": 67
  },
  "stories": [
    {
      "title": "DOOM Ported to an Earbud",
      "url": "https://doombuds.com",
      "sources": ["Hacker News", "Reddit r/technology", "The Verge"],
      "source_count": 3,
      "heat": {
        "hackernews": "227 points",
        "reddit_tech": "5.2K upvotes",
        "theverge": "featured"
      },
      "time": "7 hours ago",
      "time_unix": 1737795600,
      "content": "..."
    }
  ]
}
```

---

## Ranking Algorithm

Stories sorted by combined score:

```
score = (source_count * 100) + normalized_heat + recency_bonus
```

### Score Components

| Component | Calculation |
|-----------|-------------|
| `source_count` | Number of sources × 100 |
| `normalized_heat` | Convert to 0-100 scale (see table below) |
| `recency_bonus` | +20 if < 2 hours, +10 if < 6 hours |

### Heat Normalization

| Source | Formula | Cap |
|--------|---------|-----|
| Hacker News | points / 10 | 100 |
| Reddit | upvotes / 500 | 100 |
| GitHub | stars / 1000 | 100 |
| RSS sources | baseline 50 | 50 |

### Example Ranking

| Story | Sources | Heat | Recency | **Score** |
|-------|---------|------|---------|-----------|
| ICE Shooting Minneapolis | 4 | 85 | +10 | **495** |
| DOOM on Earbud | 3 | 72 | +10 | **382** |
| PostgreSQL Indexes | 1 | 23 | +20 | **143** |

---

## CLI Changes

```bash
# Deduplication enabled by default
python3 fetch_news.py --source all --deep

# Disable deduplication (raw output)
python3 fetch_news.py --source all --no-dedup

# Show dedup stats
python3 fetch_news.py --source all --stats
```

---

## SKILL.md Updates

### New Section: Deduplication

```markdown
## Deduplication

Stories are automatically deduplicated across sources. When presenting:
- Show **source count as credibility signal** (more sources = bigger story)
- Display heat breakdown inline: `HN (529 pts) • Reddit (11K) • BBC`
- Rank by combined reach, not single-source metrics
```

### Updated Report Structure

```markdown
1. **🔥 Top Stories** - Multi-source coverage (3+ sources)
2. **🌍 Global Headlines** - News from BBC, Reuters, AP
3. **🤖 Tech & AI** - Technology developments
4. **📈 Markets** - Finance news (if relevant)
5. **💡 Dev Insights** - Single-source but high-value items
```

### New Report Header

```markdown
---
📊 **Scan Summary**: 14 sources • 156 items fetched • 89 unique stories (67 duplicates merged)
🔝 **Top Signal**: "ICE Minneapolis" covered by 4 sources
---
```

### New Item Format

```markdown
### 1. [DOOM Ported to an Earbud](https://doombuds.com)
**🔥 Covered by 3 sources**: Hacker News (227 pts) • Reddit (5.2K) • The Verge

Someone got DOOM running on Pinebuds Pro earbuds, playable via web queue.

- **Why it matters**: The "Can it run DOOM?" meme reaches new heights
- **Keywords**: `#Gaming #Hardware #Retro`
```

---

## Implementation Plan

### New Files

| File | Purpose |
|------|---------|
| `scripts/dedup.py` | Deduplication module (standalone, importable) |

### Modified Files

| File | Changes |
|------|---------|
| `scripts/fetch_news.py` | Import dedup, add --no-dedup flag, output new format |
| `SKILL.md` | Add deduplication docs, update report format |

### Implementation Order

1. Create `dedup.py` with URL canonicalization
2. Add title fuzzy matching
3. Add content hash detection (for --deep mode)
4. Implement merge logic
5. Add ranking algorithm
6. Update `fetch_news.py` to use dedup module
7. Update `SKILL.md` with new guidelines
8. Test with full scan

---

## Success Criteria

- [ ] Duplicate stories merged correctly (same story from HN + Reddit = 1 entry)
- [ ] Source attribution preserved (shows all sources that covered it)
- [ ] Ranking favors multi-source stories
- [ ] No false positives (different stories not merged)
- [ ] Performance acceptable (< 2s overhead for 150 items)
