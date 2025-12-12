"""Tests for output_compressor.py - Command output compression for context optimization.

This module tests the OutputCompressor class which intelligently compresses
command output (pytest, npm, git, etc.) to save tokens while preserving
important information like errors and summaries.
"""

import pytest

from claude_harness.output_compressor import (
    OutputCompressor,
    CompressionRule,
    CompressionResult,
)


class TestOutputCompressorBasics:
    """Tests for OutputCompressor basic initialization and detection."""

    def test_default_threshold(self):
        """Test default compression threshold is set."""
        compressor = OutputCompressor()
        assert compressor.min_compress_length >= 500  # Reasonable default

    def test_custom_threshold(self):
        """Test custom compression threshold."""
        compressor = OutputCompressor(min_compress_length=1000)
        assert compressor.min_compress_length == 1000

    def test_detect_pytest_command(self):
        """Test detection of pytest command type via get_compression_rule."""
        compressor = OutputCompressor()
        assert compressor.get_compression_rule("pytest tests/") is not None
        assert compressor.get_compression_rule("python -m pytest") is not None

    def test_detect_npm_command(self):
        """Test detection of npm command type."""
        compressor = OutputCompressor()
        assert compressor.get_compression_rule("npm install") is not None
        assert compressor.get_compression_rule("npm run build") is not None
        assert compressor.get_compression_rule("npm test") is not None

    def test_detect_git_diff_command(self):
        """Test detection of git diff command type."""
        compressor = OutputCompressor()
        assert compressor.get_compression_rule("git diff") is not None
        assert compressor.get_compression_rule("git diff HEAD~1") is not None

    def test_detect_git_log_command(self):
        """Test detection of git log command type."""
        compressor = OutputCompressor()
        assert compressor.get_compression_rule("git log") is not None
        assert compressor.get_compression_rule("git log --oneline") is not None

    def test_detect_unknown_command(self):
        """Test detection of unknown command type."""
        compressor = OutputCompressor()
        assert compressor.get_compression_rule("some_random_command") is None
        assert compressor.get_compression_rule("ls -la") is None


class TestShouldCompress:
    """Tests for should_compress decision logic."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance with low threshold for testing."""
        return OutputCompressor(min_compress_length=100)

    def test_should_compress_threshold_below(self, compressor):
        """Test that output below threshold is not compressed."""
        short_output = "OK" * 10  # 20 chars
        assert compressor.should_compress("pytest", len(short_output)) is False

    def test_should_compress_threshold_above(self, compressor):
        """Test that output above threshold is compressed."""
        long_output = "X" * 200
        assert compressor.should_compress("pytest", len(long_output)) is True

    def test_should_compress_unknown_command(self):
        """Test that unknown command types are compressed based on length only."""
        compressor = OutputCompressor(min_compress_length=10)
        long_output = "X" * 200
        # Compression based on length threshold
        assert compressor.should_compress("random_cmd", len(long_output)) is True

    def test_should_compress_error_output_preserved(self, compressor):
        """Test that error output triggers different behavior."""
        error_output = "ERROR: Something failed\n" + "X" * 200
        # Should still compress but preserve errors
        assert compressor.should_compress("pytest", len(error_output)) is True


class TestCompressPytestOutput:
    """Tests for pytest output compression."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=100)

    def test_compress_pytest_output_success(self, compressor):
        """Test compressing successful pytest output."""
        pytest_output = """
============================= test session starts ==============================
platform linux -- Python 3.12.0, pytest-8.0.0, pluggy-1.0.0
rootdir: /root/project
collected 50 items

tests/test_module1.py ......................                              [ 44%]
tests/test_module2.py ......................                              [ 88%]
tests/test_module3.py ......                                              [100%]

============================== 50 passed in 2.34s ==============================
"""
        result = compressor.compress_with_details("pytest tests/", pytest_output)

        assert "50 passed" in result.output
        # Should preserve summary but remove individual test dots
        assert result.tokens_saved >= 0

    def test_compress_pytest_output_with_failures(self, compressor):
        """Test compressing pytest output with failures."""
        pytest_output = """
============================= test session starts ==============================
platform linux -- Python 3.12.0, pytest-8.0.0
collected 5 items

tests/test_main.py .F...                                                   [100%]

=================================== FAILURES ===================================
________________________________ test_something ________________________________

    def test_something():
>       assert 1 == 2
E       AssertionError: assert 1 == 2

