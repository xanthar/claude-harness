"""Tests for context_tracker.py - Token/context usage tracking."""

import json
import pytest
from pathlib import Path

from claude_harness.context_tracker import (
    ContextMetrics,
    ContextTracker,
    get_context_tracker,
    CHARS_PER_TOKEN,
    CODE_CHARS_PER_TOKEN,
)


class TestContextMetrics:
    """Tests for ContextMetrics dataclass."""

    def test_context_metrics_defaults(self):
        """Test default values."""
        metrics = ContextMetrics()
        assert metrics.session_start != ""
        assert metrics.session_duration_minutes == 0.0
        assert metrics.files_read == []
        assert metrics.files_written == []
        assert metrics.commands_executed == 0
        assert metrics.context_budget == 200000
        assert metrics.context_warning_threshold == 0.7
        assert metrics.context_critical_threshold == 0.9

    def test_context_usage_percent(self):
        """Test context usage percentage calculation."""
        metrics = ContextMetrics(
            estimated_total_tokens=50000,
            context_budget=200000,
        )
        assert metrics.context_usage_percent == 25.0

    def test_context_usage_percent_zero_budget(self):
        """Test context usage with zero budget."""
        metrics = ContextMetrics(
            estimated_total_tokens=50000,
            context_budget=0,
        )
        assert metrics.context_usage_percent == 0.0

    def test_remaining_tokens(self):
        """Test remaining tokens calculation."""
        metrics = ContextMetrics(
            estimated_total_tokens=50000,
            context_budget=200000,
        )
        assert metrics.remaining_tokens == 150000

    def test_remaining_tokens_over_budget(self):
        """Test remaining tokens when over budget."""
        metrics = ContextMetrics(
            estimated_total_tokens=250000,
            context_budget=200000,
        )
        assert metrics.remaining_tokens == 0

    def test_status_ok(self):
        """Test status is 'ok' under warning threshold."""
        metrics = ContextMetrics(
            estimated_total_tokens=50000,  # 25%
            context_budget=200000,
        )
        assert metrics.status == "ok"

    def test_status_warning(self):
        """Test status is 'warning' at warning threshold."""
        metrics = ContextMetrics(
            estimated_total_tokens=150000,  # 75%
            context_budget=200000,
        )
        assert metrics.status == "warning"

    def test_status_critical(self):
        """Test status is 'critical' at critical threshold."""
        metrics = ContextMetrics(
            estimated_total_tokens=190000,  # 95%
            context_budget=200000,
        )
        assert metrics.status == "critical"

    def test_to_dict(self):
        """Test metrics serialization."""
        metrics = ContextMetrics(
            files_read=["file1.py", "file2.py"],
            estimated_total_tokens=10000,
        )
        data = metrics.to_dict()
        assert data["files_read"] == ["file1.py", "file2.py"]
        assert data["estimated_total_tokens"] == 10000
        assert "context_usage_percent" in data
        assert "remaining_tokens" in data
        assert "status" in data

    def test_from_dict(self):
        """Test metrics deserialization."""
        data = {
            "session_start": "2025-01-15T10:00:00",
            "files_read": ["test.py"],
            "files_read_chars": 1000,
            "estimated_total_tokens": 5000,
            "context_budget": 100000,
        }
        metrics = ContextMetrics.from_dict(data)
        assert metrics.session_start == "2025-01-15T10:00:00"
        assert metrics.files_read == ["test.py"]
        assert metrics.estimated_total_tokens == 5000


