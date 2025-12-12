"""Compress command outputs to reduce context usage.

This module provides intelligent compression of verbose command outputs
to reduce token consumption in Claude Code sessions. It preserves
critical information (errors, summaries, key statistics) while removing
repetitive or less important content.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

__all__ = ["OutputCompressor", "CompressionRule", "CompressionResult"]


@dataclass
class CompressionRule:
    """Configuration for compressing a specific command type.

    Attributes:
        keep_lines: Maximum lines to keep from output.
        keep_errors: Whether to preserve error lines.
        keep_summary: Whether to preserve summary sections.
        keep_stats: Whether to preserve statistics.
        keep_first: Lines to always keep from the start.
        keep_last: Lines to always keep from the end.
        error_patterns: Regex patterns that indicate error lines.
        summary_patterns: Regex patterns that indicate summary lines.
        stats_patterns: Regex patterns that indicate statistics.
        custom_processor: Optional custom processing function.
    """

    keep_lines: int = 50
    keep_errors: bool = True
    keep_summary: bool = True
    keep_stats: bool = False
    keep_first: int = 5
    keep_last: int = 10
    error_patterns: List[str] = field(default_factory=list)
    summary_patterns: List[str] = field(default_factory=list)
    stats_patterns: List[str] = field(default_factory=list)
    custom_processor: Optional[Callable[[str], str]] = None


@dataclass
class CompressionResult:
    """Result of output compression.

    Attributes:
        output: The compressed output string.
        original_lines: Number of lines in original output.
        compressed_lines: Number of lines after compression.
        tokens_saved: Estimated tokens saved.
        compression_ratio: Ratio of compressed to original size.
        errors_found: List of error lines extracted.
        summary_found: Summary text if extracted.
    """

    output: str
    original_lines: int
    compressed_lines: int
    tokens_saved: int
    compression_ratio: float
    errors_found: List[str] = field(default_factory=list)
    summary_found: Optional[str] = None


class OutputCompressor:
    """Compress command outputs to reduce context usage.

    This class provides intelligent compression of verbose command outputs
    based on configurable rules per command type. It preserves important
    information while removing noise.

    Example:
        >>> compressor = OutputCompressor()
        >>> output = "..." # Long pytest output
        >>> result = compressor.compress("pytest", output)
        >>> print(f"Saved {result.tokens_saved} tokens")
    """

    # Default compression rules by command type
    COMPRESSION_RULES: Dict[str, CompressionRule] = {
        "pytest": CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=15,
            error_patterns=[
                r"^FAILED",
                r"^ERROR",
                r"^E\s+",
                r"AssertionError",
                r"Exception",
                r"Traceback",
                r"^>\s+",
                r"pytest\.raises",
            ],
            summary_patterns=[
                r"^=+\s*(FAILURES|ERRORS|short test summary|passed|failed)",
                r"^\d+\s+(passed|failed|error|warning|skipped)",
                r"^=+\s*\d+\s+(passed|failed)",
            ],
        ),
        "python": CompressionRule(
            keep_lines=60,
            keep_errors=True,
            keep_summary=False,
            keep_first=5,
            keep_last=20,
            error_patterns=[
                r"Traceback",
                r"^\s+File\s+",
                r"Error:",
                r"Exception:",
                r"Warning:",
            ],
        ),
        "npm": CompressionRule(
            keep_lines=30,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"^npm ERR!",
                r"^npm WARN",
                r"error",
                r"ENOENT",
                r"EACCES",
                r"not found",
            ],
            summary_patterns=[
                r"added\s+\d+\s+packages",
                r"up to date",
                r"found\s+\d+\s+vulnerabilities",
            ],
        ),
        "yarn": CompressionRule(
            keep_lines=30,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"error",
                r"warning",
                r"YN\d{4}:",
            ],
            summary_patterns=[
                r"Done in",
                r"success",
            ],
        ),
        "pip": CompressionRule(
            keep_lines=20,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=8,
            error_patterns=[
                r"ERROR:",
                r"WARNING:",
                r"Could not",
                r"No matching",
                r"failed",
            ],
            summary_patterns=[
                r"Successfully installed",
                r"Requirement already satisfied",
            ],
        ),
        "git diff": CompressionRule(
            keep_lines=100,
            keep_errors=False,
            keep_summary=False,
            keep_stats=True,
            keep_first=5,
            keep_last=5,
            stats_patterns=[
                r"^\d+\s+files?\s+changed",
                r"^\s*\d+\s+insertions?",
                r"^\s*\d+\s+deletions?",
            ],
        ),
        "git log": CompressionRule(
            keep_lines=30,
            keep_errors=False,
            keep_summary=False,
            keep_first=30,
            keep_last=0,
        ),
        "git status": CompressionRule(
            keep_lines=50,
            keep_errors=False,
            keep_summary=True,
            keep_first=5,
            keep_last=5,
            summary_patterns=[
                r"^On branch",
                r"^Changes to be committed",
                r"^Changes not staged",
                r"^Untracked files",
                r"nothing to commit",
            ],
        ),
        "docker": CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
            keep_first=5,
            keep_last=15,
            error_patterns=[
                r"error",
                r"ERROR",
                r"failed",
                r"Cannot",
                r"denied",
            ],
            summary_patterns=[
                r"Successfully built",
                r"Successfully tagged",
                r"digest:",
            ],
        ),
        "docker-compose": CompressionRule(
            keep_lines=40,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"error",
                r"ERROR",
                r"failed",
            ],
            summary_patterns=[
                r"Creating",
                r"Starting",
                r"done",
            ],
        ),
        "make": CompressionRule(
            keep_lines=30,
            keep_errors=True,
            keep_summary=False,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"error:",
                r"Error:",
                r"undefined reference",
                r"make\[\d+\]:\s+\*\*\*",
                r"failed",
            ],
        ),
        "cargo": CompressionRule(
            keep_lines=40,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=15,
            error_patterns=[
                r"^error",
                r"^warning",
                r"cannot find",
                r"failed to",
            ],
            summary_patterns=[
                r"Compiling",
                r"Finished",
                r"Running",
            ],
        ),
        "go": CompressionRule(
            keep_lines=40,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"cannot",
                r"undefined",
                r"error:",
                r"FAIL",
            ],
            summary_patterns=[
                r"^ok\s+",
                r"^PASS",
                r"^---\s+FAIL",
            ],
        ),
        "ruff": CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"^\S+\.py:\d+:\d+:",
                r"error:",
            ],
            summary_patterns=[
                r"Found \d+ error",
                r"All checks passed",
            ],
        ),
        "mypy": CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"^\S+\.py:\d+:",
                r"error:",
                r"note:",
            ],
            summary_patterns=[
                r"Found \d+ error",
                r"Success:",
            ],
        ),
        "eslint": CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=10,
            error_patterns=[
                r"error\s+",
                r"warning\s+",
                r"\d+:\d+\s+error",
            ],
            summary_patterns=[
                r"\d+ problems?",
                r"\d+ errors?",
                r"\d+ warnings?",
            ],
        ),
        "jest": CompressionRule(
            keep_lines=50,
            keep_errors=True,
            keep_summary=True,
            keep_first=5,
            keep_last=15,
            error_patterns=[
                r"FAIL",
                r"Error:",
                r"Expected",
                r"Received",
                r"at Object",
            ],
            summary_patterns=[
                r"Test Suites:",
                r"Tests:",
                r"Snapshots:",
                r"Time:",
                r"Ran all test",
            ],
        ),
        "webpack": CompressionRule(
            keep_lines=40,
            keep_errors=True,
            keep_summary=True,
            keep_first=3,
            keep_last=15,
            error_patterns=[
                r"ERROR",
                r"error",
                r"Module not found",
                r"Failed to compile",
            ],
            summary_patterns=[
                r"compiled successfully",
                r"webpack \d+\.\d+",
                r"Built at:",
            ],
        ),
    }

    # Minimum output length to consider compression (characters)
    MIN_COMPRESS_LENGTH = 1000

    # Tokens per character estimate
    TOKENS_PER_CHAR = 0.25

    def __init__(
        self,
        enabled: bool = True,
        min_compress_length: int = 1000,
        custom_rules: Optional[Dict[str, CompressionRule]] = None,
    ):
        """Initialize the output compressor.

        Args:
            enabled: Whether compression is enabled.
            min_compress_length: Minimum output length to trigger compression.
            custom_rules: Additional or override compression rules.
        """
        self.enabled = enabled
        self.min_compress_length = min_compress_length
        self._rules = dict(self.COMPRESSION_RULES)
        if custom_rules:
            self._rules.update(custom_rules)

    def compress(
        self,
        command: str,
        output: str,
        force: bool = False,
    ) -> Tuple[str, int]:
        """Compress command output and return tokens saved.

        Args:
            command: The command that was executed.
            output: The command's output to compress.
            force: Force compression even if below threshold.

        Returns:
            Tuple of (compressed_output, tokens_saved).

        Example:
            >>> compressor = OutputCompressor()
            >>> compressed, saved = compressor.compress("pytest", long_output)
        """
        result = self.compress_with_details(command, output, force)
        return result.output, result.tokens_saved

    def compress_with_details(
        self,
        command: str,
        output: str,
        force: bool = False,
    ) -> CompressionResult:
        """Compress output and return detailed results.

        Args:
            command: The command that was executed.
            output: The command's output to compress.
            force: Force compression even if below threshold.

        Returns:
            CompressionResult with full details.
        """
        original_length = len(output)
        original_lines = output.count("\n") + 1

        # Check if compression should be applied
        if not self.enabled or (
            not force and not self.should_compress(command, original_length)
        ):
            return CompressionResult(
                output=output,
                original_lines=original_lines,
                compressed_lines=original_lines,
                tokens_saved=0,
                compression_ratio=1.0,
            )

        # Get compression rule
        rule = self.get_compression_rule(command)
        if not rule:
            # Default compression: keep first and last lines
            compressed = self._default_compress(output)
            return self._build_result(output, compressed)

        # Apply rule-based compression
        compressed, errors, summary = self._apply_rule(output, rule)

        result = self._build_result(output, compressed)
        result.errors_found = errors
        result.summary_found = summary
        return result

    def should_compress(self, command: str, output_length: int) -> bool:
        """Determine if output should be compressed.

        Args:
            command: The command that was executed.
            output_length: Length of the output in characters.

        Returns:
            True if compression should be applied.
        """
        if not self.enabled:
            return False
        return output_length >= self.min_compress_length

    def get_compression_rule(self, command: str) -> Optional[CompressionRule]:
        """Get the compression rule for a command.

        Args:
            command: The command string.

        Returns:
            CompressionRule if found, None otherwise.
        """
        # Direct match
        command_lower = command.lower().strip()

        # Check for exact match first
        for cmd_key in self._rules:
            if command_lower == cmd_key:
                return self._rules[cmd_key]

        # Check for prefix/contains match
        for cmd_key in self._rules:
            if (
                command_lower.startswith(cmd_key)
                or cmd_key in command_lower
            ):
                return self._rules[cmd_key]

        # Check for command basename
        parts = command_lower.split()
        if parts:
            base_cmd = parts[0].split("/")[-1]
            for cmd_key in self._rules:
                if base_cmd == cmd_key or base_cmd.startswith(cmd_key):
                    return self._rules[cmd_key]

        return None

    def extract_errors(self, output: str, command: str = "") -> List[str]:
        """Extract error lines from output.

        Args:
            output: The command output.
            command: Optional command to get specific error patterns.

        Returns:
            List of lines that appear to be errors.
        """
        errors = []
        lines = output.split("\n")

        # Get command-specific patterns
        rule = self.get_compression_rule(command) if command else None
        patterns = rule.error_patterns if rule else []

        # Add common error patterns
        common_patterns = [
            r"error",
            r"Error",
            r"ERROR",
            r"failed",
            r"Failed",
            r"FAILED",
            r"Exception",
            r"Traceback",
        ]

        all_patterns = patterns + common_patterns
        compiled_patterns = [re.compile(p, re.IGNORECASE) for p in all_patterns]

        in_traceback = False
        for line in lines:
            # Track multi-line tracebacks
            if "Traceback" in line:
                in_traceback = True
            if in_traceback:
                errors.append(line)
                if line.strip() and not line.startswith(" "):
                    if "Error" in line or "Exception" in line:
                        in_traceback = False
                continue

            # Check patterns
            for pattern in compiled_patterns:
                if pattern.search(line):
                    errors.append(line)
                    break

        return errors

    def extract_summary(self, output: str, command_type: str = "") -> str:
        """Extract summary information from output.

        Args:
            output: The command output.
            command_type: Type of command for specific patterns.

        Returns:
            Summary string if found, empty string otherwise.
        """
        rule = self.get_compression_rule(command_type) if command_type else None
        patterns = rule.summary_patterns if rule else []

        # Add common summary patterns
        common_patterns = [
            r"^=+.*$",  # Divider lines often before summaries
            r"^\d+\s+(passed|failed|error|warning)",
            r"^(Success|Failure|Complete)",
        ]

        all_patterns = patterns + common_patterns
        compiled_patterns = [re.compile(p, re.MULTILINE) for p in all_patterns]

        summary_lines = []
        lines = output.split("\n")

        for line in lines:
            for pattern in compiled_patterns:
                if pattern.search(line):
                    summary_lines.append(line)
                    break

        return "\n".join(summary_lines)

    def add_rule(self, command: str, rule: CompressionRule) -> None:
        """Add or update a compression rule.

        Args:
            command: Command name/pattern.
            rule: CompressionRule configuration.
        """
        self._rules[command] = rule

    def remove_rule(self, command: str) -> None:
        """Remove a compression rule.

        Args:
            command: Command name to remove.
        """
        self._rules.pop(command, None)

    def _apply_rule(
        self,
        output: str,
        rule: CompressionRule,
    ) -> Tuple[str, List[str], Optional[str]]:
        """Apply a compression rule to output.

        Returns tuple of (compressed_output, errors, summary).
        """
        lines = output.split("\n")
        kept_lines: List[str] = []
        errors: List[str] = []
        summary_lines: List[str] = []

        # Custom processor takes precedence
        if rule.custom_processor:
            return rule.custom_processor(output), [], None

        # Compile patterns
        error_patterns = [re.compile(p) for p in rule.error_patterns]
        summary_patterns = [re.compile(p) for p in rule.summary_patterns]
        stats_patterns = [re.compile(p) for p in rule.stats_patterns]

        # Track important lines
        important_indices = set()

        # Always keep first N lines
        for i in range(min(rule.keep_first, len(lines))):
            important_indices.add(i)

        # Always keep last N lines
        for i in range(max(0, len(lines) - rule.keep_last), len(lines)):
            important_indices.add(i)

        # Find errors, summaries, and stats
        in_traceback = False
        for i, line in enumerate(lines):
            # Track tracebacks
            if "Traceback" in line:
                in_traceback = True
            if in_traceback:
                important_indices.add(i)
                errors.append(line)
                if line.strip() and not line.startswith(" "):
                    if "Error" in line or "Exception" in line:
                        in_traceback = False
                continue

            # Check error patterns
            if rule.keep_errors:
                for pattern in error_patterns:
                    if pattern.search(line):
                        important_indices.add(i)
                        errors.append(line)
                        break

            # Check summary patterns
            if rule.keep_summary:
                for pattern in summary_patterns:
                    if pattern.search(line):
                        important_indices.add(i)
                        summary_lines.append(line)
                        break

            # Check stats patterns
            if rule.keep_stats:
                for pattern in stats_patterns:
                    if pattern.search(line):
                        important_indices.add(i)
                        break

        # Build output
        sorted_indices = sorted(important_indices)

        # If we have few enough important lines, include them all
        if len(sorted_indices) <= rule.keep_lines:
            for i in sorted_indices:
                kept_lines.append(lines[i])
        else:
            # Need to truncate
            # Keep first portion
            first_count = rule.keep_lines // 2
            last_count = rule.keep_lines - first_count

            first_indices = sorted_indices[:first_count]
            last_indices = sorted_indices[-last_count:]

            for i in first_indices:
                kept_lines.append(lines[i])

            kept_lines.append(
                f"\n... [{len(lines) - len(first_indices) - len(last_indices)} lines omitted] ...\n"
            )

            for i in last_indices:
                kept_lines.append(lines[i])

        compressed = "\n".join(kept_lines)
        summary = "\n".join(summary_lines) if summary_lines else None

        return compressed, errors, summary

    def _default_compress(self, output: str) -> str:
        """Apply default compression when no rule matches."""
        lines = output.split("\n")
        total = len(lines)

        if total <= 50:
            return output

        # Keep first 10, last 20
        first = lines[:10]
        last = lines[-20:]
        omitted = total - 30

        return "\n".join(
            first + [f"\n... [{omitted} lines omitted] ...\n"] + last
        )

    def _build_result(self, original: str, compressed: str) -> CompressionResult:
        """Build a CompressionResult from original and compressed output."""
        original_length = len(original)
        compressed_length = len(compressed)
        original_lines = original.count("\n") + 1
        compressed_lines = compressed.count("\n") + 1

        chars_saved = original_length - compressed_length
        tokens_saved = int(chars_saved * self.TOKENS_PER_CHAR)

        compression_ratio = (
            compressed_length / original_length if original_length > 0 else 1.0
        )

        return CompressionResult(
            output=compressed,
            original_lines=original_lines,
            compressed_lines=compressed_lines,
            tokens_saved=max(0, tokens_saved),
            compression_ratio=compression_ratio,
        )

    def get_statistics(self) -> dict:
        """Get compressor configuration statistics.

        Returns:
            Dictionary with compressor statistics.
        """
        return {
            "enabled": self.enabled,
            "min_compress_length": self.min_compress_length,
            "rules_count": len(self._rules),
            "supported_commands": list(self._rules.keys()),
        }
