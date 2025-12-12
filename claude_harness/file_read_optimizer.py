"""Smart file reading optimizer for Claude Harness.

Reduces token usage by intelligently summarizing files instead of
reading them fully when appropriate. Uses heuristic-based strategies
for different file types.

Strategies:
- structure: Extract JSON/YAML structure (keys at depth N)
- headings: Extract Markdown headings and first paragraphs
- truncate: Show first N lines with truncation indicator
- tail: Show last N lines (useful for logs)
- head: Show first N lines (useful for data files)
"""

import json
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


# Approximate token ratio
CHARS_PER_TOKEN = 4


class FileReadOptimizer:
    """Optimize file reads to reduce token usage.

    Provides intelligent file summarization strategies based on file type
    and size to minimize context window consumption while preserving
    essential information.
    """

    # File types that can be summarized instead of fully read
    SUMMARIZABLE: Dict[str, Dict[str, Any]] = {
        ".json": {"strategy": "structure", "max_lines": 50},
        ".yaml": {"strategy": "structure", "max_lines": 50},
        ".yml": {"strategy": "structure", "max_lines": 50},
        ".md": {"strategy": "headings", "max_lines": 100},
        ".txt": {"strategy": "truncate", "max_lines": 50},
        ".log": {"strategy": "tail", "lines": 100},
        ".csv": {"strategy": "head", "lines": 20},
    }

    # Size thresholds
    LARGE_FILE_THRESHOLD = 5000  # bytes

    def __init__(self):
        """Initialize the optimizer."""
        pass

    def should_summarize(self, filepath: str, size_bytes: int) -> bool:
        """Determine if a file should be summarized instead of fully read.

        Args:
            filepath: Path to the file
            size_bytes: Size of the file in bytes

        Returns:
            True if the file should be summarized, False to read fully
        """
        # Small files are always read fully
        if size_bytes < self.LARGE_FILE_THRESHOLD:
            return False

        # Check if file extension is summarizable
        suffix = Path(filepath).suffix.lower()
        return suffix in self.SUMMARIZABLE

    def get_summary_strategy(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Get the summarization strategy for a file type.

        Args:
            filepath: Path to the file

        Returns:
            Strategy configuration dict or None if not summarizable
        """
        suffix = Path(filepath).suffix.lower()
        return self.SUMMARIZABLE.get(suffix)

    def summarize_file(self, filepath: str, content: str) -> Tuple[str, int]:
        """Summarize a file's content using the appropriate strategy.

        Args:
            filepath: Path to the file (used to determine strategy)
            content: Full file content

        Returns:
            Tuple of (summarized_content, estimated_tokens_saved)
        """
        original_tokens = len(content) // CHARS_PER_TOKEN

        strategy = self.get_summary_strategy(filepath)
        if strategy is None:
            # No strategy available, return as-is
            return content, 0

        strategy_name = strategy.get("strategy", "truncate")

        if strategy_name == "structure":
            max_depth = strategy.get("max_depth", 2)
            summarized = self._summarize_structured(filepath, content, max_depth)
        elif strategy_name == "headings":
            summarized = self.extract_markdown_headings(content)
        elif strategy_name == "tail":
            lines = strategy.get("lines", 100)
            summarized = self._extract_tail(content, lines)
        elif strategy_name == "head":
            lines = strategy.get("lines", 20)
            summarized = self._extract_head(content, lines)
        else:  # truncate is the default
            max_lines = strategy.get("max_lines", 50)
            summarized = self.truncate_with_indicator(content, max_lines)

        summarized_tokens = len(summarized) // CHARS_PER_TOKEN
        tokens_saved = max(0, original_tokens - summarized_tokens)

        return summarized, tokens_saved

    def _summarize_structured(self, filepath: str, content: str, max_depth: int) -> str:
        """Summarize structured files (JSON/YAML).

        Args:
            filepath: Path to determine file type
            content: File content
            max_depth: Maximum depth to extract

        Returns:
            Structure summary string
        """
        suffix = Path(filepath).suffix.lower()

        if suffix == ".json":
            return self.extract_json_structure(content, max_depth)
        elif suffix in (".yaml", ".yml"):
            return self._extract_yaml_structure(content, max_depth)
        else:
            return self.truncate_with_indicator(content, 50)

    def extract_json_structure(self, content: str, max_depth: int = 2) -> str:
        """Extract JSON structure showing keys at each level.

        Args:
            content: JSON string
            max_depth: Maximum depth to show (default: 2)

        Returns:
            Human-readable structure representation
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return f"[JSON Parse Error: {e}]\n{self.truncate_with_indicator(content, 20)}"

        lines = ["[JSON Structure]"]
        self._extract_structure_recursive(data, lines, depth=0, max_depth=max_depth)

        return "\n".join(lines)

    def _extract_structure_recursive(
        self,
        data: Any,
        lines: list,
        depth: int,
        max_depth: int,
        prefix: str = "",
    ):
        """Recursively extract structure from nested data.

        Args:
            data: Data to extract from
            lines: List to append lines to
            depth: Current depth
            max_depth: Maximum depth to traverse
            prefix: Indentation prefix
        """
        indent = "  " * depth

        if depth >= max_depth:
            if isinstance(data, dict):
                lines.append(f"{indent}{prefix}{{...}} ({len(data)} keys)")
            elif isinstance(data, list):
                lines.append(f"{indent}{prefix}[...] ({len(data)} items)")
            else:
                # Show truncated value
                value_str = str(data)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                lines.append(f"{indent}{prefix}{value_str}")
            return

        if isinstance(data, dict):
            if prefix:
                lines.append(f"{indent}{prefix}{{")
            for key, value in list(data.items())[:20]:  # Limit to first 20 keys
                key_str = f'"{key}": ' if isinstance(key, str) else f"{key}: "
                self._extract_structure_recursive(
                    value, lines, depth + 1, max_depth, key_str
                )
            if len(data) > 20:
                lines.append(f"{indent}  ... and {len(data) - 20} more keys")
            if prefix:
                lines.append(f"{indent}}}")
        elif isinstance(data, list):
            if prefix:
                lines.append(f"{indent}{prefix}[")
            if len(data) > 0:
                # Show structure of first item
                lines.append(f"{indent}  [0]:")
                self._extract_structure_recursive(
                    data[0], lines, depth + 2, max_depth, ""
                )
                if len(data) > 1:
                    lines.append(f"{indent}  ... ({len(data) - 1} more items)")
            if prefix:
                lines.append(f"{indent}]")
        else:
            # Scalar value
            value_str = str(data)
            if len(value_str) > 80:
                value_str = value_str[:77] + "..."
            lines.append(f"{indent}{prefix}{value_str}")

    def _extract_yaml_structure(self, content: str, max_depth: int) -> str:
        """Extract YAML structure using regex-based heuristics.

        Note: Does not require PyYAML dependency. Uses line-based parsing.

        Args:
            content: YAML string
            max_depth: Maximum indent depth to include

        Returns:
            Structure summary
        """
        lines = ["[YAML Structure]"]
        content_lines = content.split("\n")

        # Track current depth based on indentation
        shown_lines = 0
        max_shown = 50

        for line in content_lines:
            if shown_lines >= max_shown:
                lines.append(f"... ({len(content_lines) - shown_lines} more lines)")
                break

            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue

            # Calculate indent depth (assuming 2-space indent)
            indent = len(line) - len(stripped)
            depth = indent // 2

            if depth <= max_depth:
                # Show the key (up to colon) and indicate if there's a value
                if ":" in stripped:
                    key_part = stripped.split(":")[0]
                    value_part = stripped.split(":", 1)[1].strip() if ":" in stripped else ""

                    if value_part:
                        # Has inline value
                        if len(value_part) > 50:
                            value_part = value_part[:47] + "..."
                        lines.append(f"{'  ' * depth}{key_part}: {value_part}")
                    else:
                        # Nested structure
                        lines.append(f"{'  ' * depth}{key_part}:")
                else:
                    # List item or other
                    if len(stripped) > 60:
                        stripped = stripped[:57] + "..."
                    lines.append(f"{'  ' * depth}{stripped}")

                shown_lines += 1

        return "\n".join(lines)

    def extract_markdown_headings(self, content: str) -> str:
        """Extract Markdown headings and first paragraph under each.

        Args:
            content: Markdown string

        Returns:
            Summary with headings and brief content
        """
        lines = ["[Markdown Summary]"]
        content_lines = content.split("\n")

        i = 0
        while i < len(content_lines):
            line = content_lines[i]

            # Check for heading
            if line.startswith("#"):
                lines.append(line)
                # Try to capture first non-empty paragraph after heading
                i += 1
                paragraph_lines = []
                while i < len(content_lines):
                    next_line = content_lines[i].strip()
                    if next_line.startswith("#"):
                        # Next heading found
                        break
                    elif next_line:
                        paragraph_lines.append(next_line)
                        if len(paragraph_lines) >= 2:  # Max 2 lines per section
                            break
                    elif paragraph_lines:
                        # Empty line after content
                        break
                    i += 1

                if paragraph_lines:
                    summary = " ".join(paragraph_lines)
                    if len(summary) > 150:
                        summary = summary[:147] + "..."
                    lines.append(f"  {summary}")
                    lines.append("")
            else:
                i += 1

        if len(lines) == 1:
            # No headings found, show truncated content
            return self.truncate_with_indicator(content, 30)

        return "\n".join(lines)

    def truncate_with_indicator(self, content: str, max_lines: int) -> str:
        """Truncate content to max lines with clear indicator.

        Args:
            content: Content to truncate
            max_lines: Maximum number of lines to include

        Returns:
            Truncated content with indicator
        """
        lines = content.split("\n")

        if len(lines) <= max_lines:
            return content

        truncated = lines[:max_lines]
        remaining = len(lines) - max_lines

        truncated.append("")
        truncated.append(f"[... {remaining} more lines truncated ...]")

        return "\n".join(truncated)

    def _extract_tail(self, content: str, num_lines: int) -> str:
        """Extract last N lines of content.

        Args:
            content: Content to extract from
            num_lines: Number of lines to show

        Returns:
            Tail content with indicator
        """
        lines = content.split("\n")

        if len(lines) <= num_lines:
            return content

        skipped = len(lines) - num_lines
        result = [f"[... {skipped} lines skipped ...]", ""]
        result.extend(lines[-num_lines:])

        return "\n".join(result)

    def _extract_head(self, content: str, num_lines: int) -> str:
        """Extract first N lines of content.

        Args:
            content: Content to extract from
            num_lines: Number of lines to show

        Returns:
            Head content with indicator
        """
        lines = content.split("\n")

        if len(lines) <= num_lines:
            return content

        result = lines[:num_lines]
        remaining = len(lines) - num_lines
        result.append("")
        result.append(f"[... {remaining} more lines ...]")

        return "\n".join(result)

    def get_read_recommendation(
        self, filepath: str, size_bytes: int
    ) -> Dict[str, Any]:
        """Get a recommendation for how to read a file.

        Provides guidance on whether to read fully, summarize, or skip.

        Args:
            filepath: Path to the file
            size_bytes: Size in bytes

        Returns:
            Dict with 'action', 'strategy', 'reason', and 'estimated_tokens'
        """
        estimated_tokens = size_bytes // CHARS_PER_TOKEN

        # Very small files - always read fully
        if size_bytes < 1000:
            return {
                "action": "read_full",
                "strategy": None,
                "reason": "Small file, minimal token impact",
                "estimated_tokens": estimated_tokens,
            }

        # Check if summarizable
        strategy = self.get_summary_strategy(filepath)

        if strategy and size_bytes >= self.LARGE_FILE_THRESHOLD:
            # Estimate tokens after summarization
            summary_tokens = min(estimated_tokens, 500)  # Rough estimate
            return {
                "action": "summarize",
                "strategy": strategy["strategy"],
                "reason": f"Large {Path(filepath).suffix} file, summarization recommended",
                "estimated_tokens": estimated_tokens,
                "estimated_tokens_after": summary_tokens,
                "tokens_saved": estimated_tokens - summary_tokens,
            }

        # Medium files - read but warn
        if size_bytes >= self.LARGE_FILE_THRESHOLD:
            return {
                "action": "read_full",
                "strategy": None,
                "reason": "Large file but no summarization strategy available",
                "estimated_tokens": estimated_tokens,
                "warning": "Consider if full read is necessary",
            }

        # Default: read fully
        return {
            "action": "read_full",
            "strategy": None,
            "reason": "Standard file size",
            "estimated_tokens": estimated_tokens,
        }


def get_file_read_optimizer() -> FileReadOptimizer:
    """Get a FileReadOptimizer instance."""
    return FileReadOptimizer()
