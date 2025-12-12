"""Tests for progress_tracker.py - Session continuity tracking."""

import pytest
from pathlib import Path
from datetime import datetime

from claude_harness.progress_tracker import (
    SessionProgress,
    ProgressTracker,
    get_progress_tracker,
)


class TestSessionProgress:
    """Tests for SessionProgress dataclass."""

    def test_session_progress_defaults(self):
        """Test default values."""
        progress = SessionProgress()
        assert progress.session_date != ""
        assert progress.completed == []
        assert progress.in_progress == []
        assert progress.blockers == []
        assert progress.next_steps == []
        assert progress.context_notes == []
        assert progress.files_modified == []

    def test_session_progress_with_data(self):
        """Test creation with data."""
        progress = SessionProgress(
            session_date="2025-01-15 10:00",
            completed=["Task 1", "Task 2"],
            in_progress=["Task 3"],
            blockers=["Waiting for API"],
            files_modified=["src/main.py"],
        )
        assert progress.session_date == "2025-01-15 10:00"
        assert len(progress.completed) == 2
        assert len(progress.in_progress) == 1


class TestProgressTracker:
    """Tests for ProgressTracker class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with harness directory."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def tracker(self, temp_project):
        """Create a ProgressTracker instance."""
        return ProgressTracker(str(temp_project))

    def test_init_creates_progress_file(self, tracker, temp_project):
        """Test that initialization creates progress.md."""
        progress_file = temp_project / ".claude-harness" / "progress.md"
        # Access tracker to trigger file creation
        tracker.get_current_progress()
        assert progress_file.exists()

    def test_initial_progress_content(self, tracker, temp_project):
        """Test initial progress.md content."""
        tracker.get_current_progress()
        progress_file = temp_project / ".claude-harness" / "progress.md"
        content = progress_file.read_text()

        assert "# Session Progress Log" in content
        assert "### Completed This Session" in content
        assert "### Current Work In Progress" in content
        assert "### Blockers" in content
        assert "### Next Session Should" in content
        assert "### Files Modified This Session" in content

    def test_get_current_progress(self, tracker):
        """Test getting current progress."""
        progress = tracker.get_current_progress()
        assert isinstance(progress, SessionProgress)

    def test_add_completed(self, tracker):
        """Test adding a completed item."""
        tracker.add_completed("Implemented login form")
        progress = tracker.get_current_progress()
        assert "Implemented login form" in progress.completed

    def test_add_in_progress(self, tracker):
        """Test adding an in-progress item."""
        tracker.add_in_progress("Working on JWT auth")
        progress = tracker.get_current_progress()
        assert "Working on JWT auth" in progress.in_progress

    def test_add_blocker(self, tracker):
        """Test adding a blocker."""
        tracker.add_blocker("Need API credentials")
        progress = tracker.get_current_progress()
        assert "Need API credentials" in progress.blockers

    def test_add_file_modified(self, tracker):
        """Test adding a modified file."""
        tracker.add_file_modified("src/auth/login.py")
        progress = tracker.get_current_progress()
        assert "src/auth/login.py" in progress.files_modified

    def test_add_file_modified_no_duplicates(self, tracker):
        """Test that duplicate files are not added."""
        tracker.add_file_modified("src/main.py")
        tracker.add_file_modified("src/main.py")
        progress = tracker.get_current_progress()
        count = progress.files_modified.count("src/main.py")
        assert count == 1

    def test_mark_completed(self, tracker):
        """Test marking an in-progress item as completed."""
        tracker.add_in_progress("JWT handling")
        tracker.mark_completed("JWT handling")
        progress = tracker.get_current_progress()
        assert "JWT handling" in progress.completed
        # Should be removed from in_progress
        assert "JWT handling" not in progress.in_progress

    def test_update_progress_multiple_fields(self, tracker):
        """Test updating multiple progress fields at once."""
        tracker.update_progress(
            completed=["Task 1", "Task 2"],
            in_progress=["Task 3"],
            blockers=["Blocker 1"],
            next_steps=["Step 1", "Step 2"],
            archive_previous=False,
        )
        progress = tracker.get_current_progress()
        assert len(progress.completed) == 2
        assert len(progress.in_progress) == 1
        assert len(progress.blockers) == 1
        assert len(progress.next_steps) == 2

    def test_start_new_session(self, tracker, temp_project):
        """Test starting a new session."""
        # Add some progress
        tracker.add_completed("Old task")
        tracker.add_in_progress("Old WIP")

        # Start new session
        tracker.start_new_session()

        progress = tracker.get_current_progress()
        # New session may have default placeholder items that get filtered
        assert "Old task" not in progress.completed
        assert "Old WIP" not in progress.in_progress

    def test_session_archival(self, tracker, temp_project):
        """Test that old sessions are archived."""
        # Add some progress
        tracker.add_completed("Task 1")

        # Start new session (archives previous)
        tracker.start_new_session()

        # Check session-history directory
        history_dir = temp_project / ".claude-harness" / "session-history"
        assert history_dir.exists()
        archives = list(history_dir.glob("session_*.md"))
        assert len(archives) >= 1

    def test_persistence(self, temp_project):
        """Test that progress persists across tracker instances."""
        tracker1 = ProgressTracker(str(temp_project))
        tracker1.add_completed("Persistent task")

        tracker2 = ProgressTracker(str(temp_project))
        progress = tracker2.get_current_progress()
        assert "Persistent task" in progress.completed

    def test_parse_numbered_list(self, tracker, temp_project):
        """Test parsing numbered list items."""
        tracker.update_progress(
            next_steps=["First step", "Second step", "Third step"],
            archive_previous=False,
        )
        progress = tracker.get_current_progress()
        assert len(progress.next_steps) == 3
        assert "First step" in progress.next_steps

    def test_parse_checkbox_items(self, tracker, temp_project):
        """Test parsing checkbox items."""
        tracker.add_completed("Task with checkbox")
        progress = tracker.get_current_progress()
        # Should not include checkbox markers
        assert "Task with checkbox" in progress.completed
        assert "[x]" not in progress.completed[0]

    def test_context_notes(self, tracker):
        """Test adding context notes."""
        tracker.update_progress(
            context_notes=["Important context about the project"],
            archive_previous=False,
        )
        progress = tracker.get_current_progress()
        assert "Important context about the project" in progress.context_notes


class TestGetProgressTracker:
    """Tests for get_progress_tracker helper function."""

    def test_get_progress_tracker(self, tmp_path):
        """Test the convenience function."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        tracker = get_progress_tracker(str(tmp_path))
        assert isinstance(tracker, ProgressTracker)


