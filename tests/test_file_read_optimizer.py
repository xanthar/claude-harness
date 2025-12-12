"""Tests for file_read_optimizer.py - File read optimization for context management.

This module tests the FileReadOptimizer class which intelligently summarizes
large files (JSON, logs, markdown) to save tokens while preserving structure
and essential information.
"""

import json
import pytest
from pathlib import Path

from claude_harness.file_read_optimizer import (
    FileReadOptimizer,
    get_file_read_optimizer,
)


class TestFileReadOptimizerBasics:
    """Tests for FileReadOptimizer basic initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        optimizer = FileReadOptimizer()
        assert optimizer is not None

    def test_get_file_read_optimizer_factory(self):
        """Test factory function returns optimizer instance."""
        optimizer = get_file_read_optimizer()
        assert isinstance(optimizer, FileReadOptimizer)

    def test_summarizable_extensions(self):
        """Test that summarizable extensions are defined."""
        optimizer = FileReadOptimizer()
        assert ".json" in optimizer.SUMMARIZABLE
        assert ".yaml" in optimizer.SUMMARIZABLE
        assert ".yml" in optimizer.SUMMARIZABLE
        assert ".md" in optimizer.SUMMARIZABLE
        assert ".log" in optimizer.SUMMARIZABLE


class TestShouldSummarize:
    """Tests for should_summarize decision logic."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_should_summarize_large_json(self, optimizer):
        """Test that large JSON files are flagged for summarization."""
        # Large file above threshold
        assert optimizer.should_summarize("data.json", 10000) is True

    def test_should_not_summarize_small_file(self, optimizer):
        """Test that small files are not summarized."""
        # Small file below threshold
        assert optimizer.should_summarize("data.json", 100) is False

    def test_should_summarize_large_log(self, optimizer):
        """Test that large log files are flagged for summarization."""
        assert optimizer.should_summarize("app.log", 10000) is True

    def test_should_summarize_large_markdown(self, optimizer):
        """Test that large markdown files are flagged for summarization."""
        assert optimizer.should_summarize("README.md", 10000) is True

    def test_should_not_summarize_python_file(self, optimizer):
        """Test that Python files are not summarized (not in SUMMARIZABLE)."""
        # Python files are not in the summarizable list
        assert optimizer.should_summarize("main.py", 10000) is False

    def test_should_not_summarize_small_json(self, optimizer):
        """Test that small JSON files are not summarized."""
        assert optimizer.should_summarize("config.json", 100) is False


class TestGetSummaryStrategy:
    """Tests for get_summary_strategy method."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_get_summary_strategy_json(self, optimizer):
        """Test strategy selection for JSON files."""
        strategy = optimizer.get_summary_strategy("data.json")
        assert strategy is not None
        assert strategy["strategy"] == "structure"

    def test_get_summary_strategy_markdown(self, optimizer):
        """Test strategy selection for markdown files."""
        strategy = optimizer.get_summary_strategy("README.md")
        assert strategy is not None
        assert strategy["strategy"] == "headings"

    def test_get_summary_strategy_log(self, optimizer):
        """Test strategy selection for log files."""
        strategy = optimizer.get_summary_strategy("app.log")
        assert strategy is not None
        assert strategy["strategy"] == "tail"

    def test_get_summary_strategy_unknown(self, optimizer):
        """Test strategy selection for unknown file types."""
        strategy = optimizer.get_summary_strategy("data.xyz")
        assert strategy is None

    def test_get_summary_strategy_yaml(self, optimizer):
        """Test strategy selection for YAML files."""
        strategy = optimizer.get_summary_strategy("config.yaml")
        assert strategy is not None
        assert strategy["strategy"] == "structure"


class TestSummarizeJsonStructure:
    """Tests for JSON structure summarization."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_summarize_json_structure_simple(self, optimizer):
        """Test summarizing simple JSON object."""
        json_content = json.dumps({
            "name": "test",
            "version": "1.0.0",
            "description": "A test package",
        })
        result, tokens_saved = optimizer.summarize_file("package.json", json_content)

        assert "name" in result
        assert "version" in result

    def test_summarize_json_structure_nested(self, optimizer):
        """Test summarizing nested JSON object."""
        json_content = json.dumps({
            "level1": {
                "level2": {
                    "level3": {
                        "deep": "value"
                    }
                }
            }
        })
        result, tokens_saved = optimizer.summarize_file("nested.json", json_content)

        # Should show nested structure indication
        assert "level1" in result

    def test_summarize_json_structure_array(self, optimizer):
        """Test summarizing JSON array."""
        json_content = json.dumps([
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"},
            {"id": 3, "name": "item3"},
        ] * 10)  # Make it large
        result, tokens_saved = optimizer.summarize_file("items.json", json_content)

        # Should indicate array
        assert "[" in result or "items" in result.lower()

    def test_extract_json_structure_method(self, optimizer):
        """Test extract_json_structure directly."""
        json_content = json.dumps({
            "name": "test",
            "nested": {"key": "value"},
        })
        result = optimizer.extract_json_structure(json_content, max_depth=2)
        assert "name" in result
        assert "nested" in result


class TestSummarizeMarkdownHeadings:
    """Tests for markdown heading extraction."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_summarize_markdown_headings(self, optimizer):
        """Test extracting markdown headings."""
        markdown_content = """
# Main Title

Some content here that is very long and detailed.

## Section 1

More content about section 1.

### Subsection 1.1

Details about subsection.

## Section 2

Content for section 2.
"""
        result = optimizer.extract_markdown_headings(markdown_content)

        # Should contain headings
        assert "Main Title" in result
        assert "Section 1" in result
        assert "Section 2" in result

    def test_summarize_markdown_preserves_structure(self, optimizer):
        """Test that markdown summary preserves heading hierarchy."""
        markdown_content = """
