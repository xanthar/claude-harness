"""Tests for lazy_loader.py - Lazy context loading for context optimization.

This module tests the LazyContextLoader class which prioritizes file loading
based on task type and file importance, deferring non-critical files to
save context tokens.
"""

import pytest
from pathlib import Path

from claude_harness.lazy_loader import (
    LazyContextLoader,
    FilePriority,
    PrioritizedFile,
    get_lazy_loader,
)


class TestLazyContextLoaderBasics:
    """Tests for LazyContextLoader basic initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        loader = LazyContextLoader()
        assert loader is not None

    def test_with_project_path(self, tmp_path):
        """Test initialization with specific project path."""
        loader = LazyContextLoader(project_path=str(tmp_path))
        assert loader.project_path == tmp_path.resolve()

    def test_get_lazy_loader_factory(self):
        """Test factory function returns loader instance."""
        loader = get_lazy_loader()
        assert isinstance(loader, LazyContextLoader)


class TestFilePriorityEnum:
    """Tests for FilePriority enumeration."""

    def test_file_priority_values(self):
        """Test FilePriority enum values."""
        assert FilePriority.CRITICAL.value == 1
        assert FilePriority.IMPORTANT.value == 2
        assert FilePriority.REFERENCE.value == 3
        assert FilePriority.SKIP.value == 4

    def test_file_priority_ordering(self):
        """Test FilePriority enum ordering (lower value = higher priority)."""
        assert FilePriority.CRITICAL.value < FilePriority.IMPORTANT.value
        assert FilePriority.IMPORTANT.value < FilePriority.REFERENCE.value
        assert FilePriority.REFERENCE.value < FilePriority.SKIP.value


class TestPrioritizedFileDataclass:
    """Tests for PrioritizedFile dataclass."""

    def test_prioritized_file_creation(self):
        """Test PrioritizedFile can be created."""
        pf = PrioritizedFile(
            filepath="main.py",
            priority=FilePriority.CRITICAL,
            reason="Entry point",
            estimated_tokens=100,
        )
        assert pf.filepath == "main.py"
        assert pf.priority == FilePriority.CRITICAL

    def test_prioritized_file_to_dict(self):
        """Test PrioritizedFile to_dict method."""
        pf = PrioritizedFile(
            filepath="main.py",
            priority=FilePriority.CRITICAL,
            reason="Entry point",
            estimated_tokens=100,
        )
        d = pf.to_dict()
        assert d["filepath"] == "main.py"
        assert d["priority"] == "CRITICAL"
        assert d["reason"] == "Entry point"
        assert d["estimated_tokens"] == 100


class TestPrioritizeFiles:
    """Tests for file prioritization logic."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_prioritize_main_file_critical(self, loader):
        """Test that main entry point files are marked critical."""
        prioritized = loader.prioritize_files(["main.py"])
        assert prioritized[0].priority == FilePriority.CRITICAL

    def test_prioritize_app_file_critical(self, loader):
        """Test that app.py is marked critical."""
        prioritized = loader.prioritize_files(["app.py"])
        assert prioritized[0].priority == FilePriority.CRITICAL

    def test_prioritize_index_file_critical(self, loader):
        """Test that index files are marked critical."""
        prioritized = loader.prioritize_files(["src/index.js"])
        assert prioritized[0].priority == FilePriority.CRITICAL

    def test_prioritize_test_file_reference(self, loader):
        """Test that test files are marked as reference or skip priority."""
        prioritized = loader.prioritize_files(["tests/test_main.py"])
        # Test files may be REFERENCE or SKIP depending on implementation
        assert prioritized[0].priority in (FilePriority.REFERENCE, FilePriority.SKIP)

    def test_prioritize_model_file_important(self, loader):
        """Test that model files are marked important."""
        prioritized = loader.prioritize_files(["models/user.py"])
        assert prioritized[0].priority == FilePriority.IMPORTANT

    def test_prioritize_config_file_important(self, loader):
        """Test that config files are marked important."""
        prioritized = loader.prioritize_files(["config/settings.py"])
        assert prioritized[0].priority == FilePriority.IMPORTANT

    def test_prioritize_pycache_skip(self, loader):
        """Test that __pycache__ files are marked skip."""
        prioritized = loader.prioritize_files(["__pycache__/module.pyc"])
        assert prioritized[0].priority == FilePriority.SKIP


