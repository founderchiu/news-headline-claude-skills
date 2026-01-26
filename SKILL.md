---
name: english-news-skill
description: "English news aggregator fetching from 14 major sources across Tech (HN, GitHub, ProductHunt, Reddit, TechCrunch, Ars Technica, The Verge), Global (BBC, Reuters, AP), and Finance (Bloomberg, Yahoo Finance, CNBC). Best for 'morning briefings', 'tech news', 'market updates', and 'global headlines'."
---

# English News Skill

Fetch real-time news from major English-language sources worldwide.

## Sources

| Category | Sources |
|----------|---------|
| **Tech** | Hacker News, GitHub Trending, Product Hunt, Reddit (r/technology, r/programming), TechCrunch, Ars Technica, The Verge |
| **Global** | BBC News, Reuters, AP News |
| **Finance** | Bloomberg, Yahoo Finance, CNBC, **Reddit Stocks** (NEW) |

## Tools

### fetch_news.py

**Location:** `scripts/fetch_news.py`

**Usage:**

```bash
# Single source
python3 scripts/fetch_news.py --source hackernews --limit 10 --deep

# Source groups
python3 scripts/fetch_news.py --source tech --limit 10 --deep
python3 scripts/fetch_news.py --source global --limit 10 --deep
python3 scripts/fetch_news.py --source finance --limit 10 --deep

# Full scan (all sources)
python3 scripts/fetch_news.py --source all --limit 15 --deep

# Keyword filtering with smart expansion
python3 scripts/fetch_news.py --source tech --keyword "AI,LLM,GPT,Claude,Agent" --deep
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--source` | Source name, group name, or comma-separated list. Groups: `tech`, `global`, `finance`, `all` |
| `--limit` | Max items per source (default: 10) |
| `--keyword` | Comma-separated keyword filter (case-insensitive) |
| `--deep` | Fetch full article content for deeper analysis |
| `--no-dedup` | Disable deduplication (raw output, backward compatible) |

**Individual Sources:**
`hackernews`, `github`, `producthunt`, `reddit_tech`, `reddit_programming`, `techcrunch`, `arstechnica`, `theverge`, `bbc`, `reuters`, `apnews`, `bloomberg`, `yahoo_finance`, `cnbc`, `reddit_stocks`

### Reddit Stocks Tracker (NEW)

Scans r/wallstreetbets, r/stocks, r/investing for the **top 10 most discussed stock tickers**.

```bash
# Get top discussed stocks
python3 scripts/fetch_news.py --source reddit_stocks --limit 10

# Include in finance scan
python3 scripts/fetch_news.py --source finance --limit 10
```

**Output example:**
```json
{
  "title": "$META - Mentioned 15x across r/wallstreetbets, r/stocks",
  "url": "https://finance.yahoo.com/quote/META",
  "heat": "15 mentions",
  "description": "META $90K YOLO + DD",
  "top_post_url": "https://reddit.com/r/wallstreetbets/..."
}
```

## Smart Deduplication (NEW)

Stories are **automatically deduplicated** across sources using:
- URL matching (after stripping tracking params)
- Title fuzzy matching (70% similarity threshold)
- Content hash matching (for `--deep` mode)

**Benefits:**
- Same story from HN + Reddit + BBC = 1 entry with source attribution
- Multi-source coverage = credibility signal (bigger story)
- Ranked by: `(source_count × 100) + normalized_heat + recency_bonus`

**Output format:**
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
      "heat": {"hackernews": "227 points", "reddit_tech": "5.2K upvotes"},
      "time": "7 hours ago"
    }
  ]
}
```

## Interactive Menu

When the user invokes this skill without specific instructions, **READ** `templates.md` and **DISPLAY** the menu.

## Smart Keyword Expansion (CRITICAL)

**ALWAYS** expand simple keywords to cover the domain:
- User: "AI" → Agent uses: `--keyword "AI,LLM,GPT,Claude,Gemini,OpenAI,Anthropic,Machine Learning,Neural,Agent"`
- User: "crypto" → Agent uses: `--keyword "crypto,Bitcoin,Ethereum,blockchain,DeFi,Web3"`
- User: "Apple" → Agent uses: `--keyword "Apple,iPhone,Mac,iOS,macOS,iPad,Vision Pro"`

## Response Guidelines (CRITICAL)

### Format & Style
- **Headlines**: English (preserve original)
- **Analysis/Summary**: Simplified Chinese (简体中文)
- **Style**: Magazine/Newsletter style (Morning Brew / The Economist vibe)

### Report Structure
1. **🔥 Top Stories** - Multi-source coverage (3+ sources) - most important
2. **🌍 Global Headlines** - News from BBC, Reuters, AP
3. **🤖 Tech & AI** - Technology, software, AI developments
4. **📈 Markets & Finance** - Financial news (if relevant)
5. **💡 Developer Insights** - Single-source but high-value items

### Report Header (NEW)
Always include scan summary at the top:
```markdown
---
📊 **Scan Summary**: 14 sources • 156 items fetched • 89 unique stories (67 duplicates merged)
🔝 **Top Signal**: "Story Title" covered by 4 sources
---
```

### Item Format

**For multi-source stories (3+ sources):**
```markdown
### 1. [Headline Title](https://url.com)
**🔥 Covered by 4 sources**: Hacker News (529 pts) • Reddit (11K) • BBC • The Verge

One-line punchy summary.

- **Why it matters**: Technical details, context
- **Industry impact**: Market or industry implications
- **Keywords**: `#AI #Tech #Finance`
```

**For single-source stories:**
```markdown
### 5. [Headline Title](https://url.com)
**Source**: BBC News | **Time**: 2 hours ago | **Heat**: 500 upvotes

One-line punchy summary.

- **Why it matters**: Technical details, context
- **Keywords**: `#AI #Tech #Finance`
```

### Output Requirements
- **Title MUST be a Markdown link** to the original URL
- **Metadata line** must include Source, Time, and Heat/Score
- **Save report** to `reports/` with timestamped filename (e.g., `reports/tech_news_20260124_0800.md`)

## Time-Based Filtering

If user requests a specific time window (e.g., "past 6 hours"):
1. Prioritize items within the window
2. If sparse (<5 items), include high-value items from wider range
3. Mark supplementary items with ⚠️ or 🔥 annotations

## Example Prompts

| User Says | Action |
|-----------|--------|
| "Morning tech briefing" | Fetch `--source tech --limit 15 --deep`, generate newsletter-style report |
| "What's happening in AI?" | Fetch with expanded AI keywords, deep analysis |
| "Global news scan" | Fetch `--source all --limit 10 --deep`, comprehensive report |
| "Market news" | Fetch `--source finance --limit 15 --deep` |
| "HN top stories" | Fetch `--source hackernews --limit 20 --deep` |
