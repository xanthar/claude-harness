"""Tests for file_filter.py - File filtering for context optimization.

This module tests the FileFilter class which determines which files should
be tracked/included in context and which should be skipped to save tokens.
"""

import pytest
from pathlib import Path

from claude_harness.file_filter import (
    FileFilter,
    FilterResult,
)


class TestFileFilterBasics:
    """Tests for FileFilter basic initialization and defaults."""

    def test_default_exclude_patterns(self):
        """Test that default exclude patterns are set."""
        ff = FileFilter()
        # Check ALWAYS_SKIP contains expected patterns
        assert ".git/" in ff.ALWAYS_SKIP or ".git" in ff.ALWAYS_SKIP
        assert "node_modules/" in ff.ALWAYS_SKIP
        assert "__pycache__/" in ff.ALWAYS_SKIP
        assert "venv/" in ff.ALWAYS_SKIP
        assert ".venv/" in ff.ALWAYS_SKIP

    def test_default_exclude_extensions(self):
        """Test that default exclude extensions are set."""
        ff = FileFilter()
        assert "*.pyc" in ff.ALWAYS_SKIP
        assert "*.exe" in ff.ALWAYS_SKIP
        assert "*.dll" in ff.ALWAYS_SKIP
        assert "*.so" in ff.ALWAYS_SKIP

    def test_custom_exclude_patterns(self):
        """Test setting custom exclude patterns."""
        ff = FileFilter(custom_excludes=["custom_cache/", "build/", "*.custom"])
        assert "custom_cache/" in ff.custom_excludes
        assert "build/" in ff.custom_excludes
        assert "*.custom" in ff.custom_excludes
        # Should still have defaults
        assert ".git/" in ff.ALWAYS_SKIP or ".git" in ff.ALWAYS_SKIP


class TestShouldTrackFile:
    """Tests for the should_track_file method."""

    @pytest.fixture
    def file_filter(self):
        """Create a FileFilter instance."""
        return FileFilter()

    def test_should_track_regular_file(self, file_filter):
        """Test that regular source files are tracked."""
        result = file_filter.should_track_file("src/main.py")
        assert result is True

    def test_should_track_regular_js_file(self, file_filter):
        """Test that regular JavaScript files are tracked."""
        result = file_filter.should_track_file("src/app.js")
        assert result is True

    def test_should_track_regular_ts_file(self, file_filter):
        """Test that regular TypeScript files are tracked."""
        result = file_filter.should_track_file("src/components/Button.tsx")
        assert result is True

    def test_should_skip_git_directory(self, file_filter):
        """Test that .git directory files are skipped."""
        result = file_filter.should_track_file(".git/config")
        assert result is False

    def test_should_skip_git_nested(self, file_filter):
        """Test that nested .git files are skipped."""
        result = file_filter.should_track_file("project/.git/hooks/pre-commit")
        assert result is False

    def test_should_skip_node_modules(self, file_filter):
        """Test that node_modules directory is skipped."""
        result = file_filter.should_track_file("node_modules/lodash/index.js")
        assert result is False

    def test_should_skip_nested_node_modules(self, file_filter):
        """Test that nested node_modules are skipped."""
        result = file_filter.should_track_file("packages/frontend/node_modules/react/index.js")
        assert result is False

    def test_should_skip_venv(self, file_filter):
        """Test that venv directory is skipped."""
        result = file_filter.should_track_file("venv/lib/python3.12/site-packages/flask/__init__.py")
        assert result is False

    def test_should_skip_dot_venv(self, file_filter):
        """Test that .venv directory is skipped."""
        result = file_filter.should_track_file(".venv/bin/activate")
        assert result is False

    def test_should_skip_pycache(self, file_filter):
        """Test that __pycache__ directory is skipped."""
        result = file_filter.should_track_file("src/__pycache__/main.cpython-312.pyc")
        assert result is False

    def test_should_skip_binary_files_exe(self, file_filter):
        """Test that .exe binary files are skipped."""
        result = file_filter.should_track_file("dist/app.exe")
        assert result is False

    def test_should_skip_binary_files_dll(self, file_filter):
        """Test that .dll binary files are skipped."""
        result = file_filter.should_track_file("lib/module.dll")
        assert result is False

    def test_should_skip_binary_files_so(self, file_filter):
        """Test that .so binary files are skipped."""
        result = file_filter.should_track_file("lib/module.so")
        assert result is False

    def test_should_skip_pyc_files(self, file_filter):
        """Test that .pyc compiled files are skipped."""
        result = file_filter.should_track_file("src/module.pyc")
        assert result is False

    def test_should_track_markdown(self, file_filter):
        """Test that markdown files are tracked."""
        result = file_filter.should_track_file("README.md")
        assert result is True

    def test_should_track_json(self, file_filter):
        """Test that JSON files are tracked."""
        result = file_filter.should_track_file("package.json")
        assert result is True

    def test_should_track_config_files(self, file_filter):
        """Test that config files are tracked."""
        # Note: .gitignore is in ALWAYS_SKIP in the actual implementation
        assert file_filter.should_track_file("pyproject.toml") is True
        assert file_filter.should_track_file("tsconfig.json") is True