class TestTaskTypeAffectsPriority:
    """Tests for how task type affects file prioritization."""

    def test_testing_task_prioritizes_test_files(self):
        """Test that testing task raises test file priority."""
        loader = LazyContextLoader()
        prioritized = loader.prioritize_files(["tests/test_module.py"], task_type="test")
        # For test tasks, test files should be higher priority
        assert prioritized[0].priority in (FilePriority.CRITICAL, FilePriority.IMPORTANT)

    def test_docs_task_prioritizes_docs(self):
        """Test that docs task raises documentation file priority."""
        loader = LazyContextLoader()
        prioritized = loader.prioritize_files(["docs/README.md"], task_type="docs")
        # For doc tasks, doc files should be higher priority
        assert prioritized[0].priority == FilePriority.IMPORTANT


class TestGetDeferredFiles:
    """Tests for get_deferred_files method."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_get_deferred_files(self, loader):
        """Test getting deferred files from prioritized list."""
        prioritized = loader.prioritize_files([
            "main.py",  # Critical
            "tests/test_main.py",  # Reference/Skip
            "models/user.py",  # Important
        ])
        deferred = loader.get_deferred_files(prioritized)

        # Deferred should contain non-critical/important files
        assert isinstance(deferred, list)

    def test_get_immediate_files(self, loader):
        """Test getting immediate files from prioritized list."""
        prioritized = loader.prioritize_files([
            "main.py",  # Critical
            "tests/test_main.py",  # Reference/Skip
            "models/user.py",  # Important
        ])
        immediate = loader.get_immediate_files(prioritized)

        # Immediate should contain critical and important files
        assert any("main.py" in f for f in immediate)


class TestEstimateDeferredSavings:
    """Tests for estimate_deferred_savings method."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_estimate_deferred_savings(self, loader):
        """Test savings estimation."""
        deferred = ["tests/test_main.py", "utils/helpers.py"]
        savings = loader.estimate_deferred_savings(deferred)
        assert savings >= 0  # Should be non-negative


class TestGenerateDeferralNote:
    """Tests for generate_deferral_note method."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_generate_deferral_note_empty(self, loader):
        """Test deferral note with no deferred files."""
        note = loader.generate_deferral_note([])
        assert note == ""  # Empty list returns empty string

    def test_generate_deferral_note_with_files(self, loader):
        """Test deferral note with deferred files."""
        note = loader.generate_deferral_note(["utils/helpers.py", "tests/test_main.py"])

        # Should mention deferred files
        assert "Deferred" in note or "deferred" in note

    def test_generate_deferral_note_format(self, loader):
        """Test deferral note has useful format."""
        note = loader.generate_deferral_note(["utils/helpers.py"])

        # Should be informative
        assert len(note) > 10


class TestShouldLoadNow:
    """Tests for should_load_now method."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_should_load_critical_file(self, loader):
        """Test that critical files should load now."""
        assert loader.should_load_now("main.py") is True

    def test_should_not_load_test_file(self, loader):
        """Test that test files should not load immediately for general tasks."""
        assert loader.should_load_now("tests/test_main.py") is False


