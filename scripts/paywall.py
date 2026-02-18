#!/usr/bin/env python3
"""
Paywall detection for English News Skill.

Detects paywalled content and returns structured partial results
instead of failing silently.
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse


# CSS selectors that indicate a paywall
PAYWALL_CSS_SELECTORS = [
    '.paywall',
    '.subscription-wall',
    '.premium-content-gate',
    '[data-paywall]',
    '.regwall',
    '.signin-wall',
    '.article-paywall',
    '.piano-inline-offer',
    '.pw-container',
    '.subscriber-only',
    '.premium-content',
    '.metered-content',
]

# Text patterns that indicate a paywall
PAYWALL_TEXT_PATTERNS = [
    r'subscribe to (read|continue|access)',
    r'sign in to read',
    r'this (article|story) is for (subscribers|members)',
    r'you.ve reached your (free article|reading) limit',
    r'to continue reading',
    r'create a free account',
    r'subscribe now',
    r'already a subscriber\?',
    r'full article is only available',
    r'premium content',
    r'member(-)?only',
]

# Known paywalled domains with their paywall types
KNOWN_PAYWALLED_DOMAINS = {
    'bloomberg.com': {'type': 'soft', 'free_articles': 3},
    'wsj.com': {'type': 'hard'},
    'ft.com': {'type': 'hard'},
    'nytimes.com': {'type': 'metered', 'free_articles': 5},
    'economist.com': {'type': 'metered', 'free_articles': 3},
    'washingtonpost.com': {'type': 'metered', 'free_articles': 5},
    'businessinsider.com': {'type': 'soft'},
    'wired.com': {'type': 'metered'},
    'theathletic.com': {'type': 'hard'},
    'seekingalpha.com': {'type': 'soft'},
    'barrons.com': {'type': 'hard'},
}


def get_domain(url: str) -> str:
    """Extract the main domain from a URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        # Strip www prefix
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc
    except:
        return ''


def is_known_paywalled_domain(url: str) -> Optional[Dict]:
    """
    Check if URL is from a known paywalled domain.

    Returns:
        Dict with paywall info if known, None otherwise
    """
    domain = get_domain(url)

    for paywalled_domain, info in KNOWN_PAYWALLED_DOMAINS.items():
        if paywalled_domain in domain:
            return info

    return None


def detect_paywall_in_html(html: str) -> Dict:
    """
    Detect paywall indicators in HTML content.

    Args:
        html: Raw HTML content

    Returns:
        Dict with detection results
    """
    signals_found = []
    confidence = 0.0

    html_lower = html.lower()

    # Check for CSS class/selector indicators
    for selector in PAYWALL_CSS_SELECTORS:
        # Convert selector to a pattern
        if selector.startswith('.'):
            pattern = f'class=["\']{selector[1:]}["\']'
        elif selector.startswith('['):
            attr = selector[1:-1]
            if '=' in attr:
                attr_name = attr.split('=')[0]
                pattern = f'{attr_name}='
            else:
                pattern = attr
        else:
            pattern = selector

        if re.search(pattern, html_lower):
            signals_found.append(f'css:{selector}')
            confidence += 0.3

    # Check for text patterns
    for pattern in PAYWALL_TEXT_PATTERNS:
        if re.search(pattern, html_lower):
            signals_found.append(f'text:{pattern[:30]}...')
            confidence += 0.2

    # Cap confidence at 1.0
    confidence = min(1.0, confidence)

    return {
        'signals_found': signals_found,
        'confidence': confidence,
    }


def detect_paywall(html: str, url: str) -> Dict:
    """
    Detect if content is behind a paywall.

    Args:
        html: Raw HTML content
        url: URL of the content

    Returns:
        Dict with:
        - is_paywalled: bool
        - paywall_type: "hard" | "soft" | "metered" | None
        - confidence: float (0.0-1.0)
        - signals_found: List of detection signals
        - partial_content: str (first 500 chars if paywalled)
        - known_domain: bool (whether domain is known to be paywalled)
    """
    result = {
        'is_paywalled': False,
        'paywall_type': None,
        'confidence': 0.0,
        'signals_found': [],
        'partial_content': '',
        'known_domain': False,
    }

    # Check if known paywalled domain
    known_info = is_known_paywalled_domain(url)
    if known_info:
        result['known_domain'] = True
        result['paywall_type'] = known_info.get('type')
        result['confidence'] += 0.3  # Base confidence for known domains

    # Analyze HTML content
    html_detection = detect_paywall_in_html(html)
    result['signals_found'] = html_detection['signals_found']
    result['confidence'] = min(1.0, result['confidence'] + html_detection['confidence'])

    # Determine if paywalled based on confidence
    # Threshold: 0.5 for paywalled classification
    result['is_paywalled'] = result['confidence'] >= 0.5

    # If paywalled, try to extract partial content
    if result['is_paywalled'] and html:
        result['partial_content'] = extract_partial_content(html)

    return result


def extract_partial_content(html: str, max_chars: int = 500) -> str:
    """
    Extract partial content from potentially paywalled HTML.

    Tries to get the first paragraph(s) of the article that are
    usually visible before the paywall.

    Args:
        html: Raw HTML content
        max_chars: Maximum characters to extract

    Returns:
        Partial text content
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')

        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']):
            tag.decompose()

        # Try to find article content
        article = soup.find('article') or soup.find(class_=re.compile(r'article|content|story'))

        if article:
            # Get first few paragraphs
            paragraphs = article.find_all('p')[:3]
            text = ' '.join(p.get_text(strip=True) for p in paragraphs)
        else:
            # Fallback: get first few paragraphs from body
            paragraphs = soup.find_all('p')[:3]
            text = ' '.join(p.get_text(strip=True) for p in paragraphs)

        return text[:max_chars] if text else ''

    except Exception:
        return ''


def get_paywall_summary(result: Dict) -> str:
    """
    Get a human-readable summary of paywall detection.

    Args:
        result: Detection result from detect_paywall()

    Returns:
        Summary string
    """
    if not result['is_paywalled']:
        return "No paywall detected"

    paywall_type = result.get('paywall_type', 'unknown')
    confidence = result.get('confidence', 0)
    signals = len(result.get('signals_found', []))

    return f"Paywall detected ({paywall_type}, {confidence:.0%} confidence, {signals} signals)"


# CLI for testing
if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Testing paywall detection for: {url}")
        print()

        # Check known domain
        known = is_known_paywalled_domain(url)
        if known:
            print(f"Known paywalled domain: {known}")
        else:
            print("Not a known paywalled domain")
        print()

        # If we have HTML from stdin, analyze it
        if not sys.stdin.isatty():
            html = sys.stdin.read()
            result = detect_paywall(html, url)
            print("Detection result:")
            print(json.dumps(result, indent=2))
            print()
            print(get_paywall_summary(result))
    else:
        print("Usage: python paywall.py <url>")
        print("       cat page.html | python paywall.py <url>")
        print()
        print("Known paywalled domains:")
        for domain, info in sorted(KNOWN_PAYWALLED_DOMAINS.items()):
            print(f"  {domain}: {info}")