class TestContextTracker:
    """Tests for ContextTracker class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with harness directory and config."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        # Create minimal config
        config = {
            "project_name": "test-project",
            "context_tracking": {
                "enabled": True,
                "budget": 200000,
            },
        }
        config_file = harness_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        return tmp_path

    @pytest.fixture
    def tracker(self, temp_project):
        """Create a ContextTracker instance."""
        return ContextTracker(str(temp_project))

    def test_is_enabled_true(self, tracker):
        """Test is_enabled returns True when enabled."""
        assert tracker.is_enabled() is True

    def test_is_enabled_false(self, tmp_path):
        """Test is_enabled returns False when disabled."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        config = {"context_tracking": {"enabled": False}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        tracker = ContextTracker(str(tmp_path))
        assert tracker.is_enabled() is False

    def test_track_file_read(self, tracker):
        """Test tracking a file read."""
        tracker.track_file_read("src/main.py", 1000)
        metrics = tracker.get_metrics()

        assert "src/main.py" in metrics.files_read
        assert metrics.files_read_chars >= 1000
        assert metrics.estimated_input_tokens > 0
        assert metrics.tool_calls >= 1

    def test_track_file_read_no_duplicates(self, tracker):
        """Test that duplicate file paths are not added."""
        tracker.track_file_read("src/main.py", 1000)
        tracker.track_file_read("src/main.py", 500)
        metrics = tracker.get_metrics()

        count = metrics.files_read.count("src/main.py")
        assert count == 1
        # But chars should accumulate
        assert metrics.files_read_chars >= 1500

    def test_track_file_write(self, tracker):
        """Test tracking a file write."""
        tracker.track_file_write("src/output.py", 500)
        metrics = tracker.get_metrics()

        assert "src/output.py" in metrics.files_written
        assert metrics.files_written_chars >= 500
        assert metrics.estimated_output_tokens > 0

    def test_track_command(self, tracker):
        """Test tracking a command execution."""
        tracker.track_command("git status", output_length=200)
        metrics = tracker.get_metrics()

        assert metrics.commands_executed >= 1
        assert metrics.estimated_total_tokens > 0

    def test_track_conversation(self, tracker):
        """Test tracking a conversation turn."""
        tracker.track_conversation(user_message_length=100, assistant_response_length=500)
        metrics = tracker.get_metrics()

        assert metrics.estimated_input_tokens > 0
        assert metrics.estimated_output_tokens > 0

    def test_start_task(self, tracker):
        """Test starting task tracking."""
        tracker.start_task("F-001")
        metrics = tracker.get_metrics()

        assert metrics.current_task_id == "F-001"
        assert "F-001" in metrics.task_metrics

    def test_end_task(self, tracker):
        """Test ending task tracking."""
        tracker.start_task("F-001")
        tracker.end_task("F-001")
        metrics = tracker.get_metrics()

        assert metrics.current_task_id is None
        assert "ended_at" in metrics.task_metrics["F-001"]

    def test_reset_session(self, tracker):
        """Test resetting session metrics."""
        tracker.track_file_read("test.py", 1000)
        tracker.track_command("ls", 100)

        tracker.reset_session()
        metrics = tracker.get_metrics()

        assert metrics.files_read == []
        assert metrics.commands_executed == 0
        assert metrics.estimated_total_tokens == 0

    def test_per_task_tracking(self, tracker):
        """Test that file reads are tracked per task."""
        tracker.start_task("F-001")
        tracker.track_file_read("file1.py", 1000)
        tracker.track_file_read("file2.py", 500)

        metrics = tracker.get_metrics()
        task_data = metrics.task_metrics["F-001"]

        assert task_data["files_read"] >= 2
        assert task_data["tokens"] > 0

    def test_persistence(self, temp_project):
        """Test that metrics persist across tracker instances."""
        tracker1 = ContextTracker(str(temp_project))
        tracker1.track_file_read("persistent.py", 2000)

        tracker2 = ContextTracker(str(temp_project))
        metrics = tracker2.get_metrics()

        assert "persistent.py" in metrics.files_read

    def test_token_estimation_text(self, tracker):
        """Test token estimation for regular text."""
        # ~4 chars per token
        tracker.track_file_read("readme.md", 400)
        metrics = tracker.get_metrics()
        # Should be ~100 tokens
        assert metrics.estimated_input_tokens >= 80
        assert metrics.estimated_input_tokens <= 150

    def test_token_estimation_code(self, tracker):
        """Test token estimation for code files."""
        # Code uses ~3.5 chars per token
        tracker.track_file_read("main.py", 350)
        metrics = tracker.get_metrics()
        # Should be ~100 tokens
        assert metrics.estimated_input_tokens >= 80
        assert metrics.estimated_input_tokens <= 150