class TestProgressTrackerEdgeCases:
    """Edge case tests for ProgressTracker."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with harness directory."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        return tmp_path

    def test_empty_sections(self, temp_project):
        """Test handling of empty sections."""
        tracker = ProgressTracker(str(temp_project))
        progress = tracker.get_current_progress()
        # Should handle empty sections gracefully
        assert progress.completed == [] or "No tasks completed" not in progress.completed

    def test_special_characters_in_items(self, temp_project):
        """Test handling of special characters."""
        tracker = ProgressTracker(str(temp_project))
        tracker.add_completed("Task with `code` and **bold**")
        progress = tracker.get_current_progress()
        assert "Task with `code` and **bold**" in progress.completed

    def test_long_item_text(self, temp_project):
        """Test handling of long item text."""
        tracker = ProgressTracker(str(temp_project))
        long_text = "A" * 500  # 500 character item
        tracker.add_completed(long_text)
        progress = tracker.get_current_progress()
        assert long_text in progress.completed

    def test_multiple_sessions(self, temp_project):
        """Test multiple session starts."""
        tracker = ProgressTracker(str(temp_project))

        # First session - add content to make it archivable
        tracker.add_completed("Session 1 task")
        tracker.start_new_session()

        # Second session
        tracker.add_completed("Session 2 task")
        tracker.start_new_session()

        # Third session
        tracker.add_completed("Session 3 task")

        # Check archives - at least 1 session should be archived
        # Note: First session with "(No previous session)" may not archive
        history_dir = temp_project / ".claude-harness" / "session-history"
        archives = list(history_dir.glob("session_*.md"))
        assert len(archives) >= 1
