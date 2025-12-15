"""Claude Harness - AI Workflow Optimization Tool.

A comprehensive harness for optimizing Claude Code sessions with:
- Session continuity (progress tracking between sessions)
- Feature/task management (one feature at a time)
- Automated startup rituals (init.sh)
- Git safety hooks (prevent dangerous operations)
- E2E testing with Playwright
- Lazy context loading (defer non-critical files)
- Exploration caching (avoid re-reading files)
- Smart file filtering (reduce context noise)
- Output compression (compress verbose command outputs)
"""

__version__ = "1.2.0"
__author__ = "Morten Elmstroem Hansen"

# Lazy imports for optional modules
from .lazy_loader import (
    LazyContextLoader,
    FilePriority,
    PrioritizedFile,
    get_lazy_loader,
)
from .exploration_cache import (
    ExplorationCache,
    CachedExploration,
    get_exploration_cache,
)
from .file_filter import (
    FileFilter,
    FilterResult,
)
from .output_compressor import (
    OutputCompressor,
    CompressionRule,
    CompressionResult,
)

__all__ = [
    # Lazy loading
    "LazyContextLoader",
    "FilePriority",
    "PrioritizedFile",
    "get_lazy_loader",
    # Exploration cache
    "ExplorationCache",
    "CachedExploration",
    "get_exploration_cache",
    # File filtering
    "FileFilter",
    "FilterResult",
    # Output compression
    "OutputCompressor",
    "CompressionRule",
    "CompressionResult",
]
