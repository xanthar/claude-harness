"""Tests for cli.py - CLI interface."""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner

from claude_harness.cli import main


class TestCLIBasics:
    """Basic CLI tests."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "claude-harness" in result.output

    def test_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Claude Harness" in result.output
        assert "init" in result.output
        assert "status" in result.output
        assert "feature" in result.output


class TestStatusCommand:
    """Tests for status command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def initialized_project(self, tmp_path):
        """Create a project with harness initialized."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        # Create config
        config = {
            "project_name": "test-project",
            "context_tracking": {"enabled": True, "budget": 200000},
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        # Create features
        features = {"current_phase": "Phase 1", "features": [], "completed": [], "blocked": []}
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        # Create progress
        progress = """# Session Progress Log

## Last Session: (No previous session)

### Completed This Session
- [ ] No tasks completed yet

### Current Work In Progress
- [ ] No tasks in progress

### Blockers
- None

### Next Session Should
1. Run init.sh

### Context Notes
- Initialized

### Files Modified This Session
- (none)
"""
        with open(harness_dir / "progress.md", "w") as f:
            f.write(progress)

        return tmp_path

    def test_status_not_initialized(self, runner, tmp_path):
        """Test status command when harness not initialized."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 1
            assert "not initialized" in result.output.lower()

    def test_status_initialized(self, runner, initialized_project):
        """Test status command when harness is initialized."""
        with runner.isolated_filesystem(temp_dir=initialized_project):
            import os
            os.chdir(initialized_project)
            result = runner.invoke(main, ["status"])
            # Should not error
            assert result.exit_code == 0 or "Error" not in result.output


