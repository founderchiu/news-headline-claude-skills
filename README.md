# 📰 English News Skill for Claude Code

A powerful news aggregator skill for [Claude Code](https://claude.ai/claude-code) that fetches real-time content from 14 major English-language sources across Tech, Global News, and Finance categories.

## Features

- **14 News Sources** — Comprehensive coverage across tech, global news, and finance
- **Smart Deduplication** — Automatically merges duplicate stories across sources using URL, title similarity, and content hashing
- **Deep Analysis Mode** — Fetch full article content for richer summaries
- **Keyword Filtering** — Smart keyword expansion for targeted searches
- **Reddit Stock Tracker** — Tracks most-discussed tickers on r/wallstreetbets, r/stocks, r/investing
- **Bilingual Output** — Headlines in English, analysis in Simplified Chinese

## Installation

### Prerequisites

- Python 3.8+
- Claude Code CLI

### Setup

1. Clone this repository into your Claude skills directory:

```bash
git clone https://github.com/founderchiu/news-headline-claude-skills.git ~/.claude/skills/english-news-skill
```

2. Install dependencies:

```bash
cd ~/.claude/skills/english-news-skill
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Sources

| Category | Sources |
|----------|---------|
| **Tech** | Hacker News, GitHub Trending, Product Hunt, Reddit (r/technology, r/programming), TechCrunch, Ars Technica, The Verge |
| **Global** | BBC News, Reuters, AP News |
| **Finance** | Bloomberg, Yahoo Finance, CNBC, Reddit Stocks (r/wallstreetbets, r/stocks, r/investing) |

## Usage

### Via Claude Code (Recommended)

Simply invoke the skill in Claude Code:

```
Use english-news-skill to give me a morning tech briefing
Use english-news-skill to scan all sources for AI news
Use english-news-skill to show me today's market pulse
```

### Direct Script Usage

```bash
# Single source
python3 scripts/fetch_news.py --source hackernews --limit 10 --deep

# Source groups
python3 scripts/fetch_news.py --source tech --limit 10 --deep
python3 scripts/fetch_news.py --source global --limit 10 --deep
python3 scripts/fetch_news.py --source finance --limit 10 --deep

# Full scan (all 14 sources)
python3 scripts/fetch_news.py --source all --limit 15 --deep

# Keyword filtering
python3 scripts/fetch_news.py --source tech --keyword "AI,LLM,GPT,Claude" --deep
```

### Command Arguments

| Argument | Description |
|----------|-------------|
| `--source` | Source name, group (`tech`, `global`, `finance`), or `all` |
| `--limit` | Max items per source (default: 10) |
| `--keyword` | Comma-separated keyword filter (case-insensitive) |
| `--deep` | Fetch full article content for deeper analysis |
| `--no-dedup` | Disable deduplication (raw output) |

### Individual Source Names

`hackernews`, `github`, `producthunt`, `reddit_tech`, `reddit_programming`, `techcrunch`, `arstechnica`, `theverge`, `bbc`, `reuters`, `apnews`, `bloomberg`, `yahoo_finance`, `cnbc`, `reddit_stocks`

## Smart Deduplication

Stories are automatically deduplicated across sources using:

- **URL matching** — After stripping tracking parameters
- **Title fuzzy matching** — 70% similarity threshold
- **Content hash matching** — For `--deep` mode

### Benefits

- Same story from HN + Reddit + BBC = 1 entry with multi-source attribution
- Multi-source coverage signals story importance
- Ranked by: `(source_count × 100) + normalized_heat + recency_bonus`

### Output Format

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

## Reddit Stock Tracker

Scans r/wallstreetbets, r/stocks, and r/investing for the top 10 most discussed stock tickers.

```bash
python3 scripts/fetch_news.py --source reddit_stocks --limit 10
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

## Example Prompts

| Prompt | What It Does |
|--------|--------------|
| "Morning tech briefing" | Fetches all tech sources with deep analysis |
| "What's happening in AI?" | Expands keywords, scans tech sources |
| "Global news scan" | Comprehensive report from all 14 sources |
| "Market news" | Finance sources with stock tracker |
| "HN top stories" | Hacker News deep dive |

## Project Structure

```
english-news-skill/
├── SKILL.md           # Skill definition for Claude Code
├── templates.md       # Interactive command menu
├── requirements.txt   # Python dependencies
├── scripts/
│   ├── fetch_news.py  # Main news fetcher
│   └── dedup.py       # Deduplication logic
├── docs/
│   └── plans/         # Design documents
└── reports/           # Generated reports (gitignored)
```

## Report Output

Reports are saved to `reports/` with timestamped filenames:

```
reports/tech_news_20260125_0800.md
reports/global_scan_20260125_1200.md
```

## Smart Keyword Expansion

The skill automatically expands simple keywords:

| User Input | Expanded To |
|------------|-------------|
| "AI" | AI, LLM, GPT, Claude, Gemini, OpenAI, Anthropic, Machine Learning, Neural, Agent |
| "crypto" | crypto, Bitcoin, Ethereum, blockchain, DeFi, Web3 |
| "Apple" | Apple, iPhone, Mac, iOS, macOS, iPad, Vision Pro |

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

Built for [Claude Code](https://claude.ai/claude-code) by [@founderchiu](https://github.com/founderchiu)