class TestCustomExcludePatterns:
    """Tests for custom exclude patterns."""

    def test_custom_exclude_dirs(self):
        """Test custom exclude directories are respected."""
        ff = FileFilter(custom_excludes=["dist/", "coverage/"])
        assert ff.should_track_file("dist/bundle.js") is False
        assert ff.should_track_file("coverage/lcov.info") is False

    def test_custom_exclude_extensions(self):
        """Test custom exclude extensions are respected."""
        ff = FileFilter(custom_excludes=["*.log", "*.tmp"])
        assert ff.should_track_file("app.log") is False
        assert ff.should_track_file("cache.tmp") is False

    def test_custom_patterns_preserve_defaults(self):
        """Test that custom patterns don't override defaults."""
        ff = FileFilter(custom_excludes=["custom/"])
        # Custom should work
        assert ff.should_track_file("custom/file.py") is False
        # Defaults should still work
        assert ff.should_track_file(".git/config") is False
        assert ff.should_track_file("node_modules/pkg/index.js") is False


class TestFilterFileList:
    """Tests for filter_file_list method."""

    @pytest.fixture
    def file_filter(self):
        """Create a FileFilter instance."""
        return FileFilter()

    def test_filter_file_list_empty(self, file_filter):
        """Test filtering empty file list."""
        tracked, skipped = file_filter.filter_file_list([])
        assert tracked == []
        assert skipped == []

    def test_filter_file_list_all_included(self, file_filter):
        """Test filtering when all files should be included."""
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        tracked, skipped = file_filter.filter_file_list(files)
        assert len(tracked) == 3
        assert tracked == files
        assert len(skipped) == 0

    def test_filter_file_list_all_excluded(self, file_filter):
        """Test filtering when all files should be excluded."""
        files = [
            "node_modules/lodash/index.js",
            ".git/config",
            "venv/lib/site-packages/flask/__init__.py",
        ]
        tracked, skipped = file_filter.filter_file_list(files)
        assert len(tracked) == 0
        assert len(skipped) == 3

    def test_filter_file_list_mixed(self, file_filter):
        """Test filtering with mixed files."""
        files = [
            "src/main.py",
            "node_modules/react/index.js",
            "tests/test_app.py",
            ".git/hooks/pre-commit",
            "README.md",
        ]
        tracked, skipped = file_filter.filter_file_list(files)
        assert len(tracked) == 3
        assert "src/main.py" in tracked
        assert "tests/test_app.py" in tracked
        assert "README.md" in tracked
        assert len(skipped) == 2


class TestGetSkipReason:
    """Tests for get_skip_reason method."""

    @pytest.fixture
    def file_filter(self):
        """Create a FileFilter instance."""
        return FileFilter()

    def test_get_skip_reason_tracked_file(self, file_filter):
        """Test that tracked files have no skip reason."""
        reason = file_filter.get_skip_reason("src/main.py")
        assert reason is None

    def test_get_skip_reason_git_directory(self, file_filter):
        """Test skip reason for .git directory."""
        reason = file_filter.get_skip_reason(".git/config")
        # Returns string like "Version control (.git/)"
        assert reason is not None
        assert "Version control" in reason or ".git" in reason

    def test_get_skip_reason_node_modules(self, file_filter):
        """Test skip reason for node_modules."""
        reason = file_filter.get_skip_reason("node_modules/pkg/index.js")
        assert reason is not None
        assert "Dependencies" in reason or "node_modules" in reason

    def test_get_skip_reason_binary_extension(self, file_filter):
        """Test skip reason for binary extension."""
        reason = file_filter.get_skip_reason("app.exe")
        assert reason is not None
        assert "Binary" in reason or ".exe" in reason

    def test_get_skip_reason_pyc_extension(self, file_filter):
        """Test skip reason for .pyc extension."""
        reason = file_filter.get_skip_reason("module.pyc")
        assert reason is not None
        assert "Binary" in reason or ".pyc" in reason