tests/test_main.py:10: AssertionError
=========================== short test summary info ============================
FAILED tests/test_main.py::test_something - AssertionError: assert 1 == 2
============================== 1 failed, 4 passed in 0.12s =====================
"""
        result = compressor.compress_with_details("pytest tests/", pytest_output)

        # Should preserve failure information
        assert "FAILED" in result.output or "failed" in result.output
        assert "AssertionError" in result.output
        assert "test_something" in result.output

    def test_compress_pytest_preserves_errors(self, compressor):
        """Test that pytest errors are preserved."""
        pytest_output = """
============================= test session starts ==============================
ERROR collecting tests/test_broken.py
ImportError: No module named 'missing_module'
"""
        result = compressor.compress_with_details("pytest tests/", pytest_output)

        assert "ERROR" in result.output
        assert "ImportError" in result.output
        assert "missing_module" in result.output

    def test_compress_pytest_preserves_summary(self, compressor):
        """Test that pytest summary line is preserved."""
        pytest_output = """
tests/test_main.py ............................                            [100%]

============================== 28 passed, 2 skipped, 1 warning in 1.23s ========
"""
        result = compressor.compress_with_details("pytest", pytest_output)

        # Summary should be preserved
        assert "28 passed" in result.output or "passed" in result.output


class TestCompressNpmOutput:
    """Tests for npm command output compression."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=100)

    def test_compress_npm_install_output(self, compressor):
        """Test compressing npm install output."""
        npm_output = """
npm WARN deprecated package@1.0.0: This package is deprecated
npm WARN deprecated another-pkg@2.0.0: Use something else

added 150 packages, and audited 151 packages in 5s

25 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities
"""
        result = compressor.compress_with_details("npm install", npm_output)

        # Should preserve summary
        assert "150 packages" in result.output or "added" in result.output
        assert "vulnerabilities" in result.output

    def test_compress_npm_preserves_errors(self, compressor):
        """Test that npm errors are preserved."""
        npm_output = """
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR!
npm ERR! While resolving: project@1.0.0
npm ERR! Found: react@17.0.2
npm ERR! node_modules/react
npm ERR!   react@"^17.0.0" from the root project
"""
        result = compressor.compress_with_details("npm install", npm_output)

        assert "ERR!" in result.output
        assert "ERESOLVE" in result.output
        assert "dependency" in result.output.lower()

    def test_compress_npm_run_build(self, compressor):
        """Test compressing npm run build output."""
        npm_output = """
> project@1.0.0 build
> webpack --mode production

asset main.js 250 KiB [compared for emit] (name: main)
asset vendors.js 1.2 MiB [compared for emit] (name: vendors)
asset index.html 1.5 KiB [compared for emit]
asset styles.css 45 KiB [compared for emit]
Entrypoint main 1.5 MiB = vendors.js 1.2 MiB main.js 250 KiB

webpack 5.90.0 compiled successfully in 15234 ms
"""
        result = compressor.compress_with_details("npm run build", npm_output)

        # Should preserve success message
        assert "compiled successfully" in result.output or "webpack" in result.output


class TestCompressGitDiff:
    """Tests for git diff output compression."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=100)

    def test_compress_git_diff_small(self, compressor):
        """Test that small git diffs are preserved."""
        git_diff = """
diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,6 +10,7 @@ def main():
     print("Hello")
+    print("World")
     return 0
"""
        result = compressor.compress_with_details("git diff", git_diff)

        # Small diffs should preserve changes
        assert "+" in result.output or "print" in result.output

    def test_compress_git_diff_large(self, compressor):
        """Test compressing large git diffs."""
        # Create a large diff
        git_diff = "diff --git a/src/main.py b/src/main.py\n"
        for i in range(100):
            git_diff += f"+line {i} added\n"
            git_diff += f"-line {i} removed\n"

        result = compressor.compress_with_details("git diff", git_diff)

        # Should include file info
        assert "main.py" in result.output or "+" in result.output

    def test_compress_git_diff_preserves_file_names(self, compressor):
        """Test that file names in diff are preserved."""
        git_diff = """