class TestFeatureCommands:
    """Tests for feature commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def initialized_project(self, tmp_path):
        """Create a project with harness initialized."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"project_name": "test-project"}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        features = {"current_phase": "Phase 1", "features": [], "completed": [], "blocked": []}
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        progress = "# Session Progress Log\n\n## Last Session: (No previous session)\n"
        with open(harness_dir / "progress.md", "w") as f:
            f.write(progress)

        return tmp_path

    def test_feature_list_empty(self, runner, initialized_project):
        """Test feature list when empty."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["feature", "list"])
        assert result.exit_code == 0

    def test_feature_list_priority_filter(self, runner, initialized_project):
        """Test feature list with priority filter."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Low Priority", "-p", "5"])
        runner.invoke(main, ["feature", "add", "High Priority", "-p", "1"])
        runner.invoke(main, ["feature", "add", "Another High", "-p", "1"])

        result = runner.invoke(main, ["feature", "list", "--priority", "1"])
        assert result.exit_code == 0
        assert "High Priority" in result.output
        assert "Another High" in result.output
        assert "Low Priority" not in result.output
        assert "2 feature(s) found" in result.output

    def test_feature_list_search_filter(self, runner, initialized_project):
        """Test feature list with search filter."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "User Authentication"])
        runner.invoke(main, ["feature", "add", "Payment Processing"])
        runner.invoke(main, ["feature", "add", "Auth Token Refresh"])

        result = runner.invoke(main, ["feature", "list", "--search", "auth"])
        assert result.exit_code == 0
        assert "User Authentication" in result.output
        assert "Auth Token Refresh" in result.output
        assert "Payment Processing" not in result.output
        assert "2 feature(s) found" in result.output

    def test_feature_list_combined_filters(self, runner, initialized_project):
        """Test feature list with multiple filters combined."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Auth Login", "-p", "1"])
        runner.invoke(main, ["feature", "add", "Auth Logout", "-p", "2"])
        runner.invoke(main, ["feature", "add", "Payment", "-p", "1"])

        result = runner.invoke(main, ["feature", "list", "-p", "1", "-q", "auth"])
        assert result.exit_code == 0
        assert "Auth Login" in result.output
        assert "Auth Logout" not in result.output
        assert "Payment" not in result.output
        assert "1 feature(s) found" in result.output

    def test_feature_list_no_match(self, runner, initialized_project):
        """Test feature list when no features match filters."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Some Feature"])

        result = runner.invoke(main, ["feature", "list", "--search", "nonexistent"])
        assert result.exit_code == 0
        assert "No features match" in result.output

    def test_feature_add(self, runner, initialized_project):
        """Test adding a feature."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["feature", "add", "User Authentication"])
        assert result.exit_code == 0
        assert "F-001" in result.output or "Added" in result.output

    def test_feature_add_with_subtasks(self, runner, initialized_project):
        """Test adding a feature with subtasks."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(
            main,
            ["feature", "add", "Auth", "-s", "Login", "-s", "Logout"],
        )
        assert result.exit_code == 0

    def test_feature_start(self, runner, initialized_project):
        """Test starting a feature."""
        import os
        os.chdir(initialized_project)
        # Add feature first
        runner.invoke(main, ["feature", "add", "Test Feature"])
        # Start it
        result = runner.invoke(main, ["feature", "start", "F-001"])
        assert result.exit_code == 0
        assert "Started" in result.output or "F-001" in result.output

    def test_feature_complete(self, runner, initialized_project):
        """Test completing a feature."""
        import os
        os.chdir(initialized_project)
        # Add and start feature
        runner.invoke(main, ["feature", "add", "Test Feature"])
        runner.invoke(main, ["feature", "start", "F-001"])
        # Complete it
        result = runner.invoke(main, ["feature", "complete", "F-001"])
        assert result.exit_code == 0
        assert "Completed" in result.output or "F-001" in result.output

    def test_feature_not_found(self, runner, initialized_project):
        """Test feature commands with non-existent feature."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["feature", "start", "F-999"])
        assert "not found" in result.output.lower()

    def test_feature_info(self, runner, initialized_project):
        """Test feature info command."""
        import os
        os.chdir(initialized_project)
        # Add a feature with subtasks and notes
        runner.invoke(main, [
            "feature", "add", "Test Feature",
            "-s", "Subtask 1", "-s", "Subtask 2",
            "-n", "Some notes here"
        ])
        result = runner.invoke(main, ["feature", "info", "F-001"])
        assert result.exit_code == 0
        assert "F-001" in result.output
        assert "Test Feature" in result.output
        assert "Subtask 1" in result.output
        assert "Subtask 2" in result.output
        assert "Some notes here" in result.output

    def test_feature_info_not_found(self, runner, initialized_project):
        """Test feature info with non-existent feature."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["feature", "info", "F-999"])
        assert "not found" in result.output.lower()

    def test_feature_block(self, runner, initialized_project):
        """Test blocking a feature."""
        import os
        os.chdir(initialized_project)
        # Add feature first
        runner.invoke(main, ["feature", "add", "Test Feature"])
        # Block it
        result = runner.invoke(main, ["feature", "block", "F-001", "-r", "Waiting for API"])
        assert result.exit_code == 0
        assert "Blocked" in result.output or "F-001" in result.output

    def test_feature_unblock(self, runner, initialized_project):
        """Test unblocking a blocked feature."""
        import os
        os.chdir(initialized_project)
        # Add and block feature
        runner.invoke(main, ["feature", "add", "Test Feature"])
        runner.invoke(main, ["feature", "block", "F-001", "-r", "Waiting for API"])
        # Unblock it
        result = runner.invoke(main, ["feature", "unblock", "F-001"])
        assert result.exit_code == 0
        assert "Unblocked" in result.output

    def test_feature_unblock_not_blocked(self, runner, initialized_project):
        """Test unblock on a feature that isn't blocked."""
        import os
        os.chdir(initialized_project)
        # Add feature (not blocked)
        runner.invoke(main, ["feature", "add", "Test Feature"])
        # Try to unblock
        result = runner.invoke(main, ["feature", "unblock", "F-001"])
        assert result.exit_code == 0
        assert "not blocked" in result.output.lower()

    def test_feature_unblock_not_found(self, runner, initialized_project):
        """Test unblock on non-existent feature."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["feature", "unblock", "F-999"])
        assert "not found" in result.output.lower()

    def test_feature_done_by_index(self, runner, initialized_project):
        """Test marking subtask done by index."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test", "-s", "Task 1", "-s", "Task 2"])
        result = runner.invoke(main, ["feature", "done", "F-001", "0"])
        assert result.exit_code == 0
        assert "Completed" in result.output or "Task 1" in result.output

    def test_feature_done_by_name(self, runner, initialized_project):
        """Test marking subtask done by exact name."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test", "-s", "Login form", "-s", "Logout"])
        result = runner.invoke(main, ["feature", "done", "F-001", "Login form"])
        assert result.exit_code == 0
        assert "Login form" in result.output

    def test_feature_done_by_partial_name(self, runner, initialized_project):
        """Test marking subtask done by partial name match."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test", "-s", "Login form", "-s", "Logout"])
        result = runner.invoke(main, ["feature", "done", "F-001", "login"])
        assert result.exit_code == 0
        assert "Login form" in result.output

    def test_feature_done_multiple_matches(self, runner, initialized_project):
        """Test done command with ambiguous name match."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test", "-s", "Login API", "-s", "Login UI"])
        result = runner.invoke(main, ["feature", "done", "F-001", "login"])
        assert result.exit_code == 0
        assert "Multiple" in result.output

    def test_feature_done_no_match(self, runner, initialized_project):
        """Test done command with no matching subtask."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test", "-s", "Task 1"])
        result = runner.invoke(main, ["feature", "done", "F-001", "nonexistent"])
        assert result.exit_code == 0
        assert "No subtask found" in result.output

    def test_feature_note(self, runner, initialized_project):
        """Test adding a note to a feature."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test Feature"])
        result = runner.invoke(main, ["feature", "note", "F-001", "This is a test note"])
        assert result.exit_code == 0
        assert "Added note" in result.output

    def test_feature_note_shows_in_info(self, runner, initialized_project):
        """Test that notes appear in feature info."""
        import os
        os.chdir(initialized_project)
        runner.invoke(main, ["feature", "add", "Test Feature"])
        runner.invoke(main, ["feature", "note", "F-001", "First note"])
        runner.invoke(main, ["feature", "note", "F-001", "Second note"])
        result = runner.invoke(main, ["feature", "info", "F-001"])
        assert result.exit_code == 0
        assert "First note" in result.output
        assert "Second note" in result.output

    def test_feature_note_not_found(self, runner, initialized_project):
        """Test adding note to non-existent feature."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["feature", "note", "F-999", "Some note"])
        assert "not found" in result.output.lower()


