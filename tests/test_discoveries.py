"""Tests for discoveries.py - Discovery tracking."""

import json
import pytest
from pathlib import Path

from claude_harness.discoveries import (
    Discovery,
    DiscoveryTracker,
    get_discovery_tracker,
)


class TestDiscovery:
    """Tests for Discovery dataclass."""

    def test_discovery_creation(self):
        """Test creating a discovery."""
        discovery = Discovery(
            id="D001",
            timestamp="2025-01-01T00:00:00Z",
            summary="Test discovery",
            context="While testing",
            details="More details",
            impact="Affects tests",
            tags=["test", "example"],
            related_feature="F001",
            source="manual",
        )
        assert discovery.id == "D001"
        assert discovery.summary == "Test discovery"
        assert len(discovery.tags) == 2

    def test_to_dict(self):
        """Test conversion to dictionary."""
        discovery = Discovery(
            id="D001",
            timestamp="2025-01-01T00:00:00Z",
            summary="Test",
        )
        data = discovery.to_dict()
        assert data["id"] == "D001"
        assert data["summary"] == "Test"
        assert "tags" in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "D002",
            "timestamp": "2025-01-01T00:00:00Z",
            "summary": "From dict",
            "tags": ["tag1"],
        }
        discovery = Discovery.from_dict(data)
        assert discovery.id == "D002"
        assert discovery.summary == "From dict"
        assert discovery.tags == ["tag1"]