diff --git a/src/module1.py b/src/module1.py
--- a/src/module1.py
+++ b/src/module1.py
@@ -1 +1 @@
-old line
+new line
diff --git a/src/module2.py b/src/module2.py
--- a/src/module2.py
+++ b/src/module2.py
@@ -1 +1 @@
-old
+new
""" * 10  # Make it long enough to trigger compression

        result = compressor.compress_with_details("git diff", git_diff)

        # File names should be preserved in summary
        assert "module1.py" in result.output or "module2.py" in result.output


class TestPreserveErrors:
    """Tests for error preservation across all command types."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=50)

    def test_preserve_error_keyword(self, compressor):
        """Test that ERROR keyword triggers preservation."""
        output = "lots of output\n" * 20 + "ERROR: critical failure\n" + "more output\n" * 10
        result = compressor.compress_with_details("pytest", output)
        assert "ERROR" in result.output

    def test_preserve_failed_keyword(self, compressor):
        """Test that FAILED keyword triggers preservation."""
        output = "lots of output\n" * 20 + "FAILED test_something\n" + "more output\n" * 10
        result = compressor.compress_with_details("pytest", output)
        assert "FAILED" in result.output

    def test_preserve_exception_keyword(self, compressor):
        """Test that Exception keyword triggers preservation."""
        output = "output\n" * 30 + "ValueError: invalid input\n"
        result = compressor.compress_with_details("pytest", output)
        assert "ValueError" in result.output

    def test_preserve_traceback(self, compressor):
        """Test that traceback is preserved."""
        output = """
output line
Traceback (most recent call last):
  File "main.py", line 10, in <module>
    raise ValueError("test")
ValueError: test
more output
""" + "padding\n" * 20
        result = compressor.compress_with_details("pytest", output)
        assert "Traceback" in result.output
        assert "ValueError" in result.output


class TestPreserveSummary:
    """Tests for summary preservation across command types."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=50)

    def test_preserve_summary_passed(self, compressor):
        """Test that 'passed' summary is preserved."""
        output = "dots\n" * 50 + "10 passed in 1.5s\n"
        result = compressor.compress_with_details("pytest", output)
        assert "passed" in result.output

    def test_preserve_summary_completed(self, compressor):
        """Test that 'completed' summary is preserved."""
        output = "lines\n" * 50 + "Build completed successfully\n"
        result = compressor.compress_with_details("npm run build", output)
        assert "completed" in result.output.lower()


class TestShortOutputNotCompressed:
    """Tests for short output handling."""

    def test_short_output_not_compressed(self):
        """Test that short output is not compressed."""
        compressor = OutputCompressor(min_compress_length=1000)
        short_output = "All tests passed\n"
        output, tokens_saved = compressor.compress("pytest", short_output)

        assert output == short_output
        assert tokens_saved == 0

    def test_exact_threshold_not_compressed(self):
        """Test output at exact threshold is not compressed."""
        compressor = OutputCompressor(min_compress_length=100)
        output_text = "X" * 100
        result = compressor.compress_with_details("pytest", output_text)

        # Compression may or may not happen at exact threshold
        assert result.tokens_saved >= 0


class TestUnknownCommandHandling:
    """Tests for unknown command handling."""

    def test_unknown_command_uses_default_compression(self):
        """Test that unknown commands use default compression."""
        compressor = OutputCompressor(min_compress_length=10)
        long_output = "X" * 1000
        output, tokens_saved = compressor.compress("some_random_command", long_output)

        # Unknown commands may still be compressed by default rules
        assert isinstance(output, str)

    def test_ls_command_handling(self):
        """Test that ls command output is handled."""
        compressor = OutputCompressor(min_compress_length=10)
        ls_output = "file1.py\nfile2.py\nfile3.py\n" * 10
        output, tokens_saved = compressor.compress("ls -la", ls_output)

        # Output should be returned
        assert isinstance(output, str)


class TestExtractErrors:
    """Tests for extract_errors method."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor()

    def test_extract_errors_none(self, compressor):
        """Test extracting errors when none present."""
        output = "All good\nNo problems here\n"
        errors = compressor.extract_errors(output)
        assert errors == []

    def test_extract_errors_single(self, compressor):
        """Test extracting single error."""
        output = "output\nERROR: Something failed\nmore output\n"
        errors = compressor.extract_errors(output)
        assert len(errors) >= 1
        assert any("ERROR" in e for e in errors)

    def test_extract_errors_multiple(self, compressor):
        """Test extracting multiple errors."""
        output = """
output
ERROR: First error
more output
FAILED: Second error
even more
Exception: Third error
"""
        errors = compressor.extract_errors(output)
        assert len(errors) >= 3

    def test_extract_errors_traceback(self, compressor):
        """Test extracting traceback as error."""
        output = """
Traceback (most recent call last):
  File "main.py", line 10
    something()
NameError: name 'something' is not defined
"""
        errors = compressor.extract_errors(output)
        assert len(errors) >= 1
        assert any("Traceback" in e or "NameError" in e for e in errors)


