#!/usr/bin/env python3
"""
Configuration loader for English News Skill.

Loads settings from config.yaml and provides defaults.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Default config path (relative to this file's parent directory)
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class SourceConfig:
    """Source configuration settings."""
    enabled: List[str] = field(default_factory=lambda: [
        'hackernews', 'github', 'producthunt', 'reddit_tech', 'reddit_programming',
        'techcrunch', 'arstechnica', 'theverge', 'bbc', 'reuters', 'apnews',
        'yahoo_finance', 'cnbc', 'reddit_stocks'
    ])
    per_source_limits: Dict[str, int] = field(default_factory=lambda: {
        'hackernews': 15,
        'default': 10
    })

    def get_limit(self, source: str) -> int:
        """Get the limit for a specific source."""
        return self.per_source_limits.get(source, self.per_source_limits.get('default', 10))


@dataclass
class DedupConfig:
    """Deduplication configuration settings."""
    title_threshold: float = 0.70
    resolve_canonical_urls: bool = False
    preserve_alternates: bool = True


@dataclass
class DeepConfig:
    """Deep fetching configuration settings."""
    timeout_seconds: int = 10
    max_retries: int = 2
    max_workers: int = 10
    cache_ttl_minutes: int = 60


@dataclass
class OutputConfig:
    """Output configuration settings."""
    language_mode: str = "bilingual"  # bilingual, english, chinese
    default_format: str = "json"  # json, markdown, slack


@dataclass
class Config:
    """Main configuration container."""
    version: int = 1
    sources: SourceConfig = field(default_factory=SourceConfig)
    dedup: DedupConfig = field(default_factory=DedupConfig)
    deep: DeepConfig = field(default_factory=DeepConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    keyword_presets: Dict[str, List[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """
        Load configuration from YAML file.

        Args:
            path: Path to config file (defaults to config.yaml in parent dir)

        Returns:
            Config instance
        """
        config_path = path or CONFIG_PATH

        if not config_path.exists():
            return cls.defaults()

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            return cls._from_dict(data)
        except Exception as e:
            import sys
            print(f"Warning: Failed to load config from {config_path}: {e}", file=sys.stderr)
            return cls.defaults()

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create Config from dictionary."""
        sources_data = data.get('sources', {})
        dedup_data = data.get('dedup', {})
        deep_data = data.get('deep', {})
        output_data = data.get('output', {})

        return cls(
            version=data.get('version', 1),
            sources=SourceConfig(
                enabled=sources_data.get('enabled', SourceConfig().enabled),
                per_source_limits=sources_data.get('per_source_limits', {}),
            ),
            dedup=DedupConfig(
                title_threshold=dedup_data.get('title_threshold', 0.70),
                resolve_canonical_urls=dedup_data.get('resolve_canonical_urls', False),
                preserve_alternates=dedup_data.get('preserve_alternates', True),
            ),
            deep=DeepConfig(
                timeout_seconds=deep_data.get('timeout_seconds', 10),
                max_retries=deep_data.get('max_retries', 2),
                max_workers=deep_data.get('max_workers', 10),
                cache_ttl_minutes=deep_data.get('cache_ttl_minutes', 60),
            ),
            output=OutputConfig(
                language_mode=output_data.get('language_mode', 'bilingual'),
                default_format=output_data.get('default_format', 'json'),
            ),
            keyword_presets=data.get('keyword_presets', {}),
        )

    @classmethod
    def defaults(cls) -> "Config":
        """Return default configuration."""
        return cls()

    def get_keywords(self, preset_name: str) -> List[str]:
        """
        Get keywords for a preset.

        Args:
            preset_name: Name of the preset (e.g., 'ai', 'crypto')

        Returns:
            List of keywords or empty list if preset not found
        """
        return self.keyword_presets.get(preset_name.lower(), [])

    def expand_keywords(self, keyword_arg: str) -> str:
        """
        Expand keyword argument, replacing preset names with their keywords.

        Args:
            keyword_arg: Comma-separated keywords or preset names

        Returns:
            Comma-separated expanded keywords
        """
        if not keyword_arg:
            return keyword_arg

        expanded = []
        for kw in keyword_arg.split(','):
            kw = kw.strip()
            preset_keywords = self.get_keywords(kw)
            if preset_keywords:
                expanded.extend(preset_keywords)
            else:
                expanded.append(kw)

        return ','.join(expanded)

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            'version': self.version,
            'sources': {
                'enabled': self.sources.enabled,
                'per_source_limits': self.sources.per_source_limits,
            },
            'dedup': {
                'title_threshold': self.dedup.title_threshold,
                'resolve_canonical_urls': self.dedup.resolve_canonical_urls,
                'preserve_alternates': self.dedup.preserve_alternates,
            },
            'deep': {
                'timeout_seconds': self.deep.timeout_seconds,
                'max_retries': self.deep.max_retries,
                'max_workers': self.deep.max_workers,
                'cache_ttl_minutes': self.deep.cache_ttl_minutes,
            },
            'output': {
                'language_mode': self.output.language_mode,
                'default_format': self.output.default_format,
            },
            'keyword_presets': self.keyword_presets,
        }


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load()
    return _config


# CLI for testing
if __name__ == '__main__':
    import json
    import sys

    config = get_config()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == 'show':
            print(json.dumps(config.to_dict(), indent=2))

        elif cmd == 'keywords':
            if len(sys.argv) > 2:
                preset = sys.argv[2]
                keywords = config.get_keywords(preset)
                if keywords:
                    print(f"Keywords for '{preset}':")
                    print(','.join(keywords))
                else:
                    print(f"No preset found: {preset}")
            else:
                print("Available presets:")
                for name, keywords in config.keyword_presets.items():
                    print(f"  {name}: {len(keywords)} keywords")

        elif cmd == 'expand':
            if len(sys.argv) > 2:
                kw = sys.argv[2]
                expanded = config.expand_keywords(kw)
                print(f"Expanded: {expanded}")
            else:
                print("Usage: python config.py expand <keywords>")

        else:
            print(f"Unknown command: {cmd}")
            print("Commands: show, keywords [preset], expand <keywords>")
    else:
        print("Config loaded successfully!")
        print(f"  Enabled sources: {len(config.sources.enabled)}")
        print(f"  Keyword presets: {len(config.keyword_presets)}")
        print(f"  Default format: {config.output.default_format}")
        print()
        print("Commands: show, keywords [preset], expand <keywords>")