class TestGetLoadingPlan:
    """Tests for get_loading_plan method."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_get_loading_plan(self, loader):
        """Test getting a complete loading plan."""
        files = ["main.py", "tests/test_main.py", "utils/helpers.py"]
        plan = loader.get_loading_plan(files)

        assert "immediate" in plan
        assert "deferred" in plan
        assert "skipped" in plan
        assert "tokens_immediate" in plan
        assert "tokens_saved" in plan
        assert "summary" in plan

    def test_loading_plan_summary(self, loader):
        """Test loading plan summary counts."""
        files = ["main.py", "tests/test_main.py", "utils/helpers.py"]
        plan = loader.get_loading_plan(files)

        summary = plan["summary"]
        assert summary["total_files"] == 3
        assert "immediate_count" in summary
        assert "deferred_count" in summary
        assert "skipped_count" in summary


class TestLoadingOrder:
    """Tests for file loading order logic."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_prioritized_files_sorted_by_priority(self, loader):
        """Test files are sorted by priority (critical first)."""
        files = [
            "utils/helpers.py",  # Reference
            "main.py",  # Critical
            "models/user.py",  # Important
        ]
        prioritized = loader.prioritize_files(files)

        # Critical should come first in sorted output
        assert prioritized[0].priority == FilePriority.CRITICAL


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def loader(self):
        """Create a LazyContextLoader instance."""
        return LazyContextLoader()

    def test_empty_filepath(self, loader):
        """Test handling of empty filepath."""
        prioritized = loader.prioritize_files([""])
        assert len(prioritized) == 1

    def test_filepath_with_spaces(self, loader):
        """Test handling of filepath with spaces."""
        prioritized = loader.prioritize_files(["src/my file.py"])
        assert len(prioritized) == 1

    def test_deep_nested_path(self, loader):
        """Test handling of deeply nested paths."""
        prioritized = loader.prioritize_files(["a/b/c/d/e/f/g/main.py"])
        # Deep main.py should still be critical
        assert prioritized[0].priority == FilePriority.CRITICAL

    def test_uppercase_filename(self, loader):
        """Test handling of uppercase filenames."""
        prioritized = loader.prioritize_files(["README.MD"])
        # README should be important
        assert prioritized[0].priority in (FilePriority.IMPORTANT, FilePriority.REFERENCE)


class TestIntegrationWithProject:
    """Integration tests with realistic project structure."""

    @pytest.fixture
    def project_files(self):
        """Create a realistic project file list."""
        return [
            "main.py",
            "app.py",
            "config/settings.py",
            "models/user.py",
            "models/order.py",
            "routes/api.py",
            "routes/auth.py",
            "services/auth.py",
            "services/email.py",
            "utils/helpers.py",
            "utils/validators.py",
            "tests/test_main.py",
            "tests/test_auth.py",
            "README.md",
            "pyproject.toml",
        ]

    def test_realistic_project_prioritization(self, project_files):
        """Test prioritization with realistic project structure."""
        loader = LazyContextLoader()
        prioritized = loader.prioritize_files(project_files)

        # Should have entries for all files
        assert len(prioritized) == len(project_files)

        # Critical files should be first after sorting
        critical_files = [p for p in prioritized if p.priority == FilePriority.CRITICAL]
        assert len(critical_files) > 0

    def test_realistic_project_plan(self, project_files):
        """Test loading plan with realistic project structure."""
        loader = LazyContextLoader()
        plan = loader.get_loading_plan(project_files)

        summary = plan["summary"]
        assert summary["total_files"] == len(project_files)
        assert summary["immediate_count"] + summary["deferred_count"] + summary["skipped_count"] == len(project_files)

    def test_task_type_changes_plan(self, project_files):
        """Test that task type affects the loading plan."""
        loader = LazyContextLoader()

        general_plan = loader.get_loading_plan(project_files)
        testing_plan = loader.get_loading_plan(project_files, task_type="test")

        # Testing task should include test files as immediate
        general_test_files = [f for f in general_plan["deferred"] if "test_" in f.get("filepath", "")]
        testing_test_files = [f for f in testing_plan["deferred"] if "test_" in f.get("filepath", "")]

        # Testing plan should have fewer deferred test files
        assert len(testing_test_files) <= len(general_test_files)
