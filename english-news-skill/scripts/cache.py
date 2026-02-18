#!/usr/bin/env python3
"""
On-disk cache for English News Skill using SQLite.

Provides:
- Configurable TTL (time-to-live) for cached items
- Last run storage for diff mode
- Automatic cache directory creation
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List


CACHE_DIR = Path.home() / ".cache" / "english-news-skill"
DEFAULT_TTL_MINUTES = 60


class NewsCache:
    """SQLite-based cache for news items with TTL support."""

    def __init__(self, ttl_minutes: int = DEFAULT_TTL_MINUTES):
        """
        Initialize the cache.

        Args:
            ttl_minutes: Default time-to-live for cached items in minutes
        """
        self.ttl_minutes = ttl_minutes
        self.db_path = CACHE_DIR / "cache.db"
        self._init_db()

    def _init_db(self):
        """Initialize the database and create tables if needed."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS last_run (
                    run_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON cache(expires_at)
            """)

            conn.commit()

    def _now(self) -> datetime:
        """Get current UTC datetime."""
        return datetime.now(timezone.utc)

    def _generate_key(self, source: str, keyword: Optional[str] = None) -> str:
        """
        Generate a cache key from source and keyword.

        Args:
            source: Source identifier (e.g., 'hackernews', 'all')
            keyword: Optional keyword filter

        Returns:
            Cache key string
        """
        key_parts = [source]
        if keyword:
            key_parts.append(hashlib.md5(keyword.encode()).hexdigest()[:8])

        # Include hour to ensure cache refreshes at least hourly
        key_parts.append(self._now().strftime('%Y%m%d%H'))

        return ':'.join(key_parts)

    def get(self, source: str, keyword: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieve cached data if not expired.

        Args:
            source: Source identifier
            keyword: Optional keyword filter

        Returns:
            Cached data dict or None if not found/expired
        """
        cache_key = self._generate_key(source, keyword)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data, expires_at FROM cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            data, expires_at = row
            expires = datetime.fromisoformat(expires_at)

            if self._now() > expires:
                # Expired, delete and return None
                conn.execute("DELETE FROM cache WHERE cache_key = ?", (cache_key,))
                conn.commit()
                return None

            return json.loads(data)

    def set(
        self,
        source: str,
        data: Dict,
        keyword: Optional[str] = None,
        ttl_override: Optional[int] = None
    ):
        """
        Store data in cache with TTL.

        Args:
            source: Source identifier
            data: Data to cache
            keyword: Optional keyword filter
            ttl_override: Optional TTL override in minutes
        """
        cache_key = self._generate_key(source, keyword)
        ttl = ttl_override if ttl_override is not None else self.ttl_minutes

        now = self._now()
        expires = now + timedelta(minutes=ttl)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (cache_key, data, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    cache_key,
                    json.dumps(data, ensure_ascii=False),
                    now.isoformat(),
                    expires.isoformat()
                )
            )
            conn.commit()

    def get_last_run(self, run_id: str = "default") -> Optional[Dict]:
        """
        Get the last run results for diff mode.

        Args:
            run_id: Identifier for the run type (e.g., "all", "tech")

        Returns:
            Last run data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM last_run WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()

            if row:
                return json.loads(row[0])
            return None

    def save_last_run(self, data: Dict, run_id: str = "default"):
        """
        Save current run results for future diff comparison.

        Args:
            data: Run results to save
            run_id: Identifier for the run type
        """
        now = self._now()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO last_run (run_id, data, created_at)
                VALUES (?, ?, ?)
                """,
                (run_id, json.dumps(data, ensure_ascii=False), now.isoformat())
            )
            conn.commit()

    def clear_expired(self):
        """Remove all expired cache entries."""
        now = self._now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (now,)
            )
            deleted = cursor.rowcount
            conn.commit()

        return deleted

    def clear_all(self):
        """Clear all cache data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.execute("DELETE FROM last_run")
            conn.commit()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cache_count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            run_count = conn.execute("SELECT COUNT(*) FROM last_run").fetchone()[0]

            # Count expired
            now = self._now().isoformat()
            expired_count = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at < ?",
                (now,)
            ).fetchone()[0]

        return {
            "cache_entries": cache_count,
            "expired_entries": expired_count,
            "valid_entries": cache_count - expired_count,
            "last_run_entries": run_count,
            "cache_dir": str(CACHE_DIR),
            "db_path": str(self.db_path),
        }


def compute_diff(current: List[Dict], previous: List[Dict]) -> Dict:
    """
    Compute the difference between current and previous run results.

    Args:
        current: Current run stories
        previous: Previous run stories

    Returns:
        Diff containing new_stories, dropped_stories, rank_changes
    """
    # Create URL-based lookup for comparison
    def get_url(item):
        return item.get('url', '') or item.get('title', '')

    current_urls = {get_url(item): (i, item) for i, item in enumerate(current)}
    previous_urls = {get_url(item): (i, item) for i, item in enumerate(previous)}

    # Find new stories (in current but not in previous)
    new_stories = []
    for url, (rank, item) in current_urls.items():
        if url not in previous_urls:
            new_stories.append({
                **item,
                "new_rank": rank + 1,
            })

    # Find dropped stories (in previous but not in current)
    dropped_stories = []
    for url, (rank, item) in previous_urls.items():
        if url not in current_urls:
            dropped_stories.append({
                "title": item.get('title', ''),
                "url": item.get('url', ''),
                "old_rank": rank + 1,
                "sources": item.get('sources', [item.get('source', '')]),
            })

    # Find rank changes (in both, but position changed)
    rank_changes = []
    for url, (new_rank, item) in current_urls.items():
        if url in previous_urls:
            old_rank, _ = previous_urls[url]
            if old_rank != new_rank:
                rank_changes.append({
                    "title": item.get('title', ''),
                    "url": item.get('url', ''),
                    "old_rank": old_rank + 1,
                    "new_rank": new_rank + 1,
                    "change": old_rank - new_rank,  # Positive = moved up
                })

    # Sort rank changes by magnitude of change
    rank_changes.sort(key=lambda x: abs(x['change']), reverse=True)

    return {
        "new_stories": new_stories,
        "dropped_stories": dropped_stories,
        "rank_changes": rank_changes[:10],  # Top 10 rank changes
        "summary": {
            "new_count": len(new_stories),
            "dropped_count": len(dropped_stories),
            "changed_count": len(rank_changes),
        }
    }


# CLI for testing
if __name__ == '__main__':
    import sys

    cache = NewsCache(ttl_minutes=60)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "stats":
            print(json.dumps(cache.stats(), indent=2))

        elif cmd == "clear":
            cache.clear_all()
            print("Cache cleared")

        elif cmd == "clear-expired":
            deleted = cache.clear_expired()
            print(f"Deleted {deleted} expired entries")

        elif cmd == "test":
            # Test cache operations
            print("Testing cache operations...")

            # Test set/get
            test_data = {"stories": [{"title": "Test Story"}]}
            cache.set("test_source", test_data)
            retrieved = cache.get("test_source")
            assert retrieved == test_data, "Cache set/get failed"
            print("✓ Set/get works")

            # Test last run
            cache.save_last_run(test_data, "test_run")
            last_run = cache.get_last_run("test_run")
            assert last_run == test_data, "Last run save/get failed"
            print("✓ Last run works")

            # Test diff
            current = [
                {"title": "Story A", "url": "http://a.com"},
                {"title": "Story B", "url": "http://b.com"},
                {"title": "Story C", "url": "http://c.com"},
            ]
            previous = [
                {"title": "Story B", "url": "http://b.com"},
                {"title": "Story D", "url": "http://d.com"},
            ]
            diff = compute_diff(current, previous)
            assert len(diff["new_stories"]) == 2, "Diff new stories count wrong"
            assert len(diff["dropped_stories"]) == 1, "Diff dropped stories count wrong"
            print("✓ Diff computation works")

            print("\nAll tests passed!")

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python cache.py [stats|clear|clear-expired|test]")

    else:
        print("Cache stats:")
        print(json.dumps(cache.stats(), indent=2))