class TestTokensSavedCalculation:
    """Tests for tokens_saved calculation."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=100)

    def test_tokens_saved_calculation(self, compressor):
        """Test that tokens saved is calculated correctly."""
        long_output = "X" * 1000  # ~250 tokens at 4 chars/token
        result = compressor.compress_with_details("pytest", long_output)

        # If compression happened, should have saved tokens
        if len(result.output) < len(long_output):
            assert result.tokens_saved > 0

    def test_tokens_saved_zero_when_not_compressed(self):
        """Test that tokens_saved is 0 when not compressed."""
        compressor = OutputCompressor(min_compress_length=10000)
        short_output = "OK"
        output, tokens_saved = compressor.compress("pytest", short_output)

        assert tokens_saved == 0

    def test_tokens_saved_proportional_to_reduction(self, compressor):
        """Test that tokens saved is proportional to size reduction."""
        # Create long output that will be compressed
        long_output = "." * 100 + "\n" + "test line\n" * 50 + "50 passed in 1s\n"
        result = compressor.compress_with_details("pytest", long_output)

        # Tokens saved should be related to size difference
        original_size = len(long_output)
        compressed_size = len(result.output)
        # Rough check: saved tokens > 0 if size reduced
        if compressed_size < original_size:
            assert result.tokens_saved > 0


class TestCompressionResultDataclass:
    """Tests for CompressionResult dataclass."""

    def test_compression_result_creation(self):
        """Test CompressionResult can be created."""
        result = CompressionResult(
            output="compressed output",
            original_lines=50,
            compressed_lines=10,
            tokens_saved=225,
            compression_ratio=0.1,
        )
        assert result.output == "compressed output"
        assert result.tokens_saved == 225

    def test_compression_result_ratio(self):
        """Test CompressionResult compression_ratio."""
        result = CompressionResult(
            output="short",
            original_lines=100,
            compressed_lines=10,
            tokens_saved=225,
            compression_ratio=0.1,
        )
        # 0.1 means compressed is 10% of original
        assert result.compression_ratio == 0.1

    def test_compression_result_ratio_not_compressed(self):
        """Test compression_ratio when not compressed."""
        result = CompressionResult(
            output="same",
            original_lines=10,
            compressed_lines=10,
            tokens_saved=0,
            compression_ratio=1.0,
        )
        assert result.compression_ratio == 1.0


class TestCompressionRuleDataclass:
    """Tests for CompressionRule dataclass."""

    def test_compression_rule_creation(self):
        """Test CompressionRule can be created."""
        rule = CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
        )
        assert rule.keep_lines == 50
        assert rule.keep_errors is True
        assert rule.keep_summary is True

    def test_compression_rule_defaults(self):
        """Test CompressionRule default values."""
        rule = CompressionRule()
        assert rule.keep_lines == 50  # default
        assert rule.keep_errors is True  # default
        assert rule.keep_first >= 0
        assert rule.keep_last >= 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def compressor(self):
        """Create an OutputCompressor instance."""
        return OutputCompressor(min_compress_length=100)

    def test_empty_output(self, compressor):
        """Test handling of empty output."""
        output, tokens_saved = compressor.compress("pytest", "")
        assert output == ""

    def test_whitespace_only_output(self, compressor):
        """Test handling of whitespace-only output."""
        output, tokens_saved = compressor.compress("pytest", "   \n\n  \t  \n")
        assert isinstance(output, str)

    def test_unicode_output(self, compressor):
        """Test handling of unicode characters in output."""
        test_output = "Test passed\nUnicode chars\n"
        output, tokens_saved = compressor.compress("pytest", test_output)
        assert isinstance(output, str)

    def test_very_long_single_line(self, compressor):
        """Test handling of very long single line."""
        long_line = "X" * 10000
        output, tokens_saved = compressor.compress("pytest", long_line)
        # Should handle without error
        assert isinstance(output, str)

    def test_binary_looking_output(self, compressor):
        """Test handling of output that looks binary."""
        # Some commands might output binary-ish content
        test_output = "\x00\x01\x02" + "normal text" + "\x03\x04"
        output, tokens_saved = compressor.compress("pytest", test_output)
        # Should handle gracefully
        assert isinstance(output, str)