class TestDiscoveryTracker:
    """Tests for DiscoveryTracker class."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a tracker with test project."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        return DiscoveryTracker(str(tmp_path))

    def test_add_discovery(self, tracker):
        """Test adding a discovery."""
        discovery = tracker.add_discovery(
            summary="Test discovery",
            context="While testing",
            tags=["test"],
        )
        assert discovery.id == "D001"
        assert discovery.summary == "Test discovery"
        assert discovery.source == "manual"

    def test_add_multiple_discoveries(self, tracker):
        """Test adding multiple discoveries generates unique IDs."""
        d1 = tracker.add_discovery(summary="First")
        d2 = tracker.add_discovery(summary="Second")
        d3 = tracker.add_discovery(summary="Third")

        assert d1.id == "D001"
        assert d2.id == "D002"
        assert d3.id == "D003"

    def test_get_discovery(self, tracker):
        """Test getting a discovery by ID."""
        tracker.add_discovery(summary="Test")
        discovery = tracker.get_discovery("D001")
        assert discovery is not None
        assert discovery.summary == "Test"

    def test_get_nonexistent_discovery(self, tracker):
        """Test getting a nonexistent discovery returns None."""
        discovery = tracker.get_discovery("D999")
        assert discovery is None

    def test_list_discoveries(self, tracker):
        """Test listing all discoveries."""
        tracker.add_discovery(summary="First", tags=["a"])
        tracker.add_discovery(summary="Second", tags=["b"])
        tracker.add_discovery(summary="Third", tags=["a", "b"])

        all_discoveries = tracker.list_discoveries()
        assert len(all_discoveries) == 3

    def test_list_discoveries_by_tag(self, tracker):
        """Test filtering discoveries by tag."""
        tracker.add_discovery(summary="First", tags=["a"])
        tracker.add_discovery(summary="Second", tags=["b"])
        tracker.add_discovery(summary="Third", tags=["a", "b"])

        tag_a = tracker.list_discoveries(tag="a")
        assert len(tag_a) == 2

        tag_b = tracker.list_discoveries(tag="b")
        assert len(tag_b) == 2

    def test_list_discoveries_by_feature(self, tracker):
        """Test filtering discoveries by feature."""
        tracker.add_discovery(summary="First", related_feature="F001")
        tracker.add_discovery(summary="Second", related_feature="F002")
        tracker.add_discovery(summary="Third", related_feature="F001")

        f001 = tracker.list_discoveries(feature="F001")
        assert len(f001) == 2

    def test_list_discoveries_with_limit(self, tracker):
        """Test limiting number of discoveries."""
        for i in range(10):
            tracker.add_discovery(summary=f"Discovery {i}")

        limited = tracker.list_discoveries(limit=5)
        assert len(limited) == 5

    def test_search_discoveries(self, tracker):
        """Test searching discoveries."""
        tracker.add_discovery(summary="Need API key for authentication")
        tracker.add_discovery(summary="Database requires migration")
        tracker.add_discovery(summary="API rate limiting needed")

        results = tracker.search_discoveries("API")
        assert len(results) == 2

        results = tracker.search_discoveries("database")
        assert len(results) == 1

    def test_search_case_insensitive(self, tracker):
        """Test that search is case-insensitive."""
        tracker.add_discovery(summary="API Authentication Required")

        results = tracker.search_discoveries("api")
        assert len(results) == 1

        results = tracker.search_discoveries("API")
        assert len(results) == 1

    def test_update_discovery(self, tracker):
        """Test updating a discovery."""
        tracker.add_discovery(summary="Original")
        updated = tracker.update_discovery("D001", summary="Updated")

        assert updated is not None
        assert updated.summary == "Updated"

        # Verify persistence
        fetched = tracker.get_discovery("D001")
        assert fetched.summary == "Updated"

    def test_update_nonexistent_discovery(self, tracker):
        """Test updating a nonexistent discovery returns None."""
        result = tracker.update_discovery("D999", summary="Test")
        assert result is None

    def test_delete_discovery(self, tracker):
        """Test deleting a discovery."""
        tracker.add_discovery(summary="To delete")
        assert tracker.delete_discovery("D001") is True
        assert tracker.get_discovery("D001") is None

    def test_delete_nonexistent_discovery(self, tracker):
        """Test deleting a nonexistent discovery returns False."""
        result = tracker.delete_discovery("D999")
        assert result is False

    def test_get_tags(self, tracker):
        """Test getting all unique tags."""
        tracker.add_discovery(summary="First", tags=["a", "b"])
        tracker.add_discovery(summary="Second", tags=["b", "c"])
        tracker.add_discovery(summary="Third", tags=["a", "c", "d"])

        tags = tracker.get_tags()
        assert set(tags) == {"a", "b", "c", "d"}

    def test_get_stats(self, tracker):
        """Test getting discovery statistics."""
        tracker.add_discovery(summary="First", tags=["a"])
        tracker.add_discovery(summary="Second", tags=["a", "b"])

        stats = tracker.get_stats()
        assert stats["total"] == 2
        assert "manual" in stats["by_source"]
        assert "a" in stats["tags"]

    def test_persistence(self, tmp_path):
        """Test that discoveries persist across tracker instances."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        # First tracker adds discovery
        tracker1 = DiscoveryTracker(str(tmp_path))
        tracker1.add_discovery(summary="Persistent discovery")

        # New tracker should see it
        tracker2 = DiscoveryTracker(str(tmp_path))
        discoveries = tracker2.list_discoveries()
        assert len(discoveries) == 1
        assert discoveries[0].summary == "Persistent discovery"

    def test_generate_summary(self, tracker):
        """Test generating summary for context."""
        tracker.add_discovery(
            summary="Need API key",
            tags=["auth"],
            impact="All requests need auth header",
        )
        tracker.add_discovery(
            summary="Migration required",
            tags=["db"],
            impact="Run before tests",
        )

        summary = tracker.generate_summary_for_context()
        assert "Key Discoveries" in summary
        assert "Need API key" in summary
        assert "Migration required" in summary
        assert "[auth]" in summary

    def test_generate_empty_summary(self, tracker):
        """Test summary generation with no discoveries."""
        summary = tracker.generate_summary_for_context()
        assert summary == ""


class TestGetDiscoveryTracker:
    """Tests for get_discovery_tracker function."""

    def test_get_tracker(self, tmp_path):
        """Test getting a discovery tracker."""
        tracker = get_discovery_tracker(str(tmp_path))
        assert isinstance(tracker, DiscoveryTracker)
