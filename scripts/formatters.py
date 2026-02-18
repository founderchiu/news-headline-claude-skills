#!/usr/bin/env python3
"""
Output formatters for English News Skill.

Supports multiple output formats:
- JSON (default, machine-readable)
- Markdown (human-readable newsletter)
- Slack (Block Kit JSON for Slack messages)
"""

import json
from typing import List, Dict, Optional
from datetime import datetime


def format_json(stories: List[Dict], meta: Dict) -> str:
    """
    Format output as JSON.

    This is the default format, identical to the original output.
    """
    output = {
        'meta': meta,
        'stories': stories
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def format_markdown(stories: List[Dict], meta: Dict, language_mode: str = "bilingual") -> str:
    """
    Format output as Markdown newsletter.

    Args:
        stories: List of story dicts
        meta: Metadata dict
        language_mode: "bilingual", "english", or "chinese"

    Returns:
        Markdown formatted string
    """
    lines = []

    # Header
    lines.append("# 📰 News Briefing")
    lines.append("")

    # Metadata summary
    lines.append("---")
    lines.append(f"📊 **Scan Summary**: {meta.get('sources_scanned', 'N/A')} sources • "
                f"{meta.get('raw_items', 'N/A')} items fetched • "
                f"{meta.get('after_dedup', 'N/A')} unique stories "
                f"({meta.get('duplicates_merged', 0)} merged)")

    # Find top story
    if stories:
        top_story = stories[0]
        source_count = top_story.get('source_count', 1)
        if source_count > 1:
            lines.append(f"🔝 **Top Signal**: \"{top_story.get('title', '')}\" "
                        f"covered by {source_count} sources")

    lines.append("---")
    lines.append("")

    # Categorize stories
    multi_source = [s for s in stories if s.get('source_count', 1) >= 3]
    dual_source = [s for s in stories if s.get('source_count', 1) == 2]
    single_source = [s for s in stories if s.get('source_count', 1) == 1]

    # Top Stories (multi-source)
    if multi_source:
        lines.append("## 🔥 Top Stories (Multi-Source Coverage)")
        lines.append("")
        for i, story in enumerate(multi_source[:5], 1):
            lines.extend(_format_story_md(story, i, multi_source=True))
        lines.append("")

    # Trending (dual source)
    if dual_source:
        lines.append("## 📈 Trending")
        lines.append("")
        for i, story in enumerate(dual_source[:5], 1):
            lines.extend(_format_story_md(story, i, multi_source=True))
        lines.append("")

    # Latest News (single source, grouped by category)
    if single_source:
        # Group by source type
        tech_stories = [s for s in single_source if _is_tech_source(s)]
        global_stories = [s for s in single_source if _is_global_source(s)]
        finance_stories = [s for s in single_source if _is_finance_source(s)]

        if tech_stories:
            lines.append("## 🤖 Tech & AI")
            lines.append("")
            for i, story in enumerate(tech_stories[:5], 1):
                lines.extend(_format_story_md(story, i, multi_source=False))
            lines.append("")

        if global_stories:
            lines.append("## 🌍 Global Headlines")
            lines.append("")
            for i, story in enumerate(global_stories[:5], 1):
                lines.extend(_format_story_md(story, i, multi_source=False))
            lines.append("")

        if finance_stories:
            lines.append("## 💰 Markets & Finance")
            lines.append("")
            for i, story in enumerate(finance_stories[:5], 1):
                lines.extend(_format_story_md(story, i, multi_source=False))
            lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated at {meta.get('fetched_at', datetime.utcnow().isoformat())}*")

    return "\n".join(lines)


def _format_story_md(story: Dict, index: int, multi_source: bool = False) -> List[str]:
    """Format a single story as Markdown."""
    lines = []

    title = story.get('title', 'Untitled')
    url = story.get('url', '#')

    lines.append(f"### {index}. [{title}]({url})")

    if multi_source:
        sources = story.get('sources', [])
        heat_dict = story.get('heat', {})

        # Format sources with heat
        source_parts = []
        for source in sources:
            source_key = source.lower().replace(' ', '_').replace('/', '_')
            heat = heat_dict.get(source_key, '')
            if heat:
                source_parts.append(f"{source} ({heat})")
            else:
                source_parts.append(source)

        sources_str = " • ".join(source_parts)
        lines.append(f"**🔥 Covered by {len(sources)} sources**: {sources_str}")
    else:
        source = story.get('sources', ['Unknown'])[0] if 'sources' in story else story.get('source', 'Unknown')
        time_str = story.get('time', '')
        heat = list(story.get('heat', {}).values())[0] if story.get('heat') else ''

        meta_parts = [f"**Source**: {source}"]
        if time_str:
            meta_parts.append(f"**Time**: {time_str}")
        if heat:
            meta_parts.append(f"**Heat**: {heat}")

        lines.append(" | ".join(meta_parts))

    lines.append("")
    return lines


def _is_tech_source(story: Dict) -> bool:
    """Check if story is from a tech source."""
    tech_sources = ['hacker news', 'github', 'techcrunch', 'ars technica', 'the verge',
                   'reddit r/technology', 'reddit r/programming', 'product hunt']
    sources = story.get('sources', [story.get('source', '')])
    return any(s.lower() in tech_sources for s in sources)


def _is_global_source(story: Dict) -> bool:
    """Check if story is from a global news source."""
    global_sources = ['bbc', 'reuters', 'ap news']
    sources = story.get('sources', [story.get('source', '')])
    return any(any(g in s.lower() for g in global_sources) for s in sources)


def _is_finance_source(story: Dict) -> bool:
    """Check if story is from a finance source."""
    finance_sources = ['bloomberg', 'yahoo finance', 'cnbc', 'reddit stocks']
    sources = story.get('sources', [story.get('source', '')])
    return any(any(f in s.lower() for f in finance_sources) for s in sources)


def format_slack(stories: List[Dict], meta: Dict) -> str:
    """
    Format output as Slack Block Kit JSON.

    Returns JSON string ready to be sent to Slack's API.
    """
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "📰 News Briefing",
            "emoji": True
        }
    })

    # Metadata context
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"*{meta.get('after_dedup', 'N/A')}* stories from "
                       f"*{meta.get('sources_scanned', 'N/A')}* sources | "
                       f"{meta.get('fetched_at', 'Unknown time')}"
            }
        ]
    })

    blocks.append({"type": "divider"})

    # Top stories (limit to 10 for Slack message size limits)
    for story in stories[:10]:
        blocks.append(_format_story_slack_block(story))

    # More stories indicator
    if len(stories) > 10:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_...and {len(stories) - 10} more stories_"
                }
            ]
        })

    return json.dumps({"blocks": blocks}, indent=2, ensure_ascii=False)


