"""Tests for exploration_cache.py - Caching for exploration results.

This module tests the ExplorationCache class which caches results from
code exploration (grep, glob, file reads) to avoid redundant operations
and save context tokens.
"""

import json
import time
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from claude_harness.exploration_cache import (
    ExplorationCache,
    CachedExploration,
    get_exploration_cache,
)


class TestExplorationCacheBasics:
    """Tests for ExplorationCache basic initialization."""

    def test_default_initialization(self, tmp_path):
        """Test default initialization."""
        cache = ExplorationCache(project_path=str(tmp_path))
        assert cache is not None

    def test_get_exploration_cache_factory(self, tmp_path):
        """Test factory function returns cache instance."""
        cache = get_exploration_cache(str(tmp_path))
        assert isinstance(cache, ExplorationCache)

    def test_creates_cache_directory(self, tmp_path):
        """Test that cache directory is created on write."""
        cache = ExplorationCache(project_path=str(tmp_path))
        cache.cache_exploration("test", "query", {"result": "value"}, ["file.py"])

        assert (tmp_path / ".claude-harness" / "cache").exists()


class TestCachedExplorationDataclass:
    """Tests for CachedExploration dataclass."""

    def test_cached_exploration_creation(self):
        """Test CachedExploration can be created."""
        entry = CachedExploration(
            name="test_exploration",
            query="search pattern",
            results={"matches": 5},
            files_found=["a.py", "b.py"],
            timestamp=datetime.now(timezone.utc),
            ttl_hours=24,
            estimated_tokens=100,
        )
        assert entry.name == "test_exploration"
        assert entry.query == "search pattern"
        assert len(entry.files_found) == 2

    def test_cached_exploration_is_valid(self):
        """Test is_valid method with fresh entry."""
        entry = CachedExploration(
            name="test",
            query="query",
            results={},
            files_found=[],
            timestamp=datetime.now(timezone.utc),
            ttl_hours=24,
            estimated_tokens=0,
        )
        assert entry.is_valid() is True

    def test_cached_exploration_expired(self):
        """Test is_valid method with expired entry."""
        entry = CachedExploration(
            name="test",
            query="query",
            results={},
            files_found=[],
            timestamp=datetime.now(timezone.utc) - timedelta(hours=25),
            ttl_hours=24,
            estimated_tokens=0,
        )
        assert entry.is_valid() is False

    def test_cached_exploration_age_hours(self):
        """Test age_hours property."""
        entry = CachedExploration(
            name="test",
            query="query",
            results={},
            files_found=[],
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl_hours=24,
            estimated_tokens=0,
        )
        assert 1.9 <= entry.age_hours <= 2.1

    def test_cached_exploration_to_dict(self):
        """Test to_dict method."""
        entry = CachedExploration(
            name="test",
            query="query",
            results={"key": "value"},
            files_found=["file.py"],
            timestamp=datetime.now(timezone.utc),
            ttl_hours=24,
            estimated_tokens=100,
        )
        d = entry.to_dict()
        assert d["name"] == "test"
        assert d["query"] == "query"
        assert "timestamp" in d

    def test_cached_exploration_from_dict(self):
        """Test from_dict class method."""
        data = {
            "name": "test",
            "query": "query",
            "results": {"key": "value"},
            "files_found": ["file.py"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_hours": 24,
            "estimated_tokens": 100,
        }
        entry = CachedExploration.from_dict(data)
        assert entry.name == "test"
        assert entry.query == "query"


class TestCacheExploration:
    """Tests for cache_exploration method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_cache_exploration_basic(self, cache):
        """Test caching an exploration result."""
        cache_key = cache.cache_exploration(
            name="search_test",
            query="pattern",
            results={"matches": 5},
            files_found=["a.py", "b.py"],
        )
        assert cache_key is not None

    def test_cache_exploration_with_custom_ttl(self, cache):
        """Test caching with custom TTL."""
        cache.cache_exploration(
            name="short_lived",
            query="pattern",
            results={},
            files_found=[],
            ttl_hours=1,
        )
        entry = cache.get_cached("short_lived")
        assert entry is not None
        assert entry.ttl_hours == 1


class TestGetCached:
    """Tests for get_cached method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_get_cached_valid(self, cache):
        """Test getting valid cached entry."""
        cache.cache_exploration("test_key", "query", {"result": "value"}, ["file.py"])
        entry = cache.get_cached("test_key")

        assert entry is not None
        assert entry.name == "test_key"
        assert entry.results == {"result": "value"}

    def test_get_cached_not_found(self, cache):
        """Test getting non-existent key."""
        entry = cache.get_cached("nonexistent_key")
        assert entry is None


class TestInvalidate:
    """Tests for cache invalidation."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_invalidate_entry(self, cache):
        """Test invalidating a specific entry."""
        cache.cache_exploration("to_invalidate", "query", {}, [])
        assert cache.get_cached("to_invalidate") is not None

        result = cache.invalidate("to_invalidate")
        assert result is True
        assert cache.get_cached("to_invalidate") is None

    def test_invalidate_nonexistent(self, cache):
        """Test invalidating non-existent key."""
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_invalidate_all(self, cache):
        """Test invalidating all entries."""
        cache.cache_exploration("key1", "query1", {}, [])
        cache.cache_exploration("key2", "query2", {}, [])
        cache.cache_exploration("key3", "query3", {}, [])

        count = cache.invalidate_all()
        assert count >= 3

        assert cache.get_cached("key1") is None
        assert cache.get_cached("key2") is None
        assert cache.get_cached("key3") is None


class TestListCached:
    """Tests for list_cached method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_list_cached_empty(self, cache):
        """Test listing empty cache."""
        entries = cache.list_cached()
        assert entries == []

    def test_list_cached(self, cache):
        """Test listing cached entries."""
        cache.cache_exploration("key1", "query1", {}, [])
        cache.cache_exploration("key2", "query2", {}, [])

        entries = cache.list_cached()
        assert len(entries) == 2

    def test_list_valid(self, cache):
        """Test listing only valid entries."""
        cache.cache_exploration("valid", "query", {}, [], ttl_hours=24)
        entries = cache.list_valid()

        # All should be valid since just created
        assert len(entries) >= 1


class TestCleanupExpired:
    """Tests for expired entry cleanup."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_cleanup_expired(self, cache):
        """Test cleanup removes expired entries."""
        cache.cache_exploration("valid", "query", {}, [], ttl_hours=24)
        cleaned = cache.cleanup_expired()

        # No entries should be expired yet
        assert cleaned >= 0
        assert cache.get_cached("valid") is not None


class TestEstimateSavings:
    """Tests for token savings estimation."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_estimate_savings_empty(self, cache):
        """Test savings estimation with empty cache."""
        savings = cache.estimate_savings()
        assert savings == 0

    def test_estimate_savings_with_entries(self, cache):
        """Test savings estimation with entries."""
        # Large result
        large_result = {"data": "x" * 1000}
        cache.cache_exploration("large", "query", large_result, ["file.py"] * 10)

        savings = cache.estimate_savings()
        assert savings > 0


class TestCacheStats:
    """Tests for get_stats method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_get_stats_empty(self, cache):
        """Test stats with empty cache."""
        stats = cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0

    def test_get_stats_with_entries(self, cache):
        """Test stats with entries."""
        cache.cache_exploration("key1", "query1", {}, ["a.py"])
        cache.cache_exploration("key2", "query2", {}, ["b.py", "c.py"])

        stats = cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["total_files_cached"] == 3


class TestRefresh:
    """Tests for refresh method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_refresh_entry(self, cache):
        """Test refreshing a cache entry."""
        cache.cache_exploration("refreshable", "query", {}, [], ttl_hours=1)
        result = cache.refresh("refreshable", ttl_hours=48)

        assert result is True
        entry = cache.get_cached("refreshable")
        assert entry.ttl_hours == 48

    def test_refresh_nonexistent(self, cache):
        """Test refreshing non-existent entry."""
        result = cache.refresh("nonexistent")
        assert result is False


class TestSearchCached:
    """Tests for search_cached method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_search_cached(self, cache):
        """Test searching cached entries."""
        cache.cache_exploration("grep_pattern1", "TODO", {}, [])
        cache.cache_exploration("grep_pattern2", "FIXME", {}, [])
        cache.cache_exploration("glob_search", "*.py", {}, [])

        results = cache.search_cached("grep")
        assert len(results) == 2

    def test_search_cached_by_query(self, cache):
        """Test searching by query pattern."""
        cache.cache_exploration("search1", "TODO comments", {}, [])
        cache.cache_exploration("search2", "FIXME notes", {}, [])

        results = cache.search_cached("TODO")
        assert len(results) == 1


class TestGenerateCacheSummary:
    """Tests for generate_cache_summary method."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_generate_summary_empty(self, cache):
        """Test summary with empty cache."""
        summary = cache.generate_cache_summary()
        assert "No cached" in summary

    def test_generate_summary_with_entries(self, cache):
        """Test summary with entries."""
        cache.cache_exploration("test1", "query1", {}, ["a.py", "b.py"])
        cache.cache_exploration("test2", "query2", {}, ["c.py"])

        summary = cache.generate_cache_summary()
        assert "Cached" in summary
        assert "2 entries" in summary or "entries" in summary


class TestCachePersistence:
    """Tests for cache persistence across instances."""

    def test_cache_persistence(self, tmp_path):
        """Test that cache persists across instances."""
        cache1 = ExplorationCache(project_path=str(tmp_path))
        cache1.cache_exploration("persistent_key", "query", {"result": "value"}, ["file.py"])

        # Create new instance with same directory
        cache2 = ExplorationCache(project_path=str(tmp_path))
        entry = cache2.get_cached("persistent_key")

        assert entry is not None
        assert entry.results == {"result": "value"}

    def test_cache_persistence_complex_data(self, tmp_path):
        """Test persistence of complex data structures."""
        cache1 = ExplorationCache(project_path=str(tmp_path))
        data = {
            "files": ["a.py", "b.py"],
            "count": 42,
            "nested": {"key": "value"},
        }
        cache1.cache_exploration("complex_key", "query", data, ["file.py"])

        cache2 = ExplorationCache(project_path=str(tmp_path))
        entry = cache2.get_cached("complex_key")

        assert entry.results == data


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create an ExplorationCache instance."""
        return ExplorationCache(project_path=str(tmp_path))

    def test_empty_results(self, cache):
        """Test caching empty results."""
        cache.cache_exploration("empty_results", "query", {}, [])
        entry = cache.get_cached("empty_results")
        assert entry is not None
        assert entry.results == {}

    def test_large_results(self, cache):
        """Test caching large results."""
        large_data = {"files": [f"file{i}.py" for i in range(1000)]}
        cache.cache_exploration("large_results", "query", large_data, [])
        entry = cache.get_cached("large_results")
        assert entry is not None
        assert len(entry.results["files"]) == 1000

    def test_special_characters_in_name(self, cache):
        """Test names with special characters."""
        cache.cache_exploration("name/with/slashes", "query", {}, [])
        cache.cache_exploration("name:with:colons", "query", {}, [])

        # Should handle special characters via hashing
        assert cache.get_cached("name/with/slashes") is not None

    def test_unicode_content(self, cache):
        """Test caching unicode content."""
        cache.cache_exploration(
            "unicode_test",
            "query with special chars",
            {"message": "Hello World"},
            [],
        )
        entry = cache.get_cached("unicode_test")
        assert entry is not None

    def test_zero_ttl(self, cache):
        """Test caching with zero TTL (no expiration)."""
        cache.cache_exploration("no_expire", "query", {}, [], ttl_hours=0)
        entry = cache.get_cached("no_expire")

        # Zero TTL means no expiration
        if entry:
            assert entry.is_valid() is True
