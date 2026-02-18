#!/usr/bin/env python3
"""
English News Aggregator - Fetches news from major English-language sources.

Sources:
  - Tech: Hacker News, GitHub Trending, Product Hunt, Reddit (r/technology, r/programming),
          TechCrunch, Ars Technica, The Verge
  - Global: BBC News, Reuters, AP News
  - Finance: Bloomberg, Yahoo Finance, CNBC

Usage:
  python3 fetch_news.py --source hackernews --limit 10
  python3 fetch_news.py --source all --limit 15 --deep
  python3 fetch_news.py --source tech --keyword "AI,LLM" --deep
  python3 fetch_news.py --source all --no-dedup  # disable deduplication
"""

import argparse
import json
import requests
from bs4 import BeautifulSoup
import sys
import time
import re
import concurrent.futures
from datetime import datetime, timezone
from urllib.parse import quote

# Import deduplication module
from dedup import deduplicate

# Import time parser for ISO 8601 normalization
from utils.time_parser import parse_to_iso8601

# Import cache for diff mode
from cache import NewsCache, compute_diff

# Import formatters for output
from formatters import format_output

# Source type classification
SOURCE_TYPES = {
    # Aggregators: link to external content, discussions
    "Hacker News": "aggregator",
    "Reddit r/technology": "aggregator",
    "Reddit r/programming": "aggregator",
    "Reddit Stocks": "aggregator",
    "GitHub Trending": "aggregator",
    "Product Hunt": "aggregator",
    # Wire services: original reporting, syndicated
    "BBC News": "wire",
    "Reuters": "wire",
    "AP News": "wire",
    # Original reporting: first-party journalism (existing)
    "TechCrunch": "original_reporting",
    "Ars Technica": "original_reporting",
    "The Verge": "original_reporting",
    "Bloomberg": "original_reporting",
    "Yahoo Finance": "original_reporting",
    "CNBC": "original_reporting",
    # Core Financial (NEW)
    "Financial Times": "original_reporting",
    "Wall Street Journal": "original_reporting",
    "Reuters Breakingviews": "original_reporting",
    "The Economist": "original_reporting",
    # Trading-oriented (NEW)
    "MarketWatch": "original_reporting",
    "Barron's": "original_reporting",
    "Semafor Business": "original_reporting",
    "Axios Markets": "original_reporting",
    "FT Alphaville": "original_reporting",
    # AI/Tech Serious (NEW)
    "MIT Technology Review": "original_reporting",
    "The Information": "original_reporting",
    "Platformer": "original_reporting",
    "Stratechery": "original_reporting",
    "SemiAnalysis": "original_reporting",
    "The Decoder": "original_reporting",
    "State of AI": "original_reporting",
    # AI Labs & Research (NEW)
    "HuggingFace Blog": "original_reporting",
    "OpenAI Blog": "original_reporting",
    "Anthropic Blog": "original_reporting",
    "DeepMind Blog": "original_reporting",
    "Arxiv AI": "original_reporting",
    # Geopolitics & Policy (NEW)
    "Politico": "original_reporting",
    "Foreign Affairs": "original_reporting",
    "War on the Rocks": "original_reporting",
    "CSIS": "original_reporting",
    "CFR": "original_reporting",
    "Brookings": "original_reporting",
    "RAND": "original_reporting",
    # Social Media / Political Figures
    "Truth Social (Trump)": "social_media",
}

def get_source_type(source_name: str) -> str:
    """Get the source type for a given source name."""
    # Handle Reddit subreddits dynamically
    if source_name.startswith("Reddit r/"):
        return "aggregator"
    return SOURCE_TYPES.get(source_name, "unknown")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Per-domain rate limits (seconds between requests)
RATE_LIMITS = {
    "bloomberg.com": 2.0,
    "reuters.com": 1.5,
    "wsj.com": 2.0,
    "ft.com": 2.0,
    "nytimes.com": 1.5,
    "default": 0.5,
}

# Track last request time per domain
_last_request_time = {}
_rate_limit_lock = None  # Will be initialized lazily for thread safety

def _get_rate_limit(url: str) -> float:
    """Get the rate limit for a given URL's domain."""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        # Check for matching domain
        for key, limit in RATE_LIMITS.items():
            if key in domain:
                return limit
        return RATE_LIMITS["default"]
    except:
        return RATE_LIMITS["default"]

def _rate_limited_request(url: str, timeout: int = 10, retries: int = 2) -> requests.Response:
    """
    Make a rate-limited request with exponential backoff retries.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        retries: Number of retries on failure

    Returns:
        Response object

    Raises:
        requests.RequestException on final failure
    """
    import threading
    from urllib.parse import urlparse

    global _rate_limit_lock
    if _rate_limit_lock is None:
        _rate_limit_lock = threading.Lock()

    domain = urlparse(url).netloc.lower()
    rate_limit = _get_rate_limit(url)

    # Enforce rate limit
    with _rate_limit_lock:
        now = time.time()
        if domain in _last_request_time:
            elapsed = now - _last_request_time[domain]
            if elapsed < rate_limit:
                time.sleep(rate_limit - elapsed)
        _last_request_time[domain] = time.time()

    # Make request with retries
    last_exception = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.Timeout as e:
            last_exception = e
            if attempt < retries:
                # Exponential backoff
                time.sleep(2 ** attempt)
            continue
        except requests.RequestException as e:
            last_exception = e
            if attempt < retries:
                time.sleep(2 ** attempt)
            continue

    raise last_exception


