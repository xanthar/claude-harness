"""Smart file filtering to reduce context tracking noise.

This module provides intelligent file filtering capabilities to exclude
files that should not count toward token limits during Claude Code sessions.
It helps optimize context usage by filtering out:
- Version control metadata
- Dependencies and virtual environments
- Build artifacts and caches
- IDE configuration
- Temporary and binary files
"""

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple

__all__ = ["FileFilter", "FilterResult"]


@dataclass
class FilterResult:
    """Result of filtering a list of files.

    Attributes:
        tracked: Files that should be tracked for context.
        skipped: Files that were filtered out.
        skip_reasons: Mapping of skipped files to their skip reasons.
        tokens_saved_estimate: Estimated tokens saved by filtering.
    """

    tracked: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    skip_reasons: dict = field(default_factory=dict)
    tokens_saved_estimate: int = 0


class FileFilter:
    """Intelligent file filtering to reduce context tracking.

    This class provides configurable file filtering based on patterns
    that match files and directories that should never count toward
    context token limits.

    Example:
        >>> filter = FileFilter()
        >>> filter.should_track_file("src/app.py")
        True
        >>> filter.should_track_file("node_modules/lodash/index.js")
        False
        >>> filter.get_skip_reason(".git/objects/abc123")
        "Version control (.git/)"
    """

    # Patterns that should NEVER count toward token limit
    ALWAYS_SKIP: Set[str] = {
        # Version control
        ".git/",
        ".git",
        ".github/",
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
        ".hg/",
        ".svn/",
        # Dependencies
        "node_modules/",
        "venv/",
        ".venv/",
        "vendor/",
        "site-packages/",
        "packages/",
        ".npm/",
        ".yarn/",
        ".pnpm/",
        "bower_components/",
        # Python caches
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".tox/",
        ".nox/",
        ".coverage",
        "htmlcov/",
        ".hypothesis/",
        # Build artifacts
        "dist/",
        "build/",
        ".egg-info/",
        "target/",
        "out/",
        "bin/",
        "obj/",
        "*.egg",
        # IDE and editor
        ".vscode/",
        ".idea/",
        ".DS_Store",
        "Thumbs.db",
        ".project",
        ".classpath",
        ".settings/",
        "*.sublime-*",
        ".atom/",
        # Temporary
        ".tmp/",
        "tmp/",
        "temp/",
        "*.swp",
        "*.swo",
        "*.swn",
        "*.bak",
        "*.orig",
        "*.log",
        "*~",
        # Binary and compiled
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.o",
        "*.obj",
        "*.so",
        "*.dylib",
        "*.dll",
        "*.exe",
        "*.class",
        "*.jar",
        "*.war",
        # Images and media
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.gif",
        "*.ico",
        "*.svg",
        "*.bmp",
        "*.tiff",
        "*.webp",
        "*.mp3",
        "*.mp4",
        "*.wav",
        "*.avi",
        "*.mov",
        "*.pdf",
        # Compiled/minified web assets
        "*.min.js",
        "*.min.css",
        "*.map",
        "*.bundle.js",
        "*.chunk.js",
        # Lock files (large, auto-generated)
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Cargo.lock",
        "composer.lock",
        "Gemfile.lock",
        # Databases and data
        "*.sqlite",
        "*.sqlite3",
        "*.db",
        "*.mdb",
        # Archives
        "*.zip",
        "*.tar",
        "*.tar.gz",
        "*.tgz",
        "*.rar",
        "*.7z",
        # Fonts
        "*.woff",
        "*.woff2",
        "*.ttf",
        "*.eot",
        "*.otf",
    }

    # Category mapping for skip reasons
    CATEGORY_MAP = {
        "version_control": [".git", ".github/", ".gitignore", ".gitattributes",
                           ".gitmodules", ".hg/", ".svn/"],
        "dependencies": ["node_modules/", "venv/", ".venv/", "vendor/",
                        "site-packages/", "packages/", ".npm/", ".yarn/",
                        ".pnpm/", "bower_components/"],
        "python_cache": ["__pycache__/", ".pytest_cache/", ".mypy_cache/",
                        ".ruff_cache/", ".tox/", ".nox/", ".coverage",
                        "htmlcov/", ".hypothesis/"],
        "build_artifacts": ["dist/", "build/", ".egg-info/", "target/",
                           "out/", "bin/", "obj/", "*.egg"],
        "ide_config": [".vscode/", ".idea/", ".DS_Store", "Thumbs.db",
                      ".project", ".classpath", ".settings/", "*.sublime-*",
                      ".atom/"],
        "temporary": [".tmp/", "tmp/", "temp/", "*.swp", "*.swo", "*.swn",
                     "*.bak", "*.orig", "*.log", "*~"],
        "binary": ["*.pyc", "*.pyo", "*.pyd", "*.o", "*.obj", "*.so",
                  "*.dylib", "*.dll", "*.exe", "*.class", "*.jar", "*.war"],
        "media": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.svg",
                 "*.bmp", "*.tiff", "*.webp", "*.mp3", "*.mp4", "*.wav",
                 "*.avi", "*.mov", "*.pdf"],
        "minified": ["*.min.js", "*.min.css", "*.map", "*.bundle.js",
                    "*.chunk.js"],
        "lock_files": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                      "Pipfile.lock", "poetry.lock", "Cargo.lock",
                      "composer.lock", "Gemfile.lock"],
        "data_files": ["*.sqlite", "*.sqlite3", "*.db", "*.mdb"],
        "archives": ["*.zip", "*.tar", "*.tar.gz", "*.tgz", "*.rar", "*.7z"],
        "fonts": ["*.woff", "*.woff2", "*.ttf", "*.eot", "*.otf"],
    }

    # Human-readable category names
    CATEGORY_NAMES = {
        "version_control": "Version control",
        "dependencies": "Dependencies",
        "python_cache": "Python cache",
        "build_artifacts": "Build artifacts",
        "ide_config": "IDE configuration",
        "temporary": "Temporary files",
        "binary": "Binary files",
        "media": "Media files",
        "minified": "Minified assets",
        "lock_files": "Lock files",
        "data_files": "Data files",
        "archives": "Archives",
        "fonts": "Font files",
    }

    # Average tokens per character for estimation
    TOKENS_PER_CHAR = 0.25

    def __init__(
        self,
        custom_excludes: Optional[List[str]] = None,
        custom_includes: Optional[List[str]] = None,
        enabled: bool = True,
    ):
        """Initialize the file filter.

        Args:
            custom_excludes: Additional patterns to exclude.
            custom_includes: Patterns to include even if they match exclusions.
            enabled: Whether filtering is enabled. If False, all files pass.
        """
        self.enabled = enabled
        self.custom_excludes: Set[str] = set(custom_excludes or [])
        self.custom_includes: Set[str] = set(custom_includes or [])
        self._all_excludes = self.ALWAYS_SKIP | self.custom_excludes

    def should_track_file(
        self,
        filepath: str,
        custom_excludes: Optional[List[str]] = None,
    ) -> bool:
        """Determine if a file should be tracked for context.

        Args:
            filepath: Path to the file (relative or absolute).
            custom_excludes: Additional patterns to exclude for this check.

        Returns:
            True if the file should be tracked, False if it should be skipped.

        Example:
            >>> filter = FileFilter()
            >>> filter.should_track_file("src/main.py")
            True
            >>> filter.should_track_file("node_modules/express/index.js")
            False
        """
        if not self.enabled:
            return True

        # Check custom includes first (whitelist)
        if self._matches_any_pattern(filepath, self.custom_includes):
            return True

        # Build exclusion set
        excludes = self._all_excludes
        if custom_excludes:
            excludes = excludes | set(custom_excludes)

        return not self._matches_any_pattern(filepath, excludes)

    def get_skip_reason(self, filepath: str) -> Optional[str]:
        """Get the reason why a file would be skipped.

        Args:
            filepath: Path to the file.

        Returns:
            Human-readable skip reason, or None if file would be tracked.

        Example:
            >>> filter = FileFilter()
            >>> filter.get_skip_reason(".git/config")
            "Version control (.git/)"
            >>> filter.get_skip_reason("src/app.py")
            None
        """
        if not self.enabled:
            return None

        # Check custom includes first
        if self._matches_any_pattern(filepath, self.custom_includes):
            return None

        # Find matching pattern and its category
        for category, patterns in self.CATEGORY_MAP.items():
            for pattern in patterns:
                if self._matches_pattern(filepath, pattern):
                    category_name = self.CATEGORY_NAMES.get(category, category)
                    return f"{category_name} ({pattern})"

        # Check custom excludes
        for pattern in self.custom_excludes:
            if self._matches_pattern(filepath, pattern):
                return f"Custom exclude ({pattern})"

        return None

    def filter_file_list(
        self,
        filepaths: List[str],
        custom_excludes: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        """Filter a list of files into tracked and skipped.

        Args:
            filepaths: List of file paths to filter.
            custom_excludes: Additional patterns to exclude.

        Returns:
            Tuple of (tracked_files, skipped_files).

        Example:
            >>> filter = FileFilter()
            >>> tracked, skipped = filter.filter_file_list([
            ...     "src/app.py",
            ...     "node_modules/lodash/index.js",
            ...     "__pycache__/app.cpython-311.pyc"
            ... ])
            >>> tracked
            ['src/app.py']
            >>> len(skipped)
            2
        """
        tracked = []
        skipped = []

        for filepath in filepaths:
            if self.should_track_file(filepath, custom_excludes):
                tracked.append(filepath)
            else:
                skipped.append(filepath)

        return tracked, skipped

    def filter_with_details(
        self,
        filepaths: List[str],
        custom_excludes: Optional[List[str]] = None,
    ) -> FilterResult:
        """Filter files and return detailed results.

        Args:
            filepaths: List of file paths to filter.
            custom_excludes: Additional patterns to exclude.

        Returns:
            FilterResult with tracked files, skipped files, reasons, and estimates.
        """
        result = FilterResult()

        for filepath in filepaths:
            if self.should_track_file(filepath, custom_excludes):
                result.tracked.append(filepath)
            else:
                result.skipped.append(filepath)
                reason = self.get_skip_reason(filepath)
                if reason:
                    result.skip_reasons[filepath] = reason

        result.tokens_saved_estimate = self.estimate_savings(result.skipped)
        return result

    def estimate_savings(
        self,
        skipped_files: List[str],
        base_path: Optional[str] = None,
    ) -> int:
        """Estimate tokens saved by skipping files.

        This provides a rough estimate based on average file sizes for
        different file types. Actual savings may vary.

        Args:
            skipped_files: List of skipped file paths.
            base_path: Base path to resolve relative paths for size checking.

        Returns:
            Estimated number of tokens saved.

        Example:
            >>> filter = FileFilter()
            >>> filter.estimate_savings(["package-lock.json", "node_modules/x.js"])
            1250  # Rough estimate
        """
        # Size estimates per pattern (in characters)
        SIZE_ESTIMATES = {
            "package-lock.json": 50000,
            "yarn.lock": 30000,
            "pnpm-lock.yaml": 30000,
            "poetry.lock": 20000,
            "Pipfile.lock": 10000,
            "Cargo.lock": 15000,
            "node_modules/": 5000,  # Per file
            "__pycache__/": 2000,
            ".git/": 1000,
            "*.min.js": 10000,
            "*.min.css": 5000,
            "*.map": 20000,
        }

        total_chars = 0

        for filepath in skipped_files:
            # Try to get actual size if base_path provided
            if base_path:
                full_path = Path(base_path) / filepath
                if full_path.exists() and full_path.is_file():
                    try:
                        total_chars += full_path.stat().st_size
                        continue
                    except (OSError, IOError):
                        pass

            # Fall back to estimates
            estimated = False
            for pattern, size in SIZE_ESTIMATES.items():
                if self._matches_pattern(filepath, pattern):
                    total_chars += size
                    estimated = True
                    break

            if not estimated:
                # Default estimate for unknown files
                total_chars += 1000

        return int(total_chars * self.TOKENS_PER_CHAR)

    def add_exclude(self, pattern: str) -> None:
        """Add a pattern to the exclusion list.

        Args:
            pattern: Glob pattern to exclude.
        """
        self.custom_excludes.add(pattern)
        self._all_excludes = self.ALWAYS_SKIP | self.custom_excludes

    def add_include(self, pattern: str) -> None:
        """Add a pattern to the inclusion whitelist.

        Args:
            pattern: Glob pattern to always include.
        """
        self.custom_includes.add(pattern)

    def remove_exclude(self, pattern: str) -> None:
        """Remove a pattern from custom exclusions.

        Args:
            pattern: Pattern to remove.
        """
        self.custom_excludes.discard(pattern)
        self._all_excludes = self.ALWAYS_SKIP | self.custom_excludes

    def _matches_pattern(self, filepath: str, pattern: str) -> bool:
        """Check if a filepath matches a single pattern.

        Handles both glob patterns and directory prefix patterns.
        """
        # Normalize path separators
        filepath = filepath.replace("\\", "/")
        pattern = pattern.replace("\\", "/")

        # Directory pattern (ends with /)
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            # Check if directory appears anywhere in path
            parts = filepath.split("/")
            return dir_name in parts or filepath.startswith(pattern)

        # Exact filename match
        filename = os.path.basename(filepath)
        if pattern == filename:
            return True

        # Glob pattern
        if fnmatch.fnmatch(filepath, pattern):
            return True
        if fnmatch.fnmatch(filename, pattern):
            return True

        # Path contains pattern
        if f"/{pattern}/" in f"/{filepath}/":
            return True

        return False

    def _matches_any_pattern(self, filepath: str, patterns: Set[str]) -> bool:
        """Check if a filepath matches any pattern in the set."""
        for pattern in patterns:
            if self._matches_pattern(filepath, pattern):
                return True
        return False

    def get_statistics(self) -> dict:
        """Get filter configuration statistics.

        Returns:
            Dictionary with filter statistics.
        """
        return {
            "enabled": self.enabled,
            "builtin_patterns": len(self.ALWAYS_SKIP),
            "custom_excludes": len(self.custom_excludes),
            "custom_includes": len(self.custom_includes),
            "total_excludes": len(self._all_excludes),
            "categories": list(self.CATEGORY_NAMES.keys()),
        }
