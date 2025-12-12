"""Lazy context loader for Claude Harness.

Defers loading non-critical context until needed to optimize token usage:
- Prioritizes files based on patterns and task type
- Estimates token savings from deferral
- Generates notes about deferred files for context awareness
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


class FilePriority(Enum):
    """Priority levels for file loading."""

    CRITICAL = 1  # Must load immediately (main files, entry points)
    IMPORTANT = 2  # Load soon (models, services, routes)
    REFERENCE = 3  # Can defer (docs, examples, tests for non-test tasks)
    SKIP = 4  # Don't load unless explicitly requested


@dataclass
class PrioritizedFile:
    """A file with its determined priority."""

    filepath: str
    priority: FilePriority
    reason: str
    estimated_tokens: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "filepath": self.filepath,
            "priority": self.priority.name,
            "reason": self.reason,
            "estimated_tokens": self.estimated_tokens,
        }


# Approximate characters per token for estimation
CHARS_PER_TOKEN = 4
CODE_CHARS_PER_TOKEN = 3.5


class LazyContextLoader:
    """Load context on-demand based on priority.

    This class helps optimize token usage by categorizing files into
    priority levels and allowing selective loading based on task type.
    """

    # Patterns for priority classification
    CRITICAL_PATTERNS = [
        "main.",
        "app.",
        "__init__.py",
        "index.",
        "setup.py",
        "cli.py",
        "wsgi.py",
        "asgi.py",
    ]
    IMPORTANT_PATTERNS = [
        "model",
        "service",
        "route",
        "api",
        "config",
        "util",
        "helper",
        "handler",
        "controller",
        "view",
        "schema",
        "serializer",
    ]
    REFERENCE_PATTERNS = [
        "readme",
        "doc",
        "example",
        "sample",
        "demo",
        "tutorial",
        "guide",
        "changelog",
        "contributing",
        "license",
    ]
    SKIP_PATTERNS = [
        "test_",
        "_test.",
        ".spec.",
        "mock",
        "fixture",
        "conftest",
        "__pycache__",
        ".pyc",
        "node_modules",
        ".git",
        "venv",
        ".venv",
        "dist",
        "build",
        ".egg-info",
    ]

    # Task types that modify skip behavior
    TEST_TASK_TYPES = ["test", "testing", "unit_test", "e2e", "coverage"]
    DOC_TASK_TYPES = ["docs", "documentation", "readme", "api_docs"]

    def __init__(self, project_path: Optional[str] = None):
        """Initialize loader with optional project path.

        Args:
            project_path: Base path for relative file resolution.
                         If None, uses current working directory.
        """
        self.project_path = Path(project_path).resolve() if project_path else Path.cwd()

    def _estimate_file_tokens(self, filepath: str) -> int:
        """Estimate token count for a file.

        Args:
            filepath: Path to the file.

        Returns:
            Estimated token count based on file size and type.
        """
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = self.project_path / path

            if not path.exists():
                return 0

            size = path.stat().st_size
            # Use code-specific ratio for source files
            code_extensions = {
                ".py",
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
                ".go",
                ".rs",
                ".java",
                ".c",
                ".cpp",
                ".h",
                ".hpp",
                ".cs",
                ".rb",
                ".php",
                ".swift",
                ".kt",
                ".scala",
                ".sh",
                ".bash",
                ".ps1",
                ".sql",
            }

            if path.suffix.lower() in code_extensions:
                return int(size / CODE_CHARS_PER_TOKEN)
            return int(size / CHARS_PER_TOKEN)
        except (OSError, IOError):
            return 0

    def _match_patterns(self, filename: str, patterns: List[str]) -> bool:
        """Check if filename matches any pattern.

        Args:
            filename: The filename to check (lowercase).
            patterns: List of patterns to match against.

        Returns:
            True if any pattern matches.
        """
        filename_lower = filename.lower()
        for pattern in patterns:
            if pattern.lower() in filename_lower:
                return True
        return False

    def _classify_file(
        self, filepath: str, task_type: Optional[str] = None
    ) -> tuple[FilePriority, str]:
        """Classify a file into a priority level.

        Args:
            filepath: Path to the file.
            task_type: Optional task type to influence classification.

        Returns:
            Tuple of (priority, reason).
        """
        path = Path(filepath)
        filename = path.name
        filepath_lower = filepath.lower()

        # Check SKIP patterns first (unless task-specific override)
        if task_type and task_type.lower() in self.TEST_TASK_TYPES:
            # For test tasks, don't skip test files
            skip_patterns = [
                p for p in self.SKIP_PATTERNS if p not in ["test_", "_test.", ".spec."]
            ]
        else:
            skip_patterns = self.SKIP_PATTERNS

        for pattern in skip_patterns:
            if pattern.lower() in filepath_lower:
                return (
                    FilePriority.SKIP,
                    f"Matches skip pattern: {pattern}",
                )

        # Check CRITICAL patterns
        if self._match_patterns(filename, self.CRITICAL_PATTERNS):
            return (
                FilePriority.CRITICAL,
                f"Entry point or critical file: {filename}",
            )

        # Check IMPORTANT patterns
        if self._match_patterns(filename, self.IMPORTANT_PATTERNS):
            return (
                FilePriority.IMPORTANT,
                f"Core application file: {filename}",
            )

        # Check REFERENCE patterns
        if self._match_patterns(filename, self.REFERENCE_PATTERNS):
            # For doc tasks, elevate reference files to important
            if task_type and task_type.lower() in self.DOC_TASK_TYPES:
                return (
                    FilePriority.IMPORTANT,
                    f"Documentation file (elevated for doc task): {filename}",
                )
            return (
                FilePriority.REFERENCE,
                f"Reference/documentation file: {filename}",
            )

        # Test files when not doing test tasks
        if self._match_patterns(filename, ["test_", "_test.", ".spec."]):
            if task_type and task_type.lower() in self.TEST_TASK_TYPES:
                return (
                    FilePriority.IMPORTANT,
                    f"Test file (elevated for test task): {filename}",
                )
            return (
                FilePriority.REFERENCE,
                f"Test file (deferred for non-test task): {filename}",
            )

        # Default to IMPORTANT for source files
        source_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".go",
            ".rs",
            ".java",
        }
        if path.suffix.lower() in source_extensions:
            return (
                FilePriority.IMPORTANT,
                f"Source file: {filename}",
            )

        # Default to REFERENCE for other files
        return (
            FilePriority.REFERENCE,
            f"Other file: {filename}",
        )

    def prioritize_files(
        self, filepaths: List[str], task_type: Optional[str] = None
    ) -> List[PrioritizedFile]:
        """Prioritize a list of files for loading.

        Args:
            filepaths: List of file paths to prioritize.
            task_type: Optional task type to influence prioritization
                      (e.g., 'test', 'docs', 'feature').

        Returns:
            List of PrioritizedFile objects sorted by priority (CRITICAL first).
        """
        prioritized = []

        for filepath in filepaths:
            priority, reason = self._classify_file(filepath, task_type)
            estimated_tokens = self._estimate_file_tokens(filepath)

            prioritized.append(
                PrioritizedFile(
                    filepath=filepath,
                    priority=priority,
                    reason=reason,
                    estimated_tokens=estimated_tokens,
                )
            )

        # Sort by priority value (lower = higher priority)
        return sorted(prioritized, key=lambda pf: pf.priority.value)

    def get_deferred_files(self, prioritized: List[PrioritizedFile]) -> List[str]:
        """Get files that can be deferred (REFERENCE and SKIP priority).

        Args:
            prioritized: List of prioritized files.

        Returns:
            List of file paths that can be deferred.
        """
        return [
            pf.filepath
            for pf in prioritized
            if pf.priority in (FilePriority.REFERENCE, FilePriority.SKIP)
        ]

    def get_immediate_files(self, prioritized: List[PrioritizedFile]) -> List[str]:
        """Get files that should be loaded immediately (CRITICAL and IMPORTANT).

        Args:
            prioritized: List of prioritized files.

        Returns:
            List of file paths that should be loaded immediately.
        """
        return [
            pf.filepath
            for pf in prioritized
            if pf.priority in (FilePriority.CRITICAL, FilePriority.IMPORTANT)
        ]

    def estimate_deferred_savings(self, deferred: List[str]) -> int:
        """Estimate token savings from deferring files.

        Args:
            deferred: List of file paths being deferred.

        Returns:
            Estimated tokens saved by not loading these files.
        """
        return sum(self._estimate_file_tokens(fp) for fp in deferred)

    def generate_deferral_note(self, deferred: List[str]) -> str:
        """Generate a note about deferred files for context awareness.

        This note can be included in the context to inform Claude about
        files that are available but not loaded.

        Args:
            deferred: List of deferred file paths.

        Returns:
            Formatted note about deferred files.
        """
        if not deferred:
            return ""

        total_tokens = self.estimate_deferred_savings(deferred)

        lines = [
            "---",
            "**Deferred Context Files**",
            f"The following {len(deferred)} files are available but not loaded (~{total_tokens:,} tokens saved):",
            "",
        ]

        # Group by directory for cleaner output
        by_dir: dict[str, List[str]] = {}
        for fp in deferred:
            path = Path(fp)
            dir_name = str(path.parent) if path.parent != Path(".") else "(root)"
            if dir_name not in by_dir:
                by_dir[dir_name] = []
            by_dir[dir_name].append(path.name)

        for dir_name, files in sorted(by_dir.items()):
            lines.append(f"- `{dir_name}/`: {', '.join(sorted(files)[:5])}")
            if len(files) > 5:
                lines.append(f"  ... and {len(files) - 5} more")

        lines.append("")
        lines.append("*Request specific files if needed for current task.*")
        lines.append("---")

        return "\n".join(lines)

    def should_load_now(
        self, filepath: str, task_type: Optional[str] = None
    ) -> bool:
        """Check if a file should be loaded immediately.

        Args:
            filepath: Path to the file.
            task_type: Optional task type to influence decision.

        Returns:
            True if file should be loaded immediately.
        """
        priority, _ = self._classify_file(filepath, task_type)
        return priority in (FilePriority.CRITICAL, FilePriority.IMPORTANT)

    def get_loading_plan(
        self, filepaths: List[str], task_type: Optional[str] = None
    ) -> dict:
        """Get a complete loading plan for a set of files.

        Args:
            filepaths: List of file paths to plan.
            task_type: Optional task type to influence planning.

        Returns:
            Dictionary with loading plan details:
            - immediate: Files to load now
            - deferred: Files to defer
            - skipped: Files to skip entirely
            - tokens_immediate: Estimated tokens for immediate files
            - tokens_saved: Estimated tokens saved by deferral/skip
            - deferral_note: Note about deferred files
        """
        prioritized = self.prioritize_files(filepaths, task_type)

        immediate = []
        deferred = []
        skipped = []

        for pf in prioritized:
            if pf.priority in (FilePriority.CRITICAL, FilePriority.IMPORTANT):
                immediate.append(pf)
            elif pf.priority == FilePriority.REFERENCE:
                deferred.append(pf)
            else:
                skipped.append(pf)

        tokens_immediate = sum(pf.estimated_tokens for pf in immediate)
        tokens_deferred = sum(pf.estimated_tokens for pf in deferred)
        tokens_skipped = sum(pf.estimated_tokens for pf in skipped)

        deferred_paths = [pf.filepath for pf in deferred]

        return {
            "immediate": [pf.to_dict() for pf in immediate],
            "deferred": [pf.to_dict() for pf in deferred],
            "skipped": [pf.to_dict() for pf in skipped],
            "tokens_immediate": tokens_immediate,
            "tokens_saved": tokens_deferred + tokens_skipped,
            "deferral_note": self.generate_deferral_note(deferred_paths),
            "summary": {
                "total_files": len(filepaths),
                "immediate_count": len(immediate),
                "deferred_count": len(deferred),
                "skipped_count": len(skipped),
            },
        }


def get_lazy_loader(project_path: Optional[str] = None) -> LazyContextLoader:
    """Get a lazy context loader instance.

    Args:
        project_path: Optional project path. Defaults to current directory.

    Returns:
        LazyContextLoader instance.
    """
    return LazyContextLoader(project_path)