def filter_items(items, keyword=None):
    """Filter items by keyword (case-insensitive, supports comma-separated keywords)."""
    if not keyword:
        return items
    keywords = [k.strip() for k in keyword.split(',') if k.strip()]
    pattern = '|'.join([re.escape(k) for k in keywords])
    regex = re.compile(pattern, re.IGNORECASE)
    return [item for item in items if regex.search(item.get('title', '') + ' ' + item.get('description', ''))]

def fetch_url_content(url, timeout=10, retries=2):
    """
    Fetch and extract main text content from a URL (truncated to 3000 chars).

    Uses rate limiting and exponential backoff retries.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        retries: Number of retries on failure

    Returns:
        Extracted text content (max 3000 chars) or empty string on failure
    """
    if not url or not url.startswith('http'):
        return ""
    try:
        response = _rate_limited_request(url, timeout=timeout, retries=retries)
        soup = BeautifulSoup(response.content, 'html.parser')
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.extract()
        text = soup.get_text(separator=' ', strip=True)
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text[:3000]
    except Exception:
        return ""

def enrich_items_with_content(items, max_workers=10):
    """Parallel fetch content for all items."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(fetch_url_content, item['url']): item for item in items}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                content = future.result()
                if content:
                    item['content'] = content
            except Exception:
                item['content'] = ""
    return items

# =============================================================================
# TECH SOURCES
# =============================================================================

def fetch_hackernews(limit=10, keyword=None):
    """Fetch from Hacker News front page."""
    base_url = "https://news.ycombinator.com"
    news_items = []
    page = 1
    max_pages = 5

    while len(news_items) < limit and page <= max_pages:
        url = f"{base_url}/news?p={page}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                break
        except:
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('.athing')
        if not rows:
            break

        page_items = []
        for row in rows:
            try:
                id_ = row.get('id')
                title_line = row.select_one('.titleline a')
                if not title_line:
                    continue
                title = title_line.get_text()
                link = title_line.get('href')

                score_span = soup.select_one(f'#score_{id_}')
                score = score_span.get_text() if score_span else "0 points"

                age_span = soup.select_one(f'.age a[href="item?id={id_}"]')
                time_str = age_span.get_text() if age_span else ""

                # Determine if this is an HN discussion or external link
                is_hn_discussion = link and link.startswith('item?id=')
                discussion_url = f"{base_url}/item?id={id_}"

                if is_hn_discussion:
                    link = discussion_url
                    original_url = None
                else:
                    original_url = link

                item = {
                    "source": "Hacker News",
                    "source_type": "aggregator",
                    "title": title,
                    "url": original_url or discussion_url,
                    "discussion_url": discussion_url,
                    "heat": score,
                    "time": time_str,
                    "time_iso": parse_to_iso8601(time_str),
                }
                if original_url:
                    item["original_url"] = original_url

                page_items.append(item)
            except:
                continue

        news_items.extend(filter_items(page_items, keyword))
        if len(news_items) >= limit:
            break
        page += 1
        time.sleep(0.3)

    return news_items[:limit]

def fetch_github(limit=10, keyword=None):
    """Fetch GitHub Trending repositories."""
    try:
        response = requests.get("https://github.com/trending", headers=HEADERS, timeout=10)
    except:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    items = []
    for article in soup.select('article.Box-row'):
        try:
            h2 = article.select_one('h2 a')
            if not h2:
                continue
            title = h2.get_text(strip=True).replace('\n', '').replace(' ', '')
            link = "https://github.com" + h2['href']

            desc = article.select_one('p')
            desc_text = desc.get_text(strip=True) if desc else ""

            stars_tag = article.select_one('a[href$="/stargazers"]')
            stars = stars_tag.get_text(strip=True) if stars_tag else ""

            items.append({
                "source": "GitHub Trending",
                "source_type": "aggregator",
                "title": f"{title} - {desc_text}",
                "url": link,
                "heat": f"{stars} stars",
                "time": "Today",
                "time_iso": parse_to_iso8601("Today"),
            })
        except:
            continue
    return filter_items(items, keyword)[:limit]

def fetch_producthunt(limit=10, keyword=None):
    """Fetch from Product Hunt RSS feed."""
    try:
        response = requests.get("https://www.producthunt.com/feed", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')
        if not soup.find('item'):
            soup = BeautifulSoup(response.text, 'html.parser')

        items = []
        for entry in soup.find_all(['item', 'entry']):
            title = entry.find('title').get_text(strip=True)
            link_tag = entry.find('link')
            url = link_tag.get('href') or link_tag.get_text(strip=True) if link_tag else ""

            pub_tag = entry.find('pubDate') or entry.find('published')
            pub = pub_tag.get_text(strip=True) if pub_tag else ""

            items.append({
                "source": "Product Hunt",
                "source_type": "aggregator",
                "title": title,
                "url": url,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": "Featured"
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_reddit(limit=10, keyword=None, subreddit="technology"):
    """Fetch from Reddit subreddit (JSON API)."""
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50"
        headers = {**HEADERS, "Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        items = []
        for post in data['data']['children']:
            p = post['data']
            if p.get('stickied'):
                continue

            discussion_url = f"https://reddit.com{p['permalink']}"
            time_str = datetime.fromtimestamp(p['created_utc'], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')

            # Check if this links to external content or is a self post
            external_url = p.get('url', '')
            is_self_post = p.get('is_self', False) or external_url.startswith('https://reddit.com') or external_url.startswith('https://www.reddit.com')

            item = {
                "source": f"Reddit r/{subreddit}",
                "source_type": "aggregator",
                "title": p['title'],
                "url": external_url if not is_self_post else discussion_url,
                "discussion_url": discussion_url,
                "heat": f"{p['score']} upvotes",
                "time": time_str,
                "time_iso": parse_to_iso8601(time_str),
            }
            if not is_self_post and external_url:
                item["original_url"] = external_url

            items.append(item)
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_reddit_tech(limit=10, keyword=None):
    """Fetch from r/technology."""
    return fetch_reddit(limit, keyword, "technology")

def fetch_reddit_programming(limit=10, keyword=None):
    """Fetch from r/programming."""
    return fetch_reddit(limit, keyword, "programming")

def fetch_techcrunch(limit=10, keyword=None):
    """Fetch from TechCrunch RSS."""
    try:
        response = requests.get("https://techcrunch.com/feed/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True)
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "TechCrunch",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_arstechnica(limit=10, keyword=None):
    """Fetch from Ars Technica RSS."""
    try:
        response = requests.get("https://feeds.arstechnica.com/arstechnica/index", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Ars Technica",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_theverge(limit=10, keyword=None):
    """Fetch from The Verge RSS."""
    try:
        response = requests.get("https://www.theverge.com/rss/index.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for entry in soup.find_all('entry'):
            title = entry.find('title').get_text(strip=True)
            link = entry.find('link')['href'] if entry.find('link') else ""
            pub = entry.find('published').get_text(strip=True) if entry.find('published') else ""

            items.append({
                "source": "The Verge",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# GLOBAL NEWS SOURCES
# =============================================================================

def fetch_bbc(limit=10, keyword=None):
    """Fetch from BBC News RSS."""
    try:
        response = requests.get("https://feeds.bbci.co.uk/news/rss.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "BBC News",
                "source_type": "wire",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_reuters(limit=10, keyword=None):
    """Fetch from Reuters RSS."""
    try:
        response = requests.get("https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Reuters",
                "source_type": "wire",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_apnews(limit=10, keyword=None):
    """Fetch from AP News RSS."""
    try:
        response = requests.get("https://rsshub.app/apnews/topics/apf-topnews", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "AP News",
                "source_type": "wire",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# FINANCE SOURCES
# =============================================================================

def fetch_bloomberg(limit=10, keyword=None):
    """Fetch from Bloomberg (via RSS)."""
    try:
        # Bloomberg doesn't have public RSS, try scraping main page
        response = requests.get("https://www.bloomberg.com/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        items = []
        # Try to find article headlines
        for article in soup.select('article, [data-component="headline"]')[:limit*2]:
            title_el = article.find(['h1', 'h2', 'h3', 'a'])
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get('href', '')
            if link and not link.startswith('http'):
                link = f"https://www.bloomberg.com{link}"

            if title and len(title) > 10:
                items.append({
                    "source": "Bloomberg",
                    "source_type": "original_reporting",
                    "title": title,
                    "url": link,
                    "time": "Recent",
                    "time_iso": parse_to_iso8601("Recent"),
                    "heat": ""
                })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_yahoo_finance(limit=10, keyword=None):
    """Fetch from Yahoo Finance RSS."""
    try:
        response = requests.get("https://finance.yahoo.com/news/rssindex", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Yahoo Finance",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_cnbc(limit=10, keyword=None):
    """Fetch from CNBC RSS."""
    try:
        response = requests.get("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "CNBC",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_reddit_stocks(limit=10, keyword=None):
    """
    Fetch top discussed stocks from Reddit finance subreddits.
    Scans r/wallstreetbets, r/stocks, r/investing for stock ticker mentions.
    """
    import collections

    # Common stock ticker pattern (1-5 uppercase letters, often prefixed with $)
    ticker_pattern = re.compile(r'\$?([A-Z]{1,5})\b')

    # Common words to exclude (not stock tickers)
    exclude_words = {
        'I', 'A', 'AN', 'THE', 'TO', 'IS', 'IT', 'IN', 'ON', 'AT', 'BY', 'OR',
        'AND', 'FOR', 'OF', 'BE', 'AS', 'SO', 'IF', 'AM', 'PM', 'US', 'UK',
        'CEO', 'CFO', 'IPO', 'ETF', 'SEC', 'FDA', 'IMO', 'IMHO', 'TIL', 'PSA',
        'DD', 'TA', 'EPS', 'PE', 'GDP', 'CPI', 'FED', 'USD', 'EUR', 'GBP',
        'NYSE', 'NASDAQ', 'SP', 'DOW', 'ATH', 'ATL', 'EOD', 'AH', 'PM',
        'YOLO', 'FOMO', 'FUD', 'HODL', 'WSB', 'OP', 'OC', 'TL', 'DR', 'TLDR',
        'AI', 'ML', 'API', 'IT', 'IV', 'DTE', 'OTM', 'ITM', 'ATM', 'PT',
        'EDIT', 'UPDATE', 'NEW', 'OLD', 'BIG', 'TOP', 'ALL', 'ANY', 'NOW',
        'NOT', 'BUT', 'CAN', 'HAS', 'WAS', 'ARE', 'YOU', 'YOUR', 'MY', 'WE',
        'RED', 'GREEN', 'UP', 'DOWN', 'BUY', 'SELL', 'HOLD', 'LONG', 'SHORT'
    }

    # Subreddits to scan
    subreddits = ['wallstreetbets', 'stocks', 'investing']
    ticker_counts = collections.Counter()
    ticker_posts = collections.defaultdict(list)  # ticker -> list of post info

    for subreddit in subreddits:
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50"
            headers = {**HEADERS, "Accept": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            for post in data['data']['children']:
                p = post['data']
                if p.get('stickied'):
                    continue

                # Extract tickers from title and selftext
                text = p['title'] + ' ' + (p.get('selftext', '') or '')
                matches = ticker_pattern.findall(text)

                for ticker in matches:
                    if ticker not in exclude_words and len(ticker) >= 2:
                        ticker_counts[ticker] += 1
                        # Store post info for this ticker
                        if len(ticker_posts[ticker]) < 3:  # Keep top 3 posts per ticker
                            ticker_posts[ticker].append({
                                'title': p['title'],
                                'url': f"https://reddit.com{p['permalink']}",
                                'score': p['score'],
                                'subreddit': subreddit
                            })
        except:
            continue

        time.sleep(0.3)

    # Build items for top discussed tickers
    items = []
    for ticker, count in ticker_counts.most_common(limit):
        posts = ticker_posts[ticker]
        top_post = posts[0] if posts else None

        # Get stock info URL
        stock_url = f"https://finance.yahoo.com/quote/{ticker}"

        # Build description from top posts
        subreddits_mentioned = list(set(p['subreddit'] for p in posts))

        items.append({
            "source": "Reddit Stocks",
            "source_type": "aggregator",
            "title": f"${ticker} - Mentioned {count}x across {', '.join(f'r/{s}' for s in subreddits_mentioned)}",
            "url": stock_url,
            "heat": f"{count} mentions",
            "time": "Today",
            "time_iso": parse_to_iso8601("Today"),
            "description": top_post['title'] if top_post else "",
            "top_post_url": top_post['url'] if top_post else ""
        })

    return filter_items(items, keyword)[:limit]

# =============================================================================
# CORE FINANCIAL SOURCES (NEW)
# =============================================================================

def fetch_ft(limit=10, keyword=None):
    """Fetch from Financial Times RSS."""
    try:
        response = requests.get("https://www.ft.com/rss/home", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Financial Times",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_wsj(limit=10, keyword=None):
    """Fetch from Wall Street Journal RSS."""
    try:
        response = requests.get("https://feeds.a.dj.com/rss/RSSWorldNews.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Wall Street Journal",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_reuters_breakingviews(limit=10, keyword=None):
    """Fetch from Reuters Breakingviews RSS."""
    try:
        response = requests.get("https://www.reuters.com/arc/outboundfeeds/v4/section/breakingviews/?outputType=xml&client=google", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Reuters Breakingviews",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_economist(limit=10, keyword=None):
    """Fetch from The Economist RSS."""
    try:
        response = requests.get("https://www.economist.com/rss", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "The Economist",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# TRADING-ORIENTED SOURCES (NEW)
# =============================================================================

def fetch_marketwatch(limit=10, keyword=None):
    """Fetch from MarketWatch RSS."""
    try:
        response = requests.get("https://feeds.marketwatch.com/marketwatch/topstories/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "MarketWatch",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_barrons(limit=10, keyword=None):
    """Fetch from Barron's RSS."""
    try:
        response = requests.get("https://www.barrons.com/xml/rss/3_7031.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Barron's",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_semafor(limit=10, keyword=None):
    """Fetch from Semafor Business RSS."""
    try:
        response = requests.get("https://www.semafor.com/rss/business", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Semafor Business",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_axios_markets(limit=10, keyword=None):
    """Fetch from Axios Markets RSS."""
    try:
        response = requests.get("https://www.axios.com/feed/markets", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Axios Markets",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# AI/TECH SERIOUS SOURCES (NEW)
# =============================================================================

def fetch_mit_tech_review(limit=10, keyword=None):
    """Fetch from MIT Technology Review RSS."""
    try:
        response = requests.get("https://www.technologyreview.com/feed/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "MIT Technology Review",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_theinformation(limit=10, keyword=None):
    """Fetch from The Information RSS (headlines only - paywalled)."""
    try:
        response = requests.get("https://www.theinformation.com/feed", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "The Information",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": "Premium"
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_platformer(limit=10, keyword=None):
    """Fetch from Platformer (Casey Newton) RSS."""
    try:
        response = requests.get("https://www.platformer.news/rss/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Platformer",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_stratechery(limit=10, keyword=None):
    """Fetch from Stratechery RSS."""
    try:
        response = requests.get("https://stratechery.com/feed/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Stratechery",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_semianalysis(limit=10, keyword=None):
    """Fetch from SemiAnalysis RSS."""
    try:
        response = requests.get("https://www.semianalysis.com/feed", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "SemiAnalysis",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_thedecoder(limit=10, keyword=None):
    """Fetch from The Decoder RSS."""
    try:
        response = requests.get("https://the-decoder.com/feed/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "The Decoder",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_stateofai(limit=10, keyword=None):
    """Fetch from State of AI newsletter RSS."""
    try:
        response = requests.get("https://www.stateof.ai/rss.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "State of AI",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# OPEN SOURCE & DEV SOURCES (NEW)
# =============================================================================

def fetch_huggingface(limit=10, keyword=None):
    """Fetch from HuggingFace Blog RSS."""
    try:
        response = requests.get("https://huggingface.co/blog/feed.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for entry in soup.find_all('entry'):
            title = entry.find('title').get_text(strip=True)
            link = entry.find('link')['href'] if entry.find('link') else ""
            pub = entry.find('published').get_text(strip=True) if entry.find('published') else ""

            items.append({
                "source": "HuggingFace Blog",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_openai_blog(limit=10, keyword=None):
    """Fetch from OpenAI Blog RSS."""
    try:
        response = requests.get("https://openai.com/blog/rss/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "OpenAI Blog",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_anthropic_blog(limit=10, keyword=None):
    """Fetch from Anthropic Blog/Research RSS."""
    try:
        # Try research feed first
        response = requests.get("https://www.anthropic.com/research/rss.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all(['item', 'entry']):
            title_el = item.find('title')
            title = title_el.get_text(strip=True) if title_el else ""
            link_el = item.find('link')
            link = link_el.get('href') or link_el.get_text(strip=True) if link_el else ""
            pub_el = item.find('pubDate') or item.find('published')
            pub = pub_el.get_text(strip=True) if pub_el else ""

            items.append({
                "source": "Anthropic Blog",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_deepmind_blog(limit=10, keyword=None):
    """Fetch from Google DeepMind Blog RSS."""
    try:
        response = requests.get("https://deepmind.google/blog/rss.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all(['item', 'entry']):
            title_el = item.find('title')
            title = title_el.get_text(strip=True) if title_el else ""
            link_el = item.find('link')
            link = link_el.get('href') or link_el.get_text(strip=True) if link_el else ""
            pub_el = item.find('pubDate') or item.find('published')
            pub = pub_el.get_text(strip=True) if pub_el else ""

            items.append({
                "source": "DeepMind Blog",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_arxiv_ai(limit=10, keyword=None):
    """Fetch from Arxiv AI/ML category RSS."""
    try:
        # cs.AI - Artificial Intelligence, cs.LG - Machine Learning
        response = requests.get("https://rss.arxiv.org/rss/cs.AI+cs.LG", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            # Clean up arxiv titles (often have category prefixes)
            title = re.sub(r'^\[.*?\]\s*', '', title)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""
            desc = item.find('description').get_text(strip=True) if item.find('description') else ""

            items.append({
                "source": "Arxiv AI",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": "",
                "description": desc[:500] if desc else ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# GEOPOLITICS & POLICY SOURCES (NEW)
# =============================================================================

def fetch_politico(limit=10, keyword=None):
    """Fetch from Politico RSS."""
    try:
        response = requests.get("https://www.politico.com/rss/politicopicks.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Politico",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_foreign_affairs(limit=10, keyword=None):
    """Fetch from Foreign Affairs RSS."""
    try:
        response = requests.get("https://www.foreignaffairs.com/rss.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Foreign Affairs",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_warontherocks(limit=10, keyword=None):
    """Fetch from War on the Rocks RSS."""
    try:
        response = requests.get("https://warontherocks.com/feed/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "War on the Rocks",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_csis(limit=10, keyword=None):
    """Fetch from CSIS (Center for Strategic and International Studies) RSS."""
    try:
        response = requests.get("https://www.csis.org/analysis/rss.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "CSIS",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_cfr(limit=10, keyword=None):
    """Fetch from Council on Foreign Relations RSS."""
    try:
        response = requests.get("https://www.cfr.org/rss/global", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "CFR",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_brookings(limit=10, keyword=None):
    """Fetch from Brookings Institution RSS."""
    try:
        response = requests.get("https://www.brookings.edu/feed/", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "Brookings",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_rand(limit=10, keyword=None):
    """Fetch from RAND Corporation RSS."""
    try:
        response = requests.get("https://www.rand.org/blog.xml", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "RAND",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

def fetch_ft_alphaville(limit=10, keyword=None):
    """Fetch from FT Alphaville RSS."""
    try:
        response = requests.get("https://www.ft.com/alphaville?format=rss", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'xml')

        items = []
        for item in soup.find_all('item'):
            title = item.find('title').get_text(strip=True)
            link = item.find('link').get_text(strip=True) if item.find('link') else ""
            pub = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""

            items.append({
                "source": "FT Alphaville",
                "source_type": "original_reporting",
                "title": title,
                "url": link,
                "time": pub,
                "time_iso": parse_to_iso8601(pub),
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# SOCIAL MEDIA / POLITICAL FIGURES
# =============================================================================

def fetch_truthsocial(limit=10, keyword=None):
    """
    Fetch Trump's latest posts from Truth Social.

    Tries multiple methods:
    1. trumpstruth.org RSS feed (most reliable - run by Defending Democracy Together)
    2. RSSHub (if available)
    3. Direct profile scraping
    """
    items = []

    # Method 1: trumpstruth.org - dedicated Trump Truth Social archive with RSS
    try:
        response = requests.get("https://trumpstruth.org/feed", headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'xml')
            for item in soup.find_all('item'):
                title_el = item.find('title')
                title = title_el.get_text(strip=True) if title_el else ""

                # Get full content from description - it contains the actual post
                desc_el = item.find('description')
                if desc_el:
                    # Parse the HTML content to extract clean text
                    desc_html = desc_el.get_text(strip=True)
                    desc_soup = BeautifulSoup(desc_html, 'html.parser')
                    desc_text = desc_soup.get_text(separator=' ', strip=True)
                    # Use description as title if it's more complete
                    if desc_text and (not title or title.startswith('[No Title]') or len(desc_text) > len(title)):
                        title = desc_text[:250] + "..." if len(desc_text) > 250 else desc_text

                link_el = item.find('link')
                link = link_el.get_text(strip=True) if link_el else ""

                pub_el = item.find('pubDate')
                pub = pub_el.get_text(strip=True) if pub_el else ""

                # Skip empty posts or image/video-only posts
                if not title or title.startswith("[No Title]"):
                    continue

                items.append({
                    "source": "Truth Social (Trump)",
                    "source_type": "social_media",
                    "title": title,
                    "url": link,
                    "time": pub,
                    "time_iso": parse_to_iso8601(pub),
                    "heat": ""
                })

            if items:
                return filter_items(items, keyword)[:limit]
    except Exception as e:
        sys.stderr.write(f"trumpstruth.org fetch error: {e}\n")

    # Method 2: Try RSSHub instances
    rsshub_instances = [
        "https://rsshub.app/truthsocial/user/realDonaldTrump",
        "https://rss.fatpandac.com/truthsocial/user/realDonaldTrump",
    ]

    for rsshub_url in rsshub_instances:
        try:
            response = requests.get(rsshub_url, headers=HEADERS, timeout=10)
            if response.status_code == 200 and '<?xml' in response.text[:100]:
                soup = BeautifulSoup(response.text, 'xml')
                for item in soup.find_all('item'):
                    title_el = item.find('title')
                    title = title_el.get_text(strip=True) if title_el else ""

                    if not title or title == "New Truth":
                        desc_el = item.find('description')
                        if desc_el:
                            desc_text = desc_el.get_text(strip=True)
                            title = desc_text[:150] + "..." if len(desc_text) > 150 else desc_text

                    link_el = item.find('link')
                    link = link_el.get_text(strip=True) if link_el else ""

                    pub_el = item.find('pubDate')
                    pub = pub_el.get_text(strip=True) if pub_el else ""

                    items.append({
                        "source": "Truth Social (Trump)",
                        "source_type": "social_media",
                        "title": title,
                        "url": link,
                        "time": pub,
                        "time_iso": parse_to_iso8601(pub),
                        "heat": ""
                    })
                if items:
                    return filter_items(items, keyword)[:limit]
        except:
            continue

    # Method 2: Direct scraping from Truth Social profile
    try:
        profile_url = "https://truthsocial.com/@realDonaldTrump"
        response = requests.get(profile_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Truth Social uses React, so we need to look for JSON data or status elements
        # Look for status/post containers
        for post in soup.select('[data-testid="status"], .status, article')[:limit*2]:
            try:
                # Try to extract post content
                content_el = post.select_one('.status__content, .post-content, p')
                if content_el:
                    text = content_el.get_text(strip=True)
                    title = text[:150] + "..." if len(text) > 150 else text

                    # Try to find the permalink
                    link_el = post.select_one('a[href*="/posts/"], a.status__relative-time')
                    link = link_el.get('href', '') if link_el else profile_url
                    if link and not link.startswith('http'):
                        link = f"https://truthsocial.com{link}"

                    # Try to find timestamp
                    time_el = post.select_one('time, .relative-time')
                    time_str = time_el.get('datetime', '') or time_el.get_text(strip=True) if time_el else ""

                    items.append({
                        "source": "Truth Social (Trump)",
                        "source_type": "social_media",
                        "title": title,
                        "url": link,
                        "time": time_str,
                        "time_iso": parse_to_iso8601(time_str),
                        "heat": ""
                    })
            except:
                continue

        if items:
            return filter_items(items, keyword)[:limit]
    except Exception as e:
        sys.stderr.write(f"Truth Social direct scrape error: {e}\n")

    # Method 3: Return placeholder with link to profile if all methods fail
    if not items:
        sys.stderr.write("Truth Social: All fetch methods failed. Returning profile link.\n")
        items.append({
            "source": "Truth Social (Trump)",
            "source_type": "social_media",
            "title": "View Trump's latest posts on Truth Social",
            "url": "https://truthsocial.com/@realDonaldTrump",
            "time": "Now",
            "time_iso": datetime.now(timezone.utc).isoformat(),
            "heat": "",
            "description": "Direct API access unavailable. Visit profile for latest posts."
        })

    return filter_items(items, keyword)[:limit]

# =============================================================================
# MAIN
# =============================================================================

SOURCES_MAP = {
    # Tech (Original)
    'hackernews': fetch_hackernews,
    'github': fetch_github,
    'producthunt': fetch_producthunt,
    'reddit_tech': fetch_reddit_tech,
    'reddit_programming': fetch_reddit_programming,
    'techcrunch': fetch_techcrunch,
    'arstechnica': fetch_arstechnica,
    'theverge': fetch_theverge,
    # Global (Original)
    'bbc': fetch_bbc,
    'reuters': fetch_reuters,
    'apnews': fetch_apnews,
    # Finance (Original)
    'bloomberg': fetch_bloomberg,
    'yahoo_finance': fetch_yahoo_finance,
    'cnbc': fetch_cnbc,
    'reddit_stocks': fetch_reddit_stocks,
    # Core Financial (NEW)
    'ft': fetch_ft,
    'wsj': fetch_wsj,
    'reuters_breakingviews': fetch_reuters_breakingviews,
    'economist': fetch_economist,
    # Trading-oriented (NEW)
    'marketwatch': fetch_marketwatch,
    'barrons': fetch_barrons,
    'semafor': fetch_semafor,
    'axios_markets': fetch_axios_markets,
    # AI/Tech Serious (NEW)
    'mit_tech_review': fetch_mit_tech_review,
    'theinformation': fetch_theinformation,
    'platformer': fetch_platformer,
    'stratechery': fetch_stratechery,
    'semianalysis': fetch_semianalysis,
    'thedecoder': fetch_thedecoder,
    'stateofai': fetch_stateofai,
    # Open Source & Dev (NEW)
    'huggingface': fetch_huggingface,
    'openai_blog': fetch_openai_blog,
    'anthropic_blog': fetch_anthropic_blog,
    'deepmind_blog': fetch_deepmind_blog,
    'arxiv_ai': fetch_arxiv_ai,
    # Geopolitics & Policy (NEW)
    'politico': fetch_politico,
    'foreign_affairs': fetch_foreign_affairs,
    'warontherocks': fetch_warontherocks,
    'csis': fetch_csis,
    'cfr': fetch_cfr,
    'brookings': fetch_brookings,
    'rand': fetch_rand,
    'ft_alphaville': fetch_ft_alphaville,
    # Social Media / Political Figures
    'truthsocial': fetch_truthsocial,
}

SOURCE_GROUPS = {
    # Original groups
    'tech': ['hackernews', 'github', 'producthunt', 'reddit_tech', 'reddit_programming', 'techcrunch', 'arstechnica', 'theverge'],
    'global': ['bbc', 'reuters', 'apnews'],
    'finance': ['bloomberg', 'yahoo_finance', 'cnbc', 'reddit_stocks'],
    # New groups
    'finance_core': ['ft', 'wsj', 'bloomberg', 'reuters_breakingviews', 'economist'],
    'markets': ['marketwatch', 'barrons', 'semafor', 'axios_markets', 'ft_alphaville', 'yahoo_finance', 'cnbc', 'reddit_stocks'],
    'ai_research': ['mit_tech_review', 'theinformation', 'platformer', 'stratechery', 'semianalysis', 'thedecoder', 'stateofai'],
    'ai_labs': ['openai_blog', 'anthropic_blog', 'deepmind_blog', 'huggingface', 'arxiv_ai'],
    'geopolitics': ['politico', 'foreign_affairs', 'warontherocks', 'csis', 'cfr', 'brookings', 'rand'],
    'policy': ['politico', 'foreign_affairs', 'brookings', 'rand', 'csis', 'cfr'],
    # Social media / political figures
    'trump': ['truthsocial'],
    # Composite groups
    'all_finance': ['ft', 'wsj', 'bloomberg', 'reuters_breakingviews', 'economist', 'marketwatch', 'barrons', 'semafor', 'axios_markets', 'ft_alphaville', 'yahoo_finance', 'cnbc', 'reddit_stocks'],
    'all_ai': ['hackernews', 'github', 'mit_tech_review', 'theinformation', 'platformer', 'stratechery', 'semianalysis', 'thedecoder', 'stateofai', 'openai_blog', 'anthropic_blog', 'deepmind_blog', 'huggingface', 'arxiv_ai'],
    'all_politics': ['politico', 'foreign_affairs', 'warontherocks', 'csis', 'cfr', 'brookings', 'rand', 'truthsocial'],
    'all': list(SOURCES_MAP.keys()),
}

def main():
    parser = argparse.ArgumentParser(description='Fetch news from English sources')
    parser.add_argument('--source', default='all',
                        help='Source(s): hackernews, github, producthunt, reddit_tech, reddit_programming, techcrunch, arstechnica, theverge, bbc, reuters, apnews, bloomberg, yahoo_finance, cnbc, OR groups: tech, global, finance, all')
    parser.add_argument('--limit', type=int, default=10, help='Limit per source (default: 10)')
    parser.add_argument('--keyword', help='Comma-separated keyword filter')
    parser.add_argument('--deep', action='store_true', help='Fetch full article content')
    parser.add_argument('--no-dedup', action='store_true', dest='no_dedup',
                        help='Disable deduplication (output raw items)')
    parser.add_argument('--diff', action='store_true',
                        help='Show changes since last run (new/dropped/rank changes)')
    parser.add_argument('--format', choices=['json', 'md', 'markdown', 'slack'],
                        default='json', help='Output format (default: json)')
    parser.add_argument('--rank-by', choices=['trending', 'signals', 'combined'],
                        default='combined', dest='rank_by',
                        help='Ranking strategy: trending (social heat), signals (credibility), combined (default)')

    args = parser.parse_args()

    # Resolve source groups
    to_run = []
    sources_requested = [s.strip() for s in args.source.split(',')]

    for src in sources_requested:
        if src in SOURCE_GROUPS:
            for s in SOURCE_GROUPS[src]:
                if SOURCES_MAP[s] not in to_run:
                    to_run.append(SOURCES_MAP[s])
        elif src in SOURCES_MAP:
            if SOURCES_MAP[src] not in to_run:
                to_run.append(SOURCES_MAP[src])

    results = []
    for func in to_run:
        try:
            items = func(args.limit, args.keyword)
            results.extend(items)
        except Exception as e:
            sys.stderr.write(f"Error fetching {func.__name__}: {e}\n")

    if args.deep and results:
        sys.stderr.write(f"Deep fetching content for {len(results)} items...\n")
        results = enrich_items_with_content(results)

    # Apply deduplication (unless --no-dedup)
    if args.no_dedup:
        # Raw output format (backward compatible)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        # Deduplicated output with meta stats
        deduped_items, meta = deduplicate(results, rank_by=args.rank_by)
        meta['fetched_at'] = datetime.now(timezone.utc).isoformat()

        # Handle diff mode
        if args.diff:
            cache = NewsCache()
            run_id = args.source  # Use source as run identifier

            # Get previous run
            previous_run = cache.get_last_run(run_id)

            if previous_run and 'stories' in previous_run:
                diff = compute_diff(deduped_items, previous_run['stories'])
                meta['diff'] = diff
                sys.stderr.write(
                    f"Diff: {diff['summary']['new_count']} new, "
                    f"{diff['summary']['dropped_count']} dropped, "
                    f"{diff['summary']['changed_count']} rank changes\n"
                )
            else:
                meta['diff'] = {
                    'new_stories': deduped_items,
                    'dropped_stories': [],
                    'rank_changes': [],
                    'summary': {
                        'new_count': len(deduped_items),
                        'dropped_count': 0,
                        'changed_count': 0,
                        'note': 'First run - no previous data to compare'
                    }
                }
                sys.stderr.write("First run - saving baseline for future diffs\n")

            # Save current run for next comparison
            cache.save_last_run({'meta': meta, 'stories': deduped_items}, run_id)

        # Output in requested format
        print(format_output(deduped_items, meta, args.format))

if __name__ == "__main__":
    main()
