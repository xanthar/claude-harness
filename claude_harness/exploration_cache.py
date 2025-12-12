"""Exploration cache for Claude Harness.

Caches exploration results to avoid re-reading files and re-running searches:
- Persists cache to disk for cross-session use
- Automatic TTL-based expiration
- Estimates token savings from cache hits
- Supports cache invalidation
"""

import json
import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List


# Approximate characters per token for estimation
CHARS_PER_TOKEN = 4


@dataclass
class CachedExploration:
    """A cached exploration result."""

    name: str
    query: str
    results: Dict[str, Any]
    files_found: List[str]
    timestamp: datetime
    ttl_hours: int = 24
    estimated_tokens: int = 0

    def is_valid(self) -> bool:
        """Check if cache entry is still valid based on TTL.

        Returns:
            True if cache entry has not expired.
        """
        if self.ttl_hours <= 0:
            return True  # No expiration

        expiry = self.timestamp + timedelta(hours=self.ttl_hours)
        return datetime.now(timezone.utc) < expiry

    @property
    def age_hours(self) -> float:
        """Get age of cache entry in hours."""
        delta = datetime.now(timezone.utc) - self.timestamp
        return delta.total_seconds() / 3600

    @property
    def time_remaining_hours(self) -> float:
        """Get time remaining until expiration in hours."""
        if self.ttl_hours <= 0:
            return float("inf")
        expiry = self.timestamp + timedelta(hours=self.ttl_hours)
        delta = expiry - datetime.now(timezone.utc)
        return max(0, delta.total_seconds() / 3600)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "query": self.query,
            "results": self.results,
            "files_found": self.files_found,
            "timestamp": self.timestamp.isoformat(),
            "ttl_hours": self.ttl_hours,
            "estimated_tokens": self.estimated_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CachedExploration":
        """Create from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            CachedExploration instance.
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            name=data["name"],
            query=data.get("query", ""),
            results=data.get("results", {}),
            files_found=data.get("files_found", []),
            timestamp=timestamp,
            ttl_hours=data.get("ttl_hours", 24),
            estimated_tokens=data.get("estimated_tokens", 0),
        )


class ExplorationCache:
    """Cache exploration results across sessions.

    This cache persists to disk and helps avoid redundant file reads
    and searches by storing exploration results with configurable TTL.
    """

    CACHE_VERSION = "1.0"

    def __init__(self, project_path: str):
        """Initialize cache for a project.

        Args:
            project_path: Path to the project root.
        """
        self.project_path = Path(project_path).resolve()
        self.cache_dir = self.project_path / ".claude-harness" / "cache"
        self._cache_index: Optional[Dict[str, Any]] = None

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, name: str) -> str:
        """Generate a safe cache key from name.

        Args:
            name: The exploration name.

        Returns:
            Safe filename-compatible cache key.
        """
        # Create a hash to handle long or special character names
        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        # Keep a sanitized version of the name for readability
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:32]
        return f"{safe_name}_{name_hash}"

    def _get_cache_file(self, name: str) -> Path:
        """Get the cache file path for an exploration.

        Args:
            name: The exploration name.

        Returns:
            Path to the cache file.
        """
        return self.cache_dir / f"{self._get_cache_key(name)}.json"

    def _load_index(self) -> Dict[str, Any]:
        """Load or create the cache index.

        Returns:
            Cache index dictionary.
        """
        if self._cache_index is not None:
            return self._cache_index

        index_file = self.cache_dir / "index.json"

        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    self._cache_index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache_index = {
                    "version": self.CACHE_VERSION,
                    "entries": {},
                }
        else:
            self._cache_index = {
                "version": self.CACHE_VERSION,
                "entries": {},
            }

        return self._cache_index

    def _save_index(self) -> None:
        """Save the cache index to disk."""
        if self._cache_index is None:
            return

        self._ensure_cache_dir()
        index_file = self.cache_dir / "index.json"

        try:
            with open(index_file, "w") as f:
                json.dump(self._cache_index, f, indent=2)
        except IOError:
            pass  # Fail silently on write errors

    def _estimate_tokens(self, results: Dict[str, Any], files_found: List[str]) -> int:
        """Estimate tokens for cached content.

        Args:
            results: The results dictionary.
            files_found: List of files found.

        Returns:
            Estimated token count.
        """
        # Estimate from JSON size
        try:
            json_size = len(json.dumps(results))
        except (TypeError, ValueError):
            json_size = 0

        # Add estimate for file paths
        files_size = sum(len(fp) for fp in files_found)

        return int((json_size + files_size) / CHARS_PER_TOKEN)

    def cache_exploration(
        self,
        name: str,
        query: str,
        results: Dict[str, Any],
        files_found: List[str],
        ttl_hours: int = 24,
    ) -> str:
        """Cache an exploration result.

        Args:
            name: Unique name for this exploration.
            query: The query or search pattern used.
            results: Dictionary of exploration results.
            files_found: List of file paths found.
            ttl_hours: Time-to-live in hours (0 = no expiration).

        Returns:
            Cache key for this exploration.
        """
        self._ensure_cache_dir()

        estimated_tokens = self._estimate_tokens(results, files_found)

        entry = CachedExploration(
            name=name,
            query=query,
            results=results,
            files_found=files_found,
            timestamp=datetime.now(timezone.utc),
            ttl_hours=ttl_hours,
            estimated_tokens=estimated_tokens,
        )

        # Save to individual cache file
        cache_file = self._get_cache_file(name)
        try:
            with open(cache_file, "w") as f:
                json.dump(entry.to_dict(), f, indent=2)
        except IOError as e:
            raise IOError(f"Failed to write cache file: {e}") from e

        # Update index
        index = self._load_index()
        cache_key = self._get_cache_key(name)
        index["entries"][cache_key] = {
            "name": name,
            "query": query,
            "timestamp": entry.timestamp.isoformat(),
            "ttl_hours": ttl_hours,
            "estimated_tokens": estimated_tokens,
            "file_count": len(files_found),
        }
        self._save_index()

        return cache_key

    def get_cached(self, name: str) -> Optional[CachedExploration]:
        """Get a cached exploration by name.

        Args:
            name: The exploration name.

        Returns:
            CachedExploration if found and valid, None otherwise.
        """
        cache_file = self._get_cache_file(name)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            entry = CachedExploration.from_dict(data)

            # Check validity
            if not entry.is_valid():
                # Auto-clean expired entries
                self.invalidate(name)
                return None

            return entry
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def invalidate(self, name: str) -> bool:
        """Invalidate a cached exploration.

        Args:
            name: The exploration name to invalidate.

        Returns:
            True if entry was found and removed, False otherwise.
        """
        cache_file = self._get_cache_file(name)
        cache_key = self._get_cache_key(name)

        removed = False

        # Remove cache file
        if cache_file.exists():
            try:
                cache_file.unlink()
                removed = True
            except IOError:
                pass

        # Remove from index
        index = self._load_index()
        if cache_key in index["entries"]:
            del index["entries"][cache_key]
            self._save_index()
            removed = True

        return removed

    def invalidate_all(self) -> int:
        """Invalidate all cached explorations.

        Returns:
            Number of entries removed.
        """
        index = self._load_index()
        count = len(index["entries"])

        # Remove all cache files
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name != "index.json":
                    try:
                        cache_file.unlink()
                    except IOError:
                        pass

        # Clear index
        index["entries"] = {}
        self._save_index()

        return count

    def list_cached(self) -> List[CachedExploration]:
        """List all cached explorations.

        Returns:
            List of CachedExploration objects (including expired ones).
        """
        index = self._load_index()
        entries = []

        for cache_key, meta in index["entries"].items():
            # Try to load full entry
            name = meta.get("name", "")
            if not name:
                continue

            entry = self.get_cached(name)
            if entry:
                entries.append(entry)

        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def list_valid(self) -> List[CachedExploration]:
        """List only valid (non-expired) cached explorations.

        Returns:
            List of valid CachedExploration objects.
        """
        return [e for e in self.list_cached() if e.is_valid()]

    def estimate_savings(self) -> int:
        """Estimate total tokens saved by using cache.

        Returns:
            Estimated tokens saved from all valid cache entries.
        """
        return sum(e.estimated_tokens for e in self.list_valid())

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed.
        """
        index = self._load_index()
        removed = 0

        # Find expired entries
        expired_keys = []
        for cache_key, meta in index["entries"].items():
            timestamp_str = meta.get("timestamp")
            ttl_hours = meta.get("ttl_hours", 24)

            if timestamp_str and ttl_hours > 0:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    expiry = timestamp + timedelta(hours=ttl_hours)
                    if datetime.now(timezone.utc) >= expiry:
                        expired_keys.append((cache_key, meta.get("name", "")))
                except ValueError:
                    pass

        # Remove expired entries
        for cache_key, name in expired_keys:
            if name:
                self.invalidate(name)
                removed += 1

        return removed

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        index = self._load_index()
        all_entries = self.list_cached()
        valid_entries = [e for e in all_entries if e.is_valid()]
        expired_entries = [e for e in all_entries if not e.is_valid()]

        total_tokens = sum(e.estimated_tokens for e in valid_entries)
        total_files = sum(len(e.files_found) for e in valid_entries)

        return {
            "total_entries": len(index["entries"]),
            "valid_entries": len(valid_entries),
            "expired_entries": len(expired_entries),
            "estimated_tokens_saved": total_tokens,
            "total_files_cached": total_files,
            "cache_dir": str(self.cache_dir),
            "cache_version": self.CACHE_VERSION,
        }

    def refresh(self, name: str, ttl_hours: Optional[int] = None) -> bool:
        """Refresh a cache entry's timestamp (extend TTL).

        Args:
            name: The exploration name.
            ttl_hours: New TTL in hours (None = keep existing).

        Returns:
            True if entry was refreshed, False if not found.
        """
        entry = self.get_cached(name)
        if not entry:
            return False

        # Re-cache with new timestamp
        new_ttl = ttl_hours if ttl_hours is not None else entry.ttl_hours

        self.cache_exploration(
            name=entry.name,
            query=entry.query,
            results=entry.results,
            files_found=entry.files_found,
            ttl_hours=new_ttl,
        )

        return True

    def search_cached(self, query_pattern: str) -> List[CachedExploration]:
        """Search cached explorations by query pattern.

        Args:
            query_pattern: Substring to search for in exploration names/queries.

        Returns:
            List of matching CachedExploration objects.
        """
        pattern_lower = query_pattern.lower()
        matches = []

        for entry in self.list_valid():
            if (
                pattern_lower in entry.name.lower()
                or pattern_lower in entry.query.lower()
            ):
                matches.append(entry)

        return matches

    def generate_cache_summary(self) -> str:
        """Generate a summary of cached explorations for context.

        Returns:
            Formatted summary string.
        """
        stats = self.get_stats()
        valid_entries = self.list_valid()

        if not valid_entries:
            return "No cached explorations available."

        lines = [
            "---",
            "**Cached Explorations**",
            f"({stats['valid_entries']} entries, ~{stats['estimated_tokens_saved']:,} tokens)",
            "",
        ]

        for entry in valid_entries[:10]:  # Limit to 10 most recent
            age_str = f"{entry.age_hours:.1f}h ago"
            lines.append(
                f"- `{entry.name}`: {len(entry.files_found)} files, "
                f"~{entry.estimated_tokens:,} tokens ({age_str})"
            )

        if len(valid_entries) > 10:
            lines.append(f"- ... and {len(valid_entries) - 10} more")

        lines.append("")
        lines.append("*Use cached results to avoid re-reading files.*")
        lines.append("---")

        return "\n".join(lines)


def get_exploration_cache(project_path: str) -> ExplorationCache:
    """Get an exploration cache instance.

    Args:
        project_path: Path to the project root.

    Returns:
        ExplorationCache instance.
    """
    return ExplorationCache(project_path)