class TestEstimateSavings:
    """Tests for estimate_savings method."""

    @pytest.fixture
    def file_filter(self):
        """Create a FileFilter instance."""
        return FileFilter()

    def test_estimate_savings_empty_list(self, file_filter):
        """Test savings estimation with empty list."""
        result = file_filter.estimate_savings([])
        assert result == 0

    def test_estimate_savings_with_files(self, file_filter):
        """Test savings estimation with skipped files."""
        skipped_files = [
            "node_modules/pkg/index.js",
            ".git/objects/abc123",
        ]
        result = file_filter.estimate_savings(skipped_files)
        # Should return an estimated token count
        assert result > 0
        assert isinstance(result, int)

    def test_estimate_savings_lock_files(self, file_filter):
        """Test savings estimation for lock files (large)."""
        skipped_files = ["package-lock.json"]
        result = file_filter.estimate_savings(skipped_files)
        # Lock files should have significant savings estimate
        assert result > 0


class TestFilterWithPath:
    """Tests for file filtering using actual Path objects."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project structure."""
        # Create source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")
        (src_dir / "utils.py").write_text("# utils")

        # Create test files
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("# tests")

        # Create node_modules
        node_dir = tmp_path / "node_modules" / "pkg"
        node_dir.mkdir(parents=True)
        (node_dir / "index.js").write_text("// pkg")

        # Create .git
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")

        # Create __pycache__
        cache_dir = src_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "main.cpython-312.pyc").write_bytes(b"binary")

        return tmp_path

    def test_filter_project_files(self, temp_project):
        """Test filtering actual project files."""
        ff = FileFilter()
        all_files = list(temp_project.rglob("*"))
        file_paths = [str(f.relative_to(temp_project)) for f in all_files if f.is_file()]

        tracked, skipped = ff.filter_file_list(file_paths)

        # Should include source and test files
        assert any("main.py" in f for f in tracked)
        assert any("utils.py" in f for f in tracked)
        assert any("test_main.py" in f for f in tracked)

        # Should exclude node_modules, .git, __pycache__
        assert not any("node_modules" in f for f in tracked)
        assert not any(".git" in f for f in tracked)
        assert not any("__pycache__" in f for f in tracked)


class TestFilterResultDataclass:
    """Tests for FilterResult dataclass."""

    def test_filter_result_creation(self):
        """Test FilterResult can be created."""
        result = FilterResult(
            tracked=["a.py", "b.py"],
            skipped=["c.pyc"],
        )
        assert len(result.tracked) == 2
        assert len(result.skipped) == 1

    def test_filter_result_with_skip_reasons(self):
        """Test FilterResult with skip_reasons."""
        result = FilterResult(
            tracked=["a.py"],
            skipped=["c.pyc", "d.exe"],
            skip_reasons={"c.pyc": "Binary files", "d.exe": "Binary files"},
        )
        assert len(result.skip_reasons) == 2
        assert "c.pyc" in result.skip_reasons

    def test_filter_result_tokens_saved(self):
        """Test FilterResult with tokens_saved_estimate."""
        result = FilterResult(
            tracked=[],
            skipped=["node_modules/x.js"],
            tokens_saved_estimate=1000,
        )
        assert result.tokens_saved_estimate == 1000


class TestSkipReasonString:
    """Tests for skip reason string format."""

    def test_skip_reason_format(self):
        """Test skip reason returns properly formatted strings."""
        ff = FileFilter()
        # Skip reason returns strings like "Category (pattern)"
        reason = ff.get_skip_reason(".git/config")
        if reason:
            # Should contain category and pattern info
            assert "(" in reason and ")" in reason


