"""Discoveries tracking for Claude Harness.

Tracks arbitrary findings, new requirements, and special applications
discovered during development sessions. This helps preserve institutional
knowledge that would otherwise be lost across sessions.

Examples of discoveries:
- "Need to use X-API-Key header for all authenticated requests"
- "Database migrations require running flask db upgrade before tests"
- "The XYZ service requires a specific initialization order"
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@dataclass
class Discovery:
    """A single discovery/finding."""

    id: str
    timestamp: str
    summary: str  # Brief description
    context: str = ""  # What was happening when discovered
    details: str = ""  # Detailed explanation
    impact: str = ""  # What this affects
    tags: List[str] = field(default_factory=list)
    related_feature: str = ""  # Feature ID if related to a feature
    source: str = "manual"  # manual, auto-detected, imported

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "context": self.context,
            "details": self.details,
            "impact": self.impact,
            "tags": self.tags,
            "related_feature": self.related_feature,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Discovery":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            timestamp=data.get("timestamp", ""),
            summary=data.get("summary", ""),
            context=data.get("context", ""),
            details=data.get("details", ""),
            impact=data.get("impact", ""),
            tags=data.get("tags", []),
            related_feature=data.get("related_feature", ""),
            source=data.get("source", "manual"),
        )


class DiscoveryTracker:
    """Track and manage discoveries across sessions."""

    def __init__(self, project_path: str):
        """Initialize with project path.

        Args:
            project_path: Path to project root.
        """
        self.project_path = Path(project_path).resolve()
        self.harness_dir = self.project_path / ".claude-harness"
        self.discoveries_file = self.harness_dir / "discoveries.json"
        self.config_file = self.harness_dir / "config.json"
        self._data: Optional[Dict[str, Any]] = None

    def _load_config_enabled(self) -> bool:
        """Load enabled state from config.json."""
        if not self.config_file.exists():
            return False

        try:
            with open(self.config_file) as f:
                data = json.load(f)
            return data.get("discoveries", {}).get("enabled", False)
        except (json.JSONDecodeError, IOError):
            return False

    def _save_config_enabled(self, enabled: bool):
        """Save enabled state to config.json."""
        self.harness_dir.mkdir(parents=True, exist_ok=True)

        if self.config_file.exists():
            with open(self.config_file) as f:
                data = json.load(f)
        else:
            data = {}

        if "discoveries" not in data:
            data["discoveries"] = {}
        data["discoveries"]["enabled"] = enabled

        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def is_enabled(self) -> bool:
        """Check if discoveries tracking is enabled."""
        return self._load_config_enabled()

    def enable(self):
        """Enable discoveries tracking."""
        self._save_config_enabled(True)

    def disable(self):
        """Disable discoveries tracking."""
        self._save_config_enabled(False)

    def _load_data(self) -> Dict[str, Any]:
        """Load discoveries from file."""
        if self._data is not None:
            return self._data

        if self.discoveries_file.exists():
            try:
                with open(self.discoveries_file) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = self._create_default_data()
        else:
            self._data = self._create_default_data()

        return self._data

    def _create_default_data(self) -> Dict[str, Any]:
        """Create default discoveries data structure."""
        return {
            "version": "1.0",
            "discoveries": [],
            "auto_detection": {
                "enabled": True,
                "patterns": [
                    {"pattern": "need to", "category": "requirement"},
                    {"pattern": "must be", "category": "constraint"},
                    {"pattern": "important:", "category": "note"},
                    {"pattern": "discovered that", "category": "finding"},
                    {"pattern": "turns out", "category": "finding"},
                ],
            },
        }

    def _save_data(self):
        """Save discoveries to file."""
        if self._data is None:
            return

        self.discoveries_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.discoveries_file, "w") as f:
            json.dump(self._data, f, indent=2)

    def _generate_id(self) -> str:
        """Generate a unique discovery ID."""
        data = self._load_data()
        discoveries = data.get("discoveries", [])

        # Find highest existing ID number
        max_num = 0
        for d in discoveries:
            if d.get("id", "").startswith("D"):
                try:
                    num = int(d["id"][1:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass

        return f"D{max_num + 1:03d}"

    def add_discovery(
        self,
        summary: str,
        context: str = "",
        details: str = "",
        impact: str = "",
        tags: List[str] = None,
        related_feature: str = "",
        source: str = "manual",
    ) -> Discovery:
        """Add a new discovery.

        Args:
            summary: Brief description of the discovery.
            context: What was happening when discovered.
            details: Detailed explanation.
            impact: What this affects.
            tags: Tags for categorization.
            related_feature: Feature ID if related.
            source: Source of discovery (manual, auto-detected, imported).

        Returns:
            The created Discovery object.
        """
        data = self._load_data()

        discovery = Discovery(
            id=self._generate_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            context=context,
            details=details,
            impact=impact,
            tags=tags or [],
            related_feature=related_feature,
            source=source,
        )

        data["discoveries"].append(discovery.to_dict())
        self._save_data()

        return discovery

    def get_discovery(self, discovery_id: str) -> Optional[Discovery]:
        """Get a discovery by ID.

        Args:
            discovery_id: The discovery ID.

        Returns:
            Discovery object or None if not found.
        """
        data = self._load_data()
        for d in data.get("discoveries", []):
            if d.get("id") == discovery_id:
                return Discovery.from_dict(d)
        return None

    def list_discoveries(
        self,
        tag: str = None,
        feature: str = None,
        limit: int = 0,
    ) -> List[Discovery]:
        """List discoveries with optional filtering.

        Args:
            tag: Filter by tag.
            feature: Filter by related feature.
            limit: Maximum number to return (0 = all).

        Returns:
            List of Discovery objects.
        """
        data = self._load_data()
        discoveries = []

        for d in data.get("discoveries", []):
            discovery = Discovery.from_dict(d)

            # Apply filters
            if tag and tag not in discovery.tags:
                continue
            if feature and discovery.related_feature != feature:
                continue

            discoveries.append(discovery)

        # Sort by timestamp descending (most recent first)
        discoveries.sort(key=lambda x: x.timestamp, reverse=True)

        if limit > 0:
            discoveries = discoveries[:limit]

        return discoveries

    def search_discoveries(self, query: str) -> List[Discovery]:
        """Search discoveries by keyword.

        Args:
            query: Search query (case-insensitive).

        Returns:
            List of matching Discovery objects.
        """
        data = self._load_data()
        query_lower = query.lower()
        matches = []

        for d in data.get("discoveries", []):
            discovery = Discovery.from_dict(d)

            # Search in summary, details, context, impact
            searchable = " ".join([
                discovery.summary,
                discovery.details,
                discovery.context,
                discovery.impact,
                " ".join(discovery.tags),
            ]).lower()

            if query_lower in searchable:
                matches.append(discovery)

        return matches

    def update_discovery(
        self,
        discovery_id: str,
        summary: str = None,
        context: str = None,
        details: str = None,
        impact: str = None,
        tags: List[str] = None,
        related_feature: str = None,
    ) -> Optional[Discovery]:
        """Update an existing discovery.

        Args:
            discovery_id: The discovery ID to update.
            summary: New summary (None = keep existing).
            context: New context.
            details: New details.
            impact: New impact.
            tags: New tags.
            related_feature: New related feature.

        Returns:
            Updated Discovery or None if not found.
        """
        data = self._load_data()

        for i, d in enumerate(data.get("discoveries", [])):
            if d.get("id") == discovery_id:
                if summary is not None:
                    d["summary"] = summary
                if context is not None:
                    d["context"] = context
                if details is not None:
                    d["details"] = details
                if impact is not None:
                    d["impact"] = impact
                if tags is not None:
                    d["tags"] = tags
                if related_feature is not None:
                    d["related_feature"] = related_feature

                data["discoveries"][i] = d
                self._save_data()
                return Discovery.from_dict(d)

        return None

    def delete_discovery(self, discovery_id: str) -> bool:
        """Delete a discovery.

        Args:
            discovery_id: The discovery ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        data = self._load_data()
        original_len = len(data.get("discoveries", []))

        data["discoveries"] = [
            d for d in data.get("discoveries", [])
            if d.get("id") != discovery_id
        ]

        if len(data["discoveries"]) < original_len:
            self._save_data()
            return True
        return False

    def get_tags(self) -> List[str]:
        """Get all unique tags used in discoveries.

        Returns:
            List of unique tags.
        """
        data = self._load_data()
        tags = set()
        for d in data.get("discoveries", []):
            tags.update(d.get("tags", []))
        return sorted(tags)

    def get_stats(self) -> dict:
        """Get discovery statistics.

        Returns:
            Dictionary with stats.
        """
        data = self._load_data()
        discoveries = data.get("discoveries", [])

        return {
            "total": len(discoveries),
            "by_source": self._count_by_field(discoveries, "source"),
            "tags": self.get_tags(),
            "tag_counts": self._count_tags(discoveries),
        }

    def _count_by_field(self, discoveries: List[dict], field: str) -> Dict[str, int]:
        """Count discoveries by a field value."""
        counts = {}
        for d in discoveries:
            value = d.get(field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _count_tags(self, discoveries: List[dict]) -> Dict[str, int]:
        """Count tag occurrences."""
        counts = {}
        for d in discoveries:
            for tag in d.get("tags", []):
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def show_discoveries(self, discoveries: List[Discovery], compact: bool = False):
        """Display discoveries in a formatted way.

        Args:
            discoveries: List of discoveries to display.
            compact: Use compact display format.
        """
        if not discoveries:
            console.print("[dim]No discoveries found.[/dim]")
            return

        if compact:
            self._show_compact(discoveries)
        else:
            self._show_full(discoveries)

    def _show_compact(self, discoveries: List[Discovery]):
        """Show compact discovery list."""
        table = Table(title="Discoveries")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Summary", style="white")
        table.add_column("Tags", style="yellow")
        table.add_column("Date", style="dim", width=10)

        for d in discoveries:
            date = d.timestamp[:10] if d.timestamp else ""
            tags = ", ".join(d.tags[:3]) if d.tags else ""
            if len(d.tags) > 3:
                tags += "..."

            # Truncate summary
            summary = d.summary[:60] + "..." if len(d.summary) > 60 else d.summary

            table.add_row(d.id, summary, tags, date)

        console.print(table)

    def _show_full(self, discoveries: List[Discovery]):
        """Show full discovery details."""
        for d in discoveries:
            tags_str = ", ".join(d.tags) if d.tags else "(none)"
            date = d.timestamp[:19].replace("T", " ") if d.timestamp else "Unknown"

            panel_content = f"""[bold cyan]{d.summary}[/bold cyan]

[dim]ID:[/dim] {d.id}
[dim]Date:[/dim] {date}
[dim]Tags:[/dim] {tags_str}
[dim]Source:[/dim] {d.source}"""

            if d.context:
                panel_content += f"\n\n[bold]Context:[/bold]\n{d.context}"
            if d.details:
                panel_content += f"\n\n[bold]Details:[/bold]\n{d.details}"
            if d.impact:
                panel_content += f"\n\n[bold]Impact:[/bold]\n{d.impact}"
            if d.related_feature:
                panel_content += f"\n\n[dim]Related Feature:[/dim] {d.related_feature}"

            console.print(Panel(panel_content, title=f"Discovery {d.id}"))
            console.print()

    def generate_summary_for_context(self) -> str:
        """Generate a summary of discoveries for inclusion in context.

        This creates a concise summary that can be included in session
        handoffs or CLAUDE.md to preserve institutional knowledge.

        Returns:
            Formatted markdown summary.
        """
        discoveries = self.list_discoveries(limit=20)

        if not discoveries:
            return ""

        lines = [
            "## Key Discoveries",
            "",
            "Important findings and requirements discovered during development:",
            "",
        ]

        for d in discoveries:
            tags_str = f" [{', '.join(d.tags)}]" if d.tags else ""
            lines.append(f"- **{d.id}**: {d.summary}{tags_str}")
            if d.impact:
                lines.append(f"  - *Impact*: {d.impact}")

        lines.append("")
        return "\n".join(lines)


def get_discovery_tracker(project_path: str = ".") -> DiscoveryTracker:
    """Get a discovery tracker instance.

    Args:
        project_path: Path to project root.

    Returns:
        DiscoveryTracker instance.
    """
    return DiscoveryTracker(project_path)