class TestProgressCommands:
    """Tests for progress commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def initialized_project(self, tmp_path):
        """Create a project with harness initialized."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"project_name": "test-project"}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        progress = """# Session Progress Log

## Last Session: (No previous session)

### Completed This Session
- [ ] No tasks completed yet

### Current Work In Progress
- [ ] No tasks in progress

### Blockers
- None

### Next Session Should
1. Run init.sh

### Context Notes
- Initialized

### Files Modified This Session
- (none)
"""
        with open(harness_dir / "progress.md", "w") as f:
            f.write(progress)

        return tmp_path

    def test_progress_show(self, runner, initialized_project):
        """Test progress show command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["progress", "show"])
        assert result.exit_code == 0

    def test_progress_completed(self, runner, initialized_project):
        """Test adding completed item."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["progress", "completed", "Finished task"])
        assert result.exit_code == 0
        assert "completed" in result.output.lower()

    def test_progress_wip(self, runner, initialized_project):
        """Test adding WIP item."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["progress", "wip", "Working on feature"])
        assert result.exit_code == 0
        assert "progress" in result.output.lower()

    def test_progress_blocker(self, runner, initialized_project):
        """Test adding blocker."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["progress", "blocker", "Need API key"])
        assert result.exit_code == 0
        assert "blocker" in result.output.lower()

    def test_progress_file(self, runner, initialized_project):
        """Test tracking modified file."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["progress", "file", "src/main.py"])
        assert result.exit_code == 0
        assert "file" in result.output.lower()

    def test_progress_history_empty(self, runner, initialized_project):
        """Test history command with no archived sessions."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["progress", "history"])
        assert result.exit_code == 0
        assert "No session history" in result.output

    def test_progress_history_with_sessions(self, runner, initialized_project):
        """Test history command with archived sessions."""
        import os
        os.chdir(initialized_project)

        # Create session history directory with a session file
        history_dir = initialized_project / ".claude-harness" / "session-history"
        history_dir.mkdir()

        session_content = """## Last Session: 2025-12-12 10:00 UTC

### Completed This Session
- [x] First completed task
- [x] Second completed task

### Current Work In Progress
- [ ] Some work