class TestFilterWithDetails:
    """Tests for filter_with_details method."""

    @pytest.fixture
    def file_filter(self):
        """Create a FileFilter instance."""
        return FileFilter()

    def test_filter_with_details_returns_filter_result(self, file_filter):
        """Test filter_with_details returns FilterResult."""
        files = ["src/main.py", "node_modules/x.js"]
        result = file_filter.filter_with_details(files)

        assert isinstance(result, FilterResult)
        assert "src/main.py" in result.tracked
        assert "node_modules/x.js" in result.skipped
        assert "node_modules/x.js" in result.skip_reasons

    def test_filter_with_details_estimates_tokens(self, file_filter):
        """Test filter_with_details includes token estimate."""
        files = ["node_modules/x.js", "package-lock.json"]
        result = file_filter.filter_with_details(files)

        assert result.tokens_saved_estimate > 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def file_filter(self):
        """Create a FileFilter instance."""
        return FileFilter()

    def test_empty_filepath(self, file_filter):
        """Test handling of empty filepath."""
        result = file_filter.should_track_file("")
        # Should handle gracefully - either track or skip
        assert isinstance(result, bool)

    def test_filepath_with_spaces(self, file_filter):
        """Test handling of filepath with spaces."""
        result = file_filter.should_track_file("src/my file.py")
        assert result is True

    def test_filepath_with_special_chars(self, file_filter):
        """Test handling of filepath with special characters."""
        result = file_filter.should_track_file("src/file-name_v2.0.py")
        assert result is True

    def test_deep_nested_path(self, file_filter):
        """Test handling of deeply nested paths."""
        result = file_filter.should_track_file("a/b/c/d/e/f/g/h/i/main.py")
        assert result is True

    def test_hidden_file_not_in_excluded_dir(self, file_filter):
        """Test that hidden files outside excluded dirs are tracked."""
        result = file_filter.should_track_file("src/.env")
        assert result is True

    def test_double_extension(self, file_filter):
        """Test files with double extensions."""
        # .tar.gz is in ALWAYS_SKIP
        result = file_filter.should_track_file("archive.tar.gz")
        assert result is False


class TestCustomIncludes:
    """Tests for custom include patterns (whitelist)."""

    def test_custom_include_overrides_exclude(self):
        """Test that custom includes can override exclusions."""
        ff = FileFilter(custom_includes=["important.log"])
        # .log files are normally skipped
        assert ff.should_track_file("important.log") is True
        # Other .log files still skipped
        assert ff.should_track_file("other.log") is False

    def test_add_include_method(self):
        """Test add_include method."""
        ff = FileFilter()
        ff.add_include("special.exe")
        assert ff.should_track_file("special.exe") is True

    def test_add_exclude_method(self):
        """Test add_exclude method."""
        ff = FileFilter()
        ff.add_exclude("*.custom")
        assert ff.should_track_file("file.custom") is False


class TestGetStatistics:
    """Tests for get_statistics method."""

    def test_get_statistics(self):
        """Test get_statistics returns expected fields."""
        ff = FileFilter()
        stats = ff.get_statistics()

        assert "enabled" in stats
        assert "builtin_patterns" in stats
        assert "custom_excludes" in stats
        assert "custom_includes" in stats
        assert "total_excludes" in stats
        assert "categories" in stats
        assert stats["enabled"] is True

    def test_get_statistics_with_custom(self):
        """Test get_statistics reflects custom patterns."""
        ff = FileFilter(custom_excludes=["a/", "b/"])
        stats = ff.get_statistics()

        assert stats["custom_excludes"] == 2


class TestDisabledFilter:
    """Tests for disabled filter behavior."""

    def test_disabled_filter_tracks_everything(self):
        """Test that disabled filter tracks all files."""
        ff = FileFilter(enabled=False)
        # Even normally excluded files should be tracked
        assert ff.should_track_file(".git/config") is True
        assert ff.should_track_file("node_modules/x.js") is True
        assert ff.should_track_file("app.exe") is True

    def test_disabled_filter_skip_reason_none(self):
        """Test disabled filter returns no skip reasons."""
        ff = FileFilter(enabled=False)
        reason = ff.get_skip_reason(".git/config")
        assert reason is None