# Level 1
## Level 2
### Level 3
#### Level 4
""" * 5  # Make it large
        result = optimizer.extract_markdown_headings(markdown_content)

        # Should show heading levels
        assert "#" in result or "Level" in result


class TestTruncateWithIndicator:
    """Tests for truncate_with_indicator method."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_truncate_with_indicator_short_content(self, optimizer):
        """Test that short content is not truncated."""
        content = "line 1\nline 2\nline 3\n"
        result = optimizer.truncate_with_indicator(content, max_lines=100)
        assert result == content
        assert "truncated" not in result.lower()

    def test_truncate_with_indicator_long_content(self, optimizer):
        """Test truncating long content adds indicator."""
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = optimizer.truncate_with_indicator(content, max_lines=10)

        # Should have truncation indicator
        assert "..." in result or "truncated" in result.lower() or "more lines" in result.lower()
        # Should be shorter than original
        assert len(result) < len(content)

    def test_truncate_preserves_beginning(self, optimizer):
        """Test that truncation preserves beginning of content."""
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = optimizer.truncate_with_indicator(content, max_lines=5)

        # First lines should be present
        assert "line 0" in result


class TestGetReadRecommendation:
    """Tests for get_read_recommendation method."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_read_recommendation_small_file(self, optimizer):
        """Test recommendation for small files."""
        recommendation = optimizer.get_read_recommendation("small.json", 500)
        assert recommendation["action"] == "read_full"

    def test_read_recommendation_large_json(self, optimizer):
        """Test recommendation for large JSON files."""
        recommendation = optimizer.get_read_recommendation("large.json", 10000)
        assert recommendation["action"] == "summarize"
        assert recommendation["strategy"] == "structure"

    def test_read_recommendation_large_unsupported(self, optimizer):
        """Test recommendation for large unsupported file types."""
        recommendation = optimizer.get_read_recommendation("large.xyz", 10000)
        # Unknown file type - read full with warning
        assert recommendation["action"] == "read_full"


class TestTokensSavedEstimation:
    """Tests for tokens_saved estimation."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_tokens_saved_estimation_json(self, optimizer):
        """Test token savings estimation for JSON."""
        large_json = json.dumps({"key": "value" * 100})
        result, tokens_saved = optimizer.summarize_file("large.json", large_json)

        # Should have some tokens saved for large content
        if len(result) < len(large_json):
            assert tokens_saved > 0

    def test_tokens_saved_small_file(self, optimizer):
        """Test tokens_saved for small file (no summarization needed)."""
        small_json = '{"key": "value"}'
        result, tokens_saved = optimizer.summarize_file("small.json", small_json)

        # Small file may not need summarization
        assert tokens_saved >= 0


class TestIntegrationWithFiles:
    """Integration tests using actual temporary files."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_optimize_json_file(self, optimizer, tmp_path):
        """Test optimizing a real JSON file."""
        json_file = tmp_path / "data.json"
        data = {"users": [{"id": i, "name": f"User {i}"} for i in range(100)]}
        json_file.write_text(json.dumps(data, indent=2))

        content = json_file.read_text()
        result, tokens_saved = optimizer.summarize_file(str(json_file), content)

        # Should produce a summary
        assert isinstance(result, str)

    def test_optimize_markdown_file(self, optimizer, tmp_path):
        """Test optimizing a real markdown file."""
        md_file = tmp_path / "README.md"
        md_content = """
# Project Name

## Overview

This is a detailed overview that goes on for many lines.
""" * 10
        md_file.write_text(md_content)

        content = md_file.read_text()
        result, tokens_saved = optimizer.summarize_file(str(md_file), content)

        assert "Project Name" in result


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def optimizer(self):
        """Create a FileReadOptimizer instance."""
        return FileReadOptimizer()

    def test_empty_file(self, optimizer):
        """Test handling of empty file."""
        result, tokens_saved = optimizer.summarize_file("empty.json", "")
        # Empty file may return empty string or error message
        assert isinstance(result, str)
        assert tokens_saved == 0

    def test_invalid_json(self, optimizer):
        """Test handling of invalid JSON."""
        invalid_json = "{not valid json: }"
        result, tokens_saved = optimizer.summarize_file("invalid.json", invalid_json)
        # Should handle gracefully
        assert isinstance(result, str)

    def test_very_deeply_nested_json(self, optimizer):
        """Test handling of deeply nested JSON."""
        nested = {"level": None}
        current = nested
        for i in range(50):
            current["level"] = {"level": None}
            current = current["level"]

        json_content = json.dumps(nested)
        result, tokens_saved = optimizer.summarize_file("deep.json", json_content)
        # Should handle without stack overflow
        assert isinstance(result, str)

    def test_json_with_large_strings(self, optimizer):
        """Test JSON with very large string values."""
        json_content = json.dumps({"large": "x" * 10000})
        result, tokens_saved = optimizer.summarize_file("large_string.json", json_content)

        # Should produce a result
        assert isinstance(result, str)

    def test_markdown_without_headings(self, optimizer):
        """Test markdown file without any headings."""
        md_content = "Just some plain text\n" * 20
        result, tokens_saved = optimizer.summarize_file("noheadings.md", md_content)

        # Should fall back to truncation
        assert isinstance(result, str)

    def test_unicode_content(self, optimizer):
        """Test handling of unicode content."""
        json_content = json.dumps({"message": "Hello World", "emoji": "Test"})
        result, tokens_saved = optimizer.summarize_file("unicode.json", json_content)
        assert isinstance(result, str)
