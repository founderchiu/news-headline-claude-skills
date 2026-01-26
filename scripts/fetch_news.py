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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def filter_items(items, keyword=None):
    """Filter items by keyword (case-insensitive, supports comma-separated keywords)."""
    if not keyword:
        return items
    keywords = [k.strip() for k in keyword.split(',') if k.strip()]
    pattern = '|'.join([re.escape(k) for k in keywords])
    regex = re.compile(pattern, re.IGNORECASE)
    return [item for item in items if regex.search(item.get('title', '') + ' ' + item.get('description', ''))]

def fetch_url_content(url):
    """Fetch and extract main text content from a URL (truncated to 3000 chars)."""
    if not url or not url.startswith('http'):
        return ""
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        response.raise_for_status()
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

                if link and link.startswith('item?id='):
                    link = f"{base_url}/{link}"

                page_items.append({
                    "source": "Hacker News",
                    "title": title,
                    "url": link,
                    "heat": score,
                    "time": time_str
                })
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
                "title": f"{title} - {desc_text}",
                "url": link,
                "heat": f"{stars} stars",
                "time": "Today"
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
                "title": title,
                "url": url,
                "time": pub,
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
            items.append({
                "source": f"Reddit r/{subreddit}",
                "title": p['title'],
                "url": f"https://reddit.com{p['permalink']}",
                "heat": f"{p['score']} upvotes",
                "time": datetime.fromtimestamp(p['created_utc']).strftime('%Y-%m-%d %H:%M')
            })
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
                "title": title,
                "url": link,
                "time": pub,
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
                "title": title,
                "url": link,
                "time": pub,
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
                "title": title,
                "url": link,
                "time": pub,
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
                "title": title,
                "url": link,
                "time": pub,
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
                "title": title,
                "url": link,
                "time": pub,
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
                "title": title,
                "url": link,
                "time": pub,
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
                    "title": title,
                    "url": link,
                    "time": "Recent",
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
                "title": title,
                "url": link,
                "time": pub,
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
                "title": title,
                "url": link,
                "time": pub,
                "heat": ""
            })
        return filter_items(items, keyword)[:limit]
    except:
        return []

# =============================================================================
# MAIN
# =============================================================================

SOURCES_MAP = {
    # Tech
    'hackernews': fetch_hackernews,
    'github': fetch_github,
    'producthunt': fetch_producthunt,
    'reddit_tech': fetch_reddit_tech,
    'reddit_programming': fetch_reddit_programming,
    'techcrunch': fetch_techcrunch,
    'arstechnica': fetch_arstechnica,
    'theverge': fetch_theverge,
    # Global
    'bbc': fetch_bbc,
    'reuters': fetch_reuters,
    'apnews': fetch_apnews,
    # Finance
    'bloomberg': fetch_bloomberg,
    'yahoo_finance': fetch_yahoo_finance,
    'cnbc': fetch_cnbc,
}

SOURCE_GROUPS = {
    'tech': ['hackernews', 'github', 'producthunt', 'reddit_tech', 'reddit_programming', 'techcrunch', 'arstechnica', 'theverge'],
    'global': ['bbc', 'reuters', 'apnews'],
    'finance': ['bloomberg', 'yahoo_finance', 'cnbc'],
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
        deduped_items, meta = deduplicate(results)
        meta['fetched_at'] = datetime.now(timezone.utc).isoformat()

        output = {
            'meta': meta,
            'stories': deduped_items
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
