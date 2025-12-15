"""Tests for feature_manager.py - Feature lifecycle management."""

import json
import pytest
from pathlib import Path

from claude_harness.feature_manager import (
    Feature,
    Subtask,
    FeatureManager,
    get_feature_manager,
)


class TestSubtask:
    """Tests for Subtask dataclass."""

    def test_subtask_creation(self):
        """Test basic subtask creation."""
        subtask = Subtask(name="Implement login", done=False)
        assert subtask.name == "Implement login"
        assert subtask.done is False

    def test_subtask_to_dict(self):
        """Test subtask serialization."""
        subtask = Subtask(name="Write tests", done=True)
        data = subtask.to_dict()
        assert data == {"name": "Write tests", "done": True}

    def test_subtask_from_dict(self):
        """Test subtask deserialization."""
        data = {"name": "Deploy", "done": False}
        subtask = Subtask.from_dict(data)
        assert subtask.name == "Deploy"
        assert subtask.done is False

    def test_subtask_from_string(self):
        """Test subtask deserialization from plain string (legacy format)."""
        subtask = Subtask.from_dict("Deploy to production")
        assert subtask.name == "Deploy to production"
        assert subtask.done is False  # Default to not done


class TestFeature:
    """Tests for Feature dataclass."""

    def test_feature_creation_defaults(self):
        """Test feature creation with defaults."""
        feature = Feature(id="F-001", name="User Authentication")
        assert feature.id == "F-001"
        assert feature.name == "User Authentication"
        assert feature.status == "pending"
        assert feature.priority == 0
        assert feature.tests_passing is False
        assert feature.e2e_validated is False
        assert feature.subtasks == []
        assert feature.notes == ""
        assert feature.created_at != ""
        assert feature.completed_at is None
        assert feature.blocked_reason is None

    def test_feature_subtask_progress(self):
        """Test subtask progress calculation."""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            subtasks=[
                Subtask(name="Task 1", done=True),
                Subtask(name="Task 2", done=True),
                Subtask(name="Task 3", done=False),
            ],
        )
        assert feature.subtask_progress == "2/3"

    def test_feature_subtask_progress_empty(self):
        """Test subtask progress with no subtasks."""
        feature = Feature(id="F-001", name="Test Feature")
        assert feature.subtask_progress == "No subtasks"

    def test_feature_is_complete_all_done(self):
        """Test is_complete when all subtasks done."""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            tests_passing=True,
            e2e_validated=True,
            subtasks=[
                Subtask(name="Task 1", done=True),
                Subtask(name="Task 2", done=True),
            ],
        )
        assert feature.is_complete is True

    def test_feature_is_complete_subtasks_pending(self):
        """Test is_complete with pending subtasks."""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            tests_passing=True,
            e2e_validated=True,
            subtasks=[
                Subtask(name="Task 1", done=True),
                Subtask(name="Task 2", done=False),
            ],
        )
        assert feature.is_complete is False

    def test_feature_is_complete_tests_not_passing(self):
        """Test is_complete when tests not passing."""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            tests_passing=False,
            e2e_validated=True,
        )
        assert feature.is_complete is False

    def test_feature_to_dict(self):
        """Test feature serialization."""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            status="in_progress",
            priority=1,
            subtasks=[Subtask(name="Task 1", done=True)],
        )
        data = feature.to_dict()
        assert data["id"] == "F-001"
        assert data["name"] == "Test Feature"
        assert data["status"] == "in_progress"
        assert data["priority"] == 1
        assert len(data["subtasks"]) == 1
        assert data["subtasks"][0]["name"] == "Task 1"

    def test_feature_from_dict(self):
        """Test feature deserialization."""
        data = {
            "id": "F-002",
            "name": "Another Feature",
            "status": "completed",
            "priority": 2,
            "tests_passing": True,
            "e2e_validated": True,
            "subtasks": [{"name": "Sub 1", "done": True}],
            "notes": "Some notes",
            "created_at": "2025-01-01",
            "completed_at": "2025-01-15",
            "blocked_reason": None,
        }
        feature = Feature.from_dict(data)
        assert feature.id == "F-002"
        assert feature.name == "Another Feature"
        assert feature.status == "completed"
        assert feature.tests_passing is True
        assert len(feature.subtasks) == 1

    def test_feature_from_dict_legacy_tests_pass(self):
        """Test feature deserialization with legacy tests_pass field."""
        data = {
            "id": "F-003",
            "name": "Legacy Feature",
            "status": "completed",
            "tests_pass": True,  # Legacy field name
        }
        feature = Feature.from_dict(data)
        assert feature.tests_passing is True  # Should read from tests_pass

    def test_feature_from_dict_tests_passing_takes_precedence(self):
        """Test that tests_passing takes precedence over tests_pass."""
        data = {
            "id": "F-004",
            "name": "Mixed Feature",
            "status": "completed",
            "tests_pass": False,
            "tests_passing": True,  # Should take precedence
        }
        feature = Feature.from_dict(data)
        assert feature.tests_passing is True


