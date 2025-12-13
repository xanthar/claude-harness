"""Tests for output_helper.py - Output control utilities."""

import json
import pytest
from pathlib import Path

from claude_harness.output_helper import (
    OutputConfig,
    OutputHelper,
    load_output_config,
    truncate_text,
    truncate_list,
    truncate_output,
    format_file_list,
    format_table_value,
    get_output_helper,
)


class TestOutputConfig:
    """Tests for OutputConfig dataclass."""

    def test_defaults(self):
        """Test default values."""
        config = OutputConfig()
        assert config.compact_mode is False
        assert config.max_lines == 50
        assert config.max_files_shown == 20
        assert config.truncate_long_values is True
        assert config.value_max_length == 80


class TestLoadOutputConfig:
    """Tests for load_output_config function."""

    def test_load_from_file(self, tmp_path):
        """Test loading config from file."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config_data = {
            "output": {
                "compact_mode": True,
                "max_lines": 100,
                "max_files_shown": 10,
                "truncate_long_values": False,
            }
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config_data, f)

        config = load_output_config(str(tmp_path))
        assert config.compact_mode is True
        assert config.max_lines == 100
        assert config.max_files_shown == 10
        assert config.truncate_long_values is False

    def test_load_defaults_when_no_file(self, tmp_path):
        """Test defaults when config file doesn't exist."""
        config = load_output_config(str(tmp_path))
        assert config.compact_mode is False
        assert config.max_lines == 50

    def test_load_defaults_when_no_output_section(self, tmp_path):
        """Test defaults when output section is missing."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config_data = {"project_name": "test"}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config_data, f)

        config = load_output_config(str(tmp_path))
        assert config.compact_mode is False


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_no_truncation_needed(self):
        """Test when text is within limit."""
        result = truncate_text("short", max_length=80)
        assert result == "short"

    def test_truncation_applied(self):
        """Test truncation with suffix."""
        result = truncate_text("a" * 100, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_exact_length(self):
        """Test when text is exactly max length."""
        result = truncate_text("a" * 80, max_length=80)
        assert result == "a" * 80

    def test_custom_suffix(self):
        """Test with custom suffix."""
        result = truncate_text("a" * 100, max_length=20, suffix=" [...]")
        assert result.endswith(" [...]")


class TestTruncateList:
    """Tests for truncate_list function."""

    def test_no_truncation_needed(self):
        """Test when list is within limit."""
        items = ["a", "b", "c"]
        result = truncate_list(items, max_items=5)
        assert result == ["a", "b", "c"]

    def test_truncation_applied(self):
        """Test list truncation with summary."""
        items = list(range(10))
        result = truncate_list(items, max_items=3)
        assert len(result) == 4  # 3 items + summary
        assert "... and 7 more" in result[-1]

    def test_custom_formatter(self):
        """Test with custom item formatter."""
        items = [1, 2, 3]
        result = truncate_list(items, max_items=5, format_item=lambda x: f"Item {x}")
        assert result == ["Item 1", "Item 2", "Item 3"]

    def test_empty_list(self):
        """Test with empty list."""
        result = truncate_list([], max_items=5)
        assert result == []

    def test_custom_summary_format(self):
        """Test with custom summary format."""
        items = list(range(10))
        result = truncate_list(
            items, max_items=2, summary_format="({count} hidden)"
        )
        assert result[-1] == "(8 hidden)"


class TestTruncateOutput:
    """Tests for truncate_output function."""

    def test_no_truncation_needed(self):
        """Test when lines are within limit."""
        lines = ["line1", "line2", "line3"]
        result = truncate_output(lines, max_lines=10)
        assert result == lines

    def test_truncation_applied(self):
        """Test output truncation."""
        lines = [f"line{i}" for i in range(100)]
        result = truncate_output(lines, max_lines=5)
        assert len(result) == 6  # 5 lines + indicator
        assert "95 more lines" in result[-1]

    def test_unlimited_lines(self):
        """Test with max_lines=0 (unlimited)."""
        lines = [f"line{i}" for i in range(100)]
        result = truncate_output(lines, max_lines=0)
        assert result == lines

    def test_no_truncation_indicator(self):
        """Test without truncation indicator."""
        lines = [f"line{i}" for i in range(100)]
        result = truncate_output(lines, max_lines=5, show_truncation=False)
        assert len(result) == 5
        assert "more lines" not in str(result)


class TestFormatFileList:
    """Tests for format_file_list function."""

    def test_format_filenames(self):
        """Test formatting file names."""
        config = OutputConfig(max_files_shown=5)
        files = ["/path/to/file1.py", "/path/to/file2.py"]
        result = format_file_list(files, config, show_full_path=False)
        assert result == ["file1.py", "file2.py"]

    def test_format_full_paths(self):
        """Test formatting full paths."""
        config = OutputConfig(max_files_shown=5)
        files = ["/path/to/file1.py", "/path/to/file2.py"]
        result = format_file_list(files, config, show_full_path=True)
        assert "/path/to/file1.py" in result[0]

    def test_truncate_file_list(self):
        """Test truncation of file list."""
        config = OutputConfig(max_files_shown=2)
        files = [f"/path/file{i}.py" for i in range(10)]
        result = format_file_list(files, config)
        assert len(result) == 3  # 2 files + summary
        assert "8 more files" in result[-1]

    def test_empty_file_list(self):
        """Test with empty file list."""
        config = OutputConfig()
        result = format_file_list([], config)
        assert result == ["(none)"]


class TestFormatTableValue:
    """Tests for format_table_value function."""

    def test_short_value(self):
        """Test short value passes through."""
        config = OutputConfig()
        result = format_table_value("short", config)
        assert result == "short"

    def test_long_value_truncated(self):
        """Test long value is truncated."""
        config = OutputConfig(value_max_length=20)
        result = format_table_value("a" * 100, config)
        assert len(result) == 20
        assert result.endswith("...")

    def test_truncation_disabled(self):
        """Test when truncation is disabled."""
        config = OutputConfig(truncate_long_values=False)
        long_value = "a" * 100
        result = format_table_value(long_value, config)
        assert result == long_value


class TestOutputHelper:
    """Tests for OutputHelper class."""

    @pytest.fixture
    def helper(self, tmp_path):
        """Create a helper with test config."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        config_data = {
            "output": {
                "compact_mode": True,
                "max_lines": 10,
                "max_files_shown": 3,
            }
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config_data, f)
        return OutputHelper(str(tmp_path))

    def test_is_compact(self, helper):
        """Test is_compact method."""
        assert helper.is_compact() is True

    def test_truncate_lines(self, helper):
        """Test truncate_lines method."""
        lines = [f"line{i}" for i in range(50)]
        result = helper.truncate_lines(lines)
        assert len(result) == 11  # 10 lines + indicator

    def test_format_files(self, helper):
        """Test format_files method."""
        files = [f"/path/file{i}.py" for i in range(10)]
        result = helper.format_files(files)
        assert len(result) == 4  # 3 files + summary


class TestGetOutputHelper:
    """Tests for get_output_helper function."""

    def test_get_helper(self, tmp_path):
        """Test getting an output helper."""
        helper = get_output_helper(str(tmp_path))
        assert isinstance(helper, OutputHelper)