def _format_story_slack_block(story: Dict) -> Dict:
    """Format a single story as a Slack block."""
    title = story.get('title', 'Untitled')
    url = story.get('url', '#')
    source_count = story.get('source_count', 1)
    sources = story.get('sources', [story.get('source', 'Unknown')])

    # Build the text
    if source_count > 1:
        sources_str = ", ".join(sources[:3])
        if len(sources) > 3:
            sources_str += f" +{len(sources) - 3}"
        text = f"*<{url}|{title}>*\n🔥 {source_count} sources: {sources_str}"
    else:
        source = sources[0] if sources else 'Unknown'
        time_str = story.get('time', '')
        text = f"*<{url}|{title}>*\n{source}"
        if time_str:
            text += f" • {time_str}"

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text
        }
    }


def format_output(stories: List[Dict], meta: Dict, format_type: str = "json",
                 language_mode: str = "bilingual") -> str:
    """
    Format output in the specified format.

    Args:
        stories: List of story dicts
        meta: Metadata dict
        format_type: "json", "md", "markdown", or "slack"
        language_mode: "bilingual", "english", or "chinese"

    Returns:
        Formatted string
    """
    format_type = format_type.lower()

    if format_type == "json":
        return format_json(stories, meta)
    elif format_type in ("md", "markdown"):
        return format_markdown(stories, meta, language_mode)
    elif format_type == "slack":
        return format_slack(stories, meta)
    else:
        # Default to JSON for unknown formats
        return format_json(stories, meta)


# CLI for testing
if __name__ == '__main__':
    import sys

    # Sample data for testing
    sample_stories = [
        {
            "title": "DOOM Ported to an Earbud",
            "url": "https://doombuds.com",
            "sources": ["Hacker News", "Reddit r/technology", "The Verge", "BBC News"],
            "source_count": 4,
            "heat": {
                "hacker_news": "529 points",
                "reddit_r_technology": "5.2K upvotes",
                "the_verge": "",
                "bbc_news": ""
            },
            "time": "2 hours ago",
        },
        {
            "title": "OpenAI Announces GPT-5",
            "url": "https://techcrunch.com/gpt5",
            "sources": ["TechCrunch", "Hacker News"],
            "source_count": 2,
            "heat": {
                "techcrunch": "",
                "hacker_news": "1205 points"
            },
            "time": "3 hours ago",
        },
        {
            "title": "Fed Holds Interest Rates Steady",
            "url": "https://reuters.com/fed",
            "sources": ["Reuters"],
            "source_count": 1,
            "heat": {"reuters": ""},
            "time": "1 hour ago",
        },
    ]

    sample_meta = {
        "raw_items": 150,
        "after_dedup": 89,
        "duplicates_merged": 61,
        "sources_scanned": 14,
        "fetched_at": "2026-01-25T10:30:00Z"
    }

    if len(sys.argv) > 1:
        format_type = sys.argv[1]
        print(format_output(sample_stories, sample_meta, format_type))
    else:
        print("Usage: python formatters.py <json|md|slack>")
        print()
        print("Example outputs:")
        print()
        print("=== JSON ===")
        print(format_output(sample_stories[:1], sample_meta, "json"))
        print()
        print("=== MARKDOWN ===")
        print(format_output(sample_stories, sample_meta, "md"))