class TestFeatureManager:
    """Tests for FeatureManager class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with harness directory."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def manager(self, temp_project):
        """Create a FeatureManager instance."""
        return FeatureManager(str(temp_project))

    def test_init_creates_features_file(self, manager, temp_project):
        """Test that initialization creates features.json when adding feature."""
        features_file = temp_project / ".claude-harness" / "features.json"
        # Adding a feature triggers file creation
        manager.add_feature(name="Test Feature")
        assert features_file.exists()

    def test_add_feature_basic(self, manager):
        """Test adding a basic feature."""
        feature = manager.add_feature(name="User Login")
        assert feature.id == "F-001"
        assert feature.name == "User Login"
        assert feature.status == "pending"

    def test_add_feature_with_subtasks(self, manager):
        """Test adding a feature with subtasks."""
        feature = manager.add_feature(
            name="Authentication",
            subtasks=["Login form", "Logout", "Password reset"],
        )
        assert len(feature.subtasks) == 3
        assert feature.subtasks[0].name == "Login form"
        assert feature.subtasks[0].done is False

    def test_add_feature_with_priority(self, manager):
        """Test adding a feature with priority."""
        feature = manager.add_feature(name="Critical Feature", priority=1)
        assert feature.priority == 1

    def test_add_multiple_features_increments_id(self, manager):
        """Test that feature IDs increment."""
        f1 = manager.add_feature(name="Feature 1")
        f2 = manager.add_feature(name="Feature 2")
        f3 = manager.add_feature(name="Feature 3")
        assert f1.id == "F-001"
        assert f2.id == "F-002"
        assert f3.id == "F-003"

    def test_get_feature(self, manager):
        """Test getting a specific feature."""
        manager.add_feature(name="Test Feature")
        feature = manager.get_feature("F-001")
        assert feature is not None
        assert feature.name == "Test Feature"

    def test_get_feature_not_found(self, manager):
        """Test getting a non-existent feature."""
        feature = manager.get_feature("F-999")
        assert feature is None

    def test_list_features_all(self, manager):
        """Test listing all features."""
        manager.add_feature(name="Feature 1")
        manager.add_feature(name="Feature 2")
        features = manager.list_features()
        assert len(features) == 2

    def test_list_features_by_status(self, manager):
        """Test listing features by status."""
        manager.add_feature(name="Feature 1")
        f2 = manager.add_feature(name="Feature 2")
        manager.start_feature(f2.id)

        pending = manager.list_features(status="pending")
        in_progress = manager.list_features(status="in_progress")

        assert len(pending) == 1
        assert len(in_progress) == 1

    def test_start_feature(self, manager):
        """Test starting a feature."""
        manager.add_feature(name="Test Feature")
        feature = manager.start_feature("F-001")
        assert feature.status == "in_progress"

    def test_start_feature_stops_previous(self, manager):
        """Test that starting a feature stops the previous one."""
        manager.add_feature(name="Feature 1")
        manager.add_feature(name="Feature 2")

        manager.start_feature("F-001")
        manager.start_feature("F-002")

        f1 = manager.get_feature("F-001")
        f2 = manager.get_feature("F-002")

        assert f1.status == "pending"  # Reverted
        assert f2.status == "in_progress"

    def test_complete_feature(self, manager):
        """Test completing a feature."""
        manager.add_feature(name="Test Feature")
        manager.start_feature("F-001")
        feature = manager.complete_feature("F-001")

        assert feature.status == "completed"
        assert feature.completed_at is not None

    def test_update_status_blocked(self, manager):
        """Test blocking a feature."""
        manager.add_feature(name="Test Feature")
        feature = manager.update_status(
            "F-001", "blocked", blocked_reason="Waiting for API"
        )
        assert feature.status == "blocked"
        assert feature.blocked_reason == "Waiting for API"

    def test_add_subtask(self, manager):
        """Test adding a subtask to a feature."""
        manager.add_feature(name="Test Feature")
        feature = manager.add_subtask("F-001", "New Subtask")
        assert len(feature.subtasks) == 1
        assert feature.subtasks[0].name == "New Subtask"

    def test_complete_subtask(self, manager):
        """Test completing a subtask."""
        manager.add_feature(name="Test Feature", subtasks=["Task 1", "Task 2"])
        feature = manager.complete_subtask("F-001", 0)
        assert feature.subtasks[0].done is True
        assert feature.subtasks[1].done is False

    def test_set_tests_passing(self, manager):
        """Test marking tests as passing."""
        manager.add_feature(name="Test Feature")
        feature = manager.set_tests_passing("F-001", True)
        assert feature.tests_passing is True

    def test_set_e2e_validated(self, manager):
        """Test marking E2E as validated."""
        manager.add_feature(name="Test Feature")
        feature = manager.set_e2e_validated("F-001", True)
        assert feature.e2e_validated is True

    def test_get_set_current_phase(self, manager):
        """Test phase management."""
        manager.set_current_phase("Phase 2 - Advanced Features")
        phase = manager.get_current_phase()
        assert phase == "Phase 2 - Advanced Features"

    def test_get_in_progress(self, manager):
        """Test getting the in-progress feature."""
        manager.add_feature(name="Feature 1")
        manager.add_feature(name="Feature 2")
        manager.start_feature("F-002")

        in_progress = manager.get_in_progress()
        assert in_progress is not None
        assert in_progress.id == "F-002"

    def test_get_in_progress_none(self, manager):
        """Test get_in_progress when none active."""
        manager.add_feature(name="Feature 1")
        in_progress = manager.get_in_progress()
        assert in_progress is None

    def test_get_next_pending(self, manager):
        """Test getting next pending feature by priority."""
        manager.add_feature(name="Low Priority", priority=10)
        manager.add_feature(name="High Priority", priority=1)
        manager.add_feature(name="Medium Priority", priority=5)

        next_feature = manager.get_next_pending()
        assert next_feature.name == "High Priority"

    def test_persistence(self, temp_project):
        """Test that features persist across manager instances."""
        manager1 = FeatureManager(str(temp_project))
        manager1.add_feature(name="Persistent Feature")

        manager2 = FeatureManager(str(temp_project))
        features = manager2.list_features()
        assert len(features) == 1
        assert features[0].name == "Persistent Feature"


class TestGetFeatureManager:
    """Tests for get_feature_manager helper function."""

    def test_get_feature_manager(self, tmp_path):
        """Test the convenience function."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        manager = get_feature_manager(str(tmp_path))
        assert isinstance(manager, FeatureManager)


