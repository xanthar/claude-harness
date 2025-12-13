"""Output helper for Claude Harness.

Provides configurable output control to reduce terminal scrolling issues:
- Truncate long outputs
- Limit file lists
- Compact mode
"""

import json
from pathlib import Path
from typing import List, Optional, Any
from dataclasses import dataclass


@dataclass
class OutputConfig:
    """Output configuration options."""

    compact_mode: bool = False
    max_lines: int = 50  # 0 = unlimited
    max_files_shown: int = 20
    truncate_long_values: bool = True
    value_max_length: int = 80  # Max length for truncated values


def load_output_config(project_path: str) -> OutputConfig:
    """Load output configuration from project config.

    Args:
        project_path: Path to project root.

    Returns:
        OutputConfig with settings from config.json or defaults.
    """
    config_file = Path(project_path) / ".claude-harness" / "config.json"

    if config_file.exists():
        try:
            with open(config_file) as f:
                data = json.load(f)
            output_config = data.get("output", {})
            return OutputConfig(
                compact_mode=output_config.get("compact_mode", False),
                max_lines=output_config.get("max_lines", 50),
                max_files_shown=output_config.get("max_files_shown", 20),
                truncate_long_values=output_config.get("truncate_long_values", True),
            )
        except (json.JSONDecodeError, IOError):
            pass

    return OutputConfig()


def truncate_text(text: str, max_length: int = 80, suffix: str = "...") -> str:
    """Truncate text to max length with suffix.

    Args:
        text: Text to truncate.
        max_length: Maximum length including suffix.
        suffix: Suffix to add when truncated.

    Returns:
        Truncated text or original if within limit.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def truncate_list(
    items: List[Any],
    max_items: int,
    format_item: Optional[callable] = None,
    summary_format: str = "... and {count} more",
) -> List[str]:
    """Truncate a list with a summary of remaining items.

    Args:
        items: List of items to truncate.
        max_items: Maximum items to show.
        format_item: Optional function to format each item.
        summary_format: Format string for remaining count.

    Returns:
        List of formatted strings, possibly truncated with summary.
    """
    if not items:
        return []

    formatter = format_item or str

    if len(items) <= max_items:
        return [formatter(item) for item in items]

    result = [formatter(item) for item in items[:max_items]]
    remaining = len(items) - max_items
    result.append(summary_format.format(count=remaining))
    return result


def truncate_output(
    lines: List[str], max_lines: int, show_truncation: bool = True
) -> List[str]:
    """Truncate multi-line output.

    Args:
        lines: Lines of output.
        max_lines: Maximum lines to show (0 = unlimited).
        show_truncation: Whether to add truncation indicator.

    Returns:
        Truncated lines with optional indicator.
    """
    if max_lines <= 0 or len(lines) <= max_lines:
        return lines

    result = lines[:max_lines]
    if show_truncation:
        remaining = len(lines) - max_lines
        result.append(f"... ({remaining} more lines)")
    return result


def format_file_list(
    files: List[str],
    config: OutputConfig,
    show_full_path: bool = False,
) -> List[str]:
    """Format a list of files with truncation.

    Args:
        files: List of file paths.
        config: Output configuration.
        show_full_path: Whether to show full path or just filename.

    Returns:
        Formatted list of files.
    """
    if not files:
        return ["(none)"]

    def format_file(filepath: str) -> str:
        if show_full_path:
            return truncate_text(filepath, config.value_max_length)
        else:
            name = Path(filepath).name
            return truncate_text(name, config.value_max_length)

    return truncate_list(
        files,
        config.max_files_shown,
        format_file,
        summary_format="... and {count} more files",
    )


def format_table_value(value: Any, config: OutputConfig) -> str:
    """Format a value for table display with optional truncation.

    Args:
        value: Value to format.
        config: Output configuration.

    Returns:
        Formatted string value.
    """
    text = str(value)
    if config.truncate_long_values:
        return truncate_text(text, config.value_max_length)
    return text


class OutputHelper:
    """Helper class for controlled output."""

    def __init__(self, project_path: str = "."):
        """Initialize with project path.

        Args:
            project_path: Path to project root.
        """
        self.project_path = project_path
        self.config = load_output_config(project_path)

    def truncate_lines(self, lines: List[str]) -> List[str]:
        """Truncate lines based on config."""
        return truncate_output(lines, self.config.max_lines)

    def truncate_value(self, value: Any) -> str:
        """Truncate a value based on config."""
        return format_table_value(value, self.config)

    def format_files(self, files: List[str], full_path: bool = False) -> List[str]:
        """Format file list based on config."""
        return format_file_list(files, self.config, full_path)

    def is_compact(self) -> bool:
        """Check if compact mode is enabled."""
        return self.config.compact_mode


def get_output_helper(project_path: str = ".") -> OutputHelper:
    """Get an output helper instance.

    Args:
        project_path: Path to project root.

    Returns:
        OutputHelper instance.
    """
    return OutputHelper(project_path)