### Blockers
- None
"""
        (history_dir / "session_2025-12-12_1000_UTC.md").write_text(session_content)

        result = runner.invoke(main, ["progress", "history"])
        assert result.exit_code == 0
        assert "Session History" in result.output
        assert "2025-12-12" in result.output

    def test_progress_history_show_session(self, runner, initialized_project):
        """Test showing a specific historical session."""
        import os
        os.chdir(initialized_project)

        # Create session history
        history_dir = initialized_project / ".claude-harness" / "session-history"
        history_dir.mkdir()

        session_content = """## Last Session: 2025-12-12 10:00 UTC

### Completed This Session
- [x] Test task one
"""
        (history_dir / "session_2025-12-12_1000_UTC.md").write_text(session_content)

        result = runner.invoke(main, ["progress", "history", "--show", "1"])
        assert result.exit_code == 0
        assert "Test task one" in result.output


class TestContextCommands:
    """Tests for context commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def initialized_project(self, tmp_path):
        """Create a project with harness initialized."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {
            "project_name": "test-project",
            "context_tracking": {"enabled": True, "budget": 200000},
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        progress = "# Session Progress Log\n"
        with open(harness_dir / "progress.md", "w") as f:
            f.write(progress)

        features = {"current_phase": "Phase 1", "features": []}
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        return tmp_path

    def test_context_show(self, runner, initialized_project):
        """Test context show command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "show"])
        assert result.exit_code == 0

    def test_context_show_full(self, runner, initialized_project):
        """Test context show --full command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "show", "--full"])
        assert result.exit_code == 0

    def test_context_reset(self, runner, initialized_project):
        """Test context reset command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "reset"])
        assert result.exit_code == 0
        assert "reset" in result.output.lower()

    def test_context_track_file(self, runner, initialized_project):
        """Test context track-file command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "track-file", "test.py", "1000"])
        assert result.exit_code == 0
        assert "tracked" in result.output.lower()

    def test_context_start_task(self, runner, initialized_project):
        """Test context start-task command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "start-task", "F-001"])
        assert result.exit_code == 0
        assert "started" in result.output.lower()

    def test_context_summary(self, runner, initialized_project):
        """Test context summary command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "summary"])
        assert result.exit_code == 0
        assert "Summary" in result.output

    def test_context_handoff(self, runner, initialized_project):
        """Test context handoff command."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["context", "handoff"])
        assert result.exit_code == 0
        assert "Handoff" in result.output


class TestDetectCommand:
    """Tests for detect command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_detect_empty_directory(self, runner, tmp_path):
        """Test detect on empty directory."""
        import os
        os.chdir(tmp_path)
        result = runner.invoke(main, ["detect"])
        assert result.exit_code == 0
        assert "Detection Results" in result.output

    def test_detect_python_project(self, runner, tmp_path):
        """Test detect on Python project."""
        import os
        # Create requirements.txt
        (tmp_path / "requirements.txt").write_text("flask>=2.0\n")
        os.chdir(tmp_path)
        result = runner.invoke(main, ["detect"])
        assert result.exit_code == 0
        assert "python" in result.output.lower()


class TestE2ECommands:
    """Tests for E2E commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def initialized_project(self, tmp_path):
        """Create a project with harness and feature."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"project_name": "test-project"}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        features = {
            "current_phase": "Phase 1",
            "features": [
                {
                    "id": "F-001",
                    "name": "Test Feature",
                    "status": "pending",
                    "subtasks": [{"name": "Sub 1", "done": False}],
                }
            ],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        # Create e2e directory
        e2e_dir = tmp_path / "e2e" / "tests"
        e2e_dir.mkdir(parents=True)

        return tmp_path

    def test_e2e_generate(self, runner, initialized_project):
        """Test E2E test generation."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["e2e", "generate", "F-001"])
        assert result.exit_code == 0
        assert "Generated" in result.output

        # Check file was created
        test_file = initialized_project / "e2e" / "tests" / "test_f_001.py"
        assert test_file.exists()

    def test_e2e_generate_not_found(self, runner, initialized_project):
        """Test E2E generation for non-existent feature."""
        import os
        os.chdir(initialized_project)
        result = runner.invoke(main, ["e2e", "generate", "F-999"])
        # Either exits with error code or has error message
        assert result.exit_code != 0 or "not found" in result.output.lower() or "error" in result.output.lower()