class TestFeatureSync:
    """Tests for sync_from_files functionality."""

    @pytest.fixture
    def manager_with_feature(self, tmp_path):
        """Create a manager with a feature that has subtasks."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        manager = FeatureManager(str(tmp_path))
        manager.add_feature(
            name="Database Setup",
            subtasks=[
                "Create models.py",
                "Write migrations",
                "Add schema validation",
            ]
        )
        return manager

    def test_sync_auto_starts_feature(self, manager_with_feature):
        """Test that sync auto-starts the first pending feature."""
        results = manager_with_feature.sync_from_files(
            ["src/models.py"],
            auto_start=True
        )
        assert "F-001" in results['started']
        feature = manager_with_feature.get_feature("F-001")
        assert feature.status == "in_progress"

    def test_sync_matches_subtask_by_keyword(self, manager_with_feature):
        """Test that files are matched to subtasks by keyword."""
        manager_with_feature.start_feature("F-001")
        results = manager_with_feature.sync_from_files(
            ["src/models.py"],
            auto_start=False
        )
        assert len(results['subtasks_completed']) == 1
        assert results['subtasks_completed'][0][1] == "Create models.py"

    def test_sync_matches_multiple_subtasks(self, manager_with_feature):
        """Test matching multiple files to multiple subtasks."""
        manager_with_feature.start_feature("F-001")
        results = manager_with_feature.sync_from_files(
            ["src/models.py", "migrations/001_initial.py", "src/schema.py"],
            auto_start=False
        )
        # Should match models and migrations, possibly schema
        assert len(results['subtasks_completed']) >= 2

    def test_sync_no_auto_start(self, manager_with_feature):
        """Test that auto_start=False doesn't start features."""
        results = manager_with_feature.sync_from_files(
            ["src/models.py"],
            auto_start=False
        )
        assert results['started'] == []
        assert results['no_match'] == ["src/models.py"]

    def test_sync_empty_files(self, manager_with_feature):
        """Test sync with empty file list."""
        results = manager_with_feature.sync_from_files([], auto_start=True)
        assert results['started'] == []
        assert results['subtasks_completed'] == []

    def test_sync_unmatched_files(self, manager_with_feature):
        """Test that unmatched files are tracked."""
        manager_with_feature.start_feature("F-001")
        results = manager_with_feature.sync_from_files(
            ["totally_unrelated_file.xyz"],
            auto_start=False
        )
        assert "totally_unrelated_file.xyz" in results['no_match']

    def test_extract_keywords(self, manager_with_feature):
        """Test keyword extraction from subtask text."""
        keywords = manager_with_feature._extract_keywords(
            "implement user authentication module"
        )
        assert "user" in keywords
        assert "authentication" in keywords
        assert "module" in keywords
        # Stop words should be filtered
        assert "implement" not in keywords

    def test_sync_auto_completes_feature(self, tmp_path):
        """Test that feature is auto-completed when all subtasks are done."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        manager = FeatureManager(str(tmp_path))
        manager.add_feature(
            name="Simple Feature",
            subtasks=["Create config.py"]
        )
        manager.start_feature("F-001")

        results = manager.sync_from_files(["src/config.py"])

        assert "F-001" in results['features_completed']
        feature = manager.get_feature("F-001")
        assert feature.status == "completed"