class TestContextTrackerSummary:
    """Tests for summary and handoff generation."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with full harness setup."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        # Create config
        config = {
            "project_name": "test-project",
            "stack": {"language": "python", "framework": "flask"},
            "context_tracking": {"enabled": True, "budget": 200000},
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        # Create features
        features = {
            "current_phase": "Phase 1",
            "features": [
                {
                    "id": "F-001",
                    "name": "Test Feature",
                    "status": "in_progress",
                    "subtasks": [
                        {"name": "Sub 1", "done": True},
                        {"name": "Sub 2", "done": False},
                    ],
                }
            ],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        # Create progress
        progress_content = """# Session Progress Log

## Last Session: 2025-01-15 10:00 UTC

### Completed This Session
- [x] Task 1
- [x] Task 2

### Current Work In Progress
- [ ] Task 3

### Blockers
- None

### Next Session Should
1. Continue work

### Context Notes
- Test context

### Files Modified This Session
- src/main.py
"""
        with open(harness_dir / "progress.md", "w") as f:
            f.write(progress_content)

        return tmp_path

    @pytest.fixture
    def tracker(self, temp_project):
        """Create a ContextTracker instance."""
        return ContextTracker(str(temp_project))

    def test_generate_summary(self, tracker):
        """Test generating a session summary."""
        tracker.track_file_read("test.py", 1000)
        summary = tracker.generate_summary()

        assert "# Session Summary" in summary
        assert "Context Usage" in summary
        assert "tokens" in summary.lower()

    def test_generate_summary_includes_feature(self, tracker):
        """Test that summary includes current feature."""
        summary = tracker.generate_summary()
        assert "F-001" in summary or "Test Feature" in summary

    def test_generate_handoff(self, tracker):
        """Test generating a handoff document."""
        handoff = tracker.generate_handoff()

        assert "# Session Handoff Document" in handoff
        assert "Continue work" in handoff
        assert "Recommended Actions" in handoff

    def test_save_handoff(self, tracker, temp_project):
        """Test saving handoff to file."""
        filepath = tracker.save_handoff()

        assert Path(filepath).exists()
        content = Path(filepath).read_text()
        assert "Session Handoff Document" in content

    def test_save_handoff_custom_filename(self, tracker, temp_project):
        """Test saving handoff with custom filename."""
        filepath = tracker.save_handoff("custom_handoff.md")

        assert "custom_handoff.md" in filepath
        assert Path(filepath).exists()

    def test_compress_session(self, tracker, temp_project):
        """Test full session compression."""
        tracker.track_file_read("test.py", 1000)
        results = tracker.compress_session()

        assert "handoff" in results
        assert results["progress_archived"] is True
        assert results["metrics_reset"] is True

        # Metrics should be reset
        metrics = tracker.get_metrics()
        assert metrics.estimated_total_tokens == 0


class TestGetContextTracker:
    """Tests for get_context_tracker helper function."""

    def test_get_context_tracker(self, tmp_path):
        """Test the convenience function."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        config = {"context_tracking": {"enabled": True}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        tracker = get_context_tracker(str(tmp_path))
        assert isinstance(tracker, ContextTracker)


class TestContextTrackerDisabled:
    """Tests for ContextTracker when disabled."""

    @pytest.fixture
    def disabled_tracker(self, tmp_path):
        """Create a tracker with context tracking disabled."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        config = {"context_tracking": {"enabled": False}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)
        return ContextTracker(str(tmp_path))

    def test_track_file_read_disabled(self, disabled_tracker):
        """Test that tracking is skipped when disabled."""
        disabled_tracker.track_file_read("test.py", 1000)
        # Should not raise, just skip

    def test_track_command_disabled(self, disabled_tracker):
        """Test that command tracking is skipped when disabled."""
        disabled_tracker.track_command("ls", 100)
        # Should not raise, just skip
