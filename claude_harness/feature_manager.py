"""Feature and task management for Claude Harness.

Manages the features.json file with operations:
- Add/remove features
- Update status (pending, in_progress, completed, blocked)
- Manage subtasks
- Track E2E validation status
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


@dataclass
class Subtask:
    """A subtask within a feature."""

    name: str
    done: bool = False

    def to_dict(self) -> dict:
        return {"name": self.name, "done": self.done}

    @classmethod
    def from_dict(cls, data: dict) -> "Subtask":
        return cls(name=data["name"], done=data.get("done", False))


@dataclass
class Feature:
    """A feature being tracked."""

    id: str
    name: str
    status: str = "pending"  # pending, in_progress, completed, blocked
    priority: int = 0
    tests_passing: bool = False
    e2e_validated: bool = False
    subtasks: List[Subtask] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    completed_at: Optional[str] = None
    blocked_reason: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "priority": self.priority,
            "tests_passing": self.tests_passing,
            "e2e_validated": self.e2e_validated,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "notes": self.notes,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Feature":
        subtasks = [Subtask.from_dict(s) for s in data.get("subtasks", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            status=data.get("status", "pending"),
            priority=data.get("priority", 0),
            tests_passing=data.get("tests_passing", False),
            e2e_validated=data.get("e2e_validated", False),
            subtasks=subtasks,
            notes=data.get("notes", ""),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at"),
            blocked_reason=data.get("blocked_reason"),
        )

    @property
    def subtask_progress(self) -> str:
        """Return subtask progress as string."""
        if not self.subtasks:
            return "No subtasks"
        done = sum(1 for s in self.subtasks if s.done)
        return f"{done}/{len(self.subtasks)}"

    @property
    def is_complete(self) -> bool:
        """Check if feature is complete (all subtasks done + validated)."""
        subtasks_done = all(s.done for s in self.subtasks) if self.subtasks else True
        return subtasks_done and self.tests_passing


class FeatureManager:
    """Manages features in features.json."""

    def __init__(self, project_path: str):
        """Initialize with project path."""
        self.project_path = Path(project_path).resolve()
        self.features_file = self.project_path / ".claude-harness" / "features.json"
        self._data = None

    def _load(self) -> dict:
        """Load features data."""
        if self._data is not None:
            return self._data

        if not self.features_file.exists():
            self._data = {
                "current_phase": "Phase 1",
                "features": [],
                "completed": [],
                "blocked": [],
            }
        else:
            with open(self.features_file) as f:
                self._data = json.load(f)

        return self._data

    def _save(self):
        """Save features data."""
        if self._data is None:
            return

        self.features_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.features_file, "w") as f:
            json.dump(self._data, f, indent=2)

    def _generate_id(self) -> str:
        """Generate next feature ID."""
        data = self._load()
        all_features = data["features"] + data["completed"] + data["blocked"]

        if not all_features:
            return "F-001"

        # Find highest number
        max_num = 0
        for f in all_features:
            fid = f.get("id", "F-000")
            try:
                num = int(fid.split("-")[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                pass

        return f"F-{max_num + 1:03d}"

    # --- Public Methods ---

    def list_features(self, status: Optional[str] = None) -> List[Feature]:
        """List all features, optionally filtered by status."""
        data = self._load()
        features = [Feature.from_dict(f) for f in data["features"]]

        if status:
            features = [f for f in features if f.status == status]

        return sorted(features, key=lambda f: (f.priority, f.id))

    def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get a specific feature by ID."""
        data = self._load()

        for f in data["features"]:
            if f["id"] == feature_id:
                return Feature.from_dict(f)

        # Check completed
        for f in data["completed"]:
            if f["id"] == feature_id:
                return Feature.from_dict(f)

        # Check blocked
        for f in data["blocked"]:
            if f["id"] == feature_id:
                return Feature.from_dict(f)

        return None

    def add_feature(
        self,
        name: str,
        priority: int = 0,
        subtasks: Optional[List[str]] = None,
        notes: str = "",
    ) -> Feature:
        """Add a new feature."""
        data = self._load()

        feature = Feature(
            id=self._generate_id(),
            name=name,
            priority=priority,
            subtasks=[Subtask(name=s) for s in (subtasks or [])],
            notes=notes,
        )

        data["features"].append(feature.to_dict())
        self._save()

        return feature

    def update_status(
        self,
        feature_id: str,
        status: str,
        blocked_reason: Optional[str] = None,
    ) -> Optional[Feature]:
        """Update feature status."""
        data = self._load()

        # Find feature in any list
        feature_dict = None
        source_list = None

        for lst_name in ["features", "completed", "blocked"]:
            for i, f in enumerate(data[lst_name]):
                if f["id"] == feature_id:
                    feature_dict = f
                    source_list = (lst_name, i)
                    break
            if feature_dict:
                break

        if not feature_dict:
            return None

        # Remove from current list
        lst_name, idx = source_list
        data[lst_name].pop(idx)

        # Update status
        feature_dict["status"] = status

        if status == "completed":
            feature_dict["completed_at"] = datetime.now(timezone.utc).isoformat()
            data["completed"].append(feature_dict)
        elif status == "blocked":
            feature_dict["blocked_reason"] = blocked_reason
            data["blocked"].append(feature_dict)
        else:
            feature_dict["blocked_reason"] = None
            data["features"].append(feature_dict)

        self._save()
        return Feature.from_dict(feature_dict)

    def start_feature(self, feature_id: str) -> Optional[Feature]:
        """Mark a feature as in_progress (and ensure only one is active)."""
        data = self._load()

        # First, set any in_progress features back to pending
        for f in data["features"]:
            if f["status"] == "in_progress" and f["id"] != feature_id:
                f["status"] = "pending"

        # Now start the requested feature
        return self.update_status(feature_id, "in_progress")

    def complete_feature(self, feature_id: str) -> Optional[Feature]:
        """Mark a feature as completed."""
        feature = self.get_feature(feature_id)

        if not feature:
            return None

        # Validate completion requirements
        if feature.subtasks:
            incomplete = [s for s in feature.subtasks if not s.done]
            if incomplete:
                console.print(
                    f"[yellow]Warning: {len(incomplete)} subtasks not completed[/yellow]"
                )

        if not feature.tests_passing:
            console.print("[yellow]Warning: Tests not marked as passing[/yellow]")

        return self.update_status(feature_id, "completed")

    def add_subtask(self, feature_id: str, subtask_name: str) -> Optional[Feature]:
        """Add a subtask to a feature."""
        data = self._load()

        for f in data["features"]:
            if f["id"] == feature_id:
                f["subtasks"].append({"name": subtask_name, "done": False})
                self._save()
                return Feature.from_dict(f)

        return None

    def complete_subtask(
        self, feature_id: str, subtask_index: int
    ) -> Optional[Feature]:
        """Mark a subtask as done."""
        data = self._load()

        for f in data["features"]:
            if f["id"] == feature_id:
                if 0 <= subtask_index < len(f["subtasks"]):
                    f["subtasks"][subtask_index]["done"] = True
                    self._save()
                    return Feature.from_dict(f)

        return None

    def set_tests_passing(
        self, feature_id: str, passing: bool = True
    ) -> Optional[Feature]:
        """Mark feature tests as passing."""
        data = self._load()

        for f in data["features"]:
            if f["id"] == feature_id:
                f["tests_passing"] = passing
                self._save()
                return Feature.from_dict(f)

        return None

    def set_e2e_validated(
        self, feature_id: str, validated: bool = True
    ) -> Optional[Feature]:
        """Mark feature as E2E validated."""
        data = self._load()

        for f in data["features"]:
            if f["id"] == feature_id:
                f["e2e_validated"] = validated
                self._save()
                return Feature.from_dict(f)

        return None

    def add_note(self, feature_id: str, note: str) -> Optional[Feature]:
        """Add a timestamped note to a feature."""
        data = self._load()

        # Search in all lists
        for lst_name in ["features", "completed", "blocked"]:
            for f in data[lst_name]:
                if f["id"] == feature_id:
                    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                    note_entry = f"[{timestamp}] {note}"

                    # Append to existing notes
                    if f.get("notes"):
                        f["notes"] = f["notes"] + "\n" + note_entry
                    else:
                        f["notes"] = note_entry

                    self._save()
                    return Feature.from_dict(f)

        return None

    def get_current_phase(self) -> str:
        """Get current phase name."""
        data = self._load()
        return data.get("current_phase", "Phase 1")

    def set_current_phase(self, phase: str):
        """Set current phase name."""
        data = self._load()
        data["current_phase"] = phase
        self._save()

    def get_in_progress(self) -> Optional[Feature]:
        """Get the currently in-progress feature."""
        features = self.list_features(status="in_progress")
        return features[0] if features else None

    def get_next_pending(self) -> Optional[Feature]:
        """Get the next pending feature by priority."""
        features = self.list_features(status="pending")
        return features[0] if features else None

    # --- Display Methods ---

    def show_status(self):
        """Display feature status summary."""
        data = self._load()

        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]Feature Tracking[/bold blue]\n"
                f"Phase: {data.get('current_phase', 'Unknown')}",
                border_style="blue",
            )
        )

        # In Progress
        in_progress = self.get_in_progress()
        if in_progress:
            console.print(f"\n[bold yellow]In Progress:[/bold yellow]")
            console.print(f"  {in_progress.id}: {in_progress.name}")
            console.print(f"  Subtasks: {in_progress.subtask_progress}")
            if in_progress.subtasks:
                for i, st in enumerate(in_progress.subtasks):
                    mark = "[green]x[/green]" if st.done else "[ ]"
                    console.print(f"    {mark} {st.name}")

        # Pending
        pending = self.list_features(status="pending")
        if pending:
            console.print(f"\n[bold blue]Pending ({len(pending)}):[/bold blue]")
            for f in pending[:5]:  # Show top 5
                console.print(f"  {f.id}: {f.name}")
            if len(pending) > 5:
                console.print(f"  [dim]... and {len(pending) - 5} more[/dim]")

        # Blocked
        blocked_features = [Feature.from_dict(f) for f in data["blocked"]]
        if blocked_features:
            console.print(f"\n[bold red]Blocked ({len(blocked_features)}):[/bold red]")
            for f in blocked_features:
                console.print(f"  {f.id}: {f.name}")
                if f.blocked_reason:
                    console.print(f"    [dim]Reason: {f.blocked_reason}[/dim]")

        # Completed count
        completed_count = len(data["completed"])
        total = len(data["features"]) + completed_count + len(data["blocked"])
        console.print(f"\n[green]Completed: {completed_count}/{total}[/green]")

    def show_table(self, include_completed: bool = False):
        """Display features as a table."""
        data = self._load()

        table = Table(title=f"Features - {data.get('current_phase', 'Unknown')}")
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Name", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Subtasks", justify="center")
        table.add_column("Tests", justify="center")
        table.add_column("E2E", justify="center")

        # Active features
        for f_dict in data["features"]:
            f = Feature.from_dict(f_dict)
            status_style = {
                "pending": "blue",
                "in_progress": "yellow",
                "blocked": "red",
            }.get(f.status, "white")

            tests_mark = "[green]Y[/green]" if f.tests_passing else "[red]N[/red]"
            e2e_mark = "[green]Y[/green]" if f.e2e_validated else "[red]N[/red]"

            table.add_row(
                f.id,
                f.name,
                f"[{status_style}]{f.status}[/{status_style}]",
                f.subtask_progress,
                tests_mark,
                e2e_mark,
            )

        # Completed (if requested)
        if include_completed:
            for f_dict in data["completed"]:
                f = Feature.from_dict(f_dict)
                table.add_row(
                    f.id,
                    f.name,
                    "[green]completed[/green]",
                    f.subtask_progress,
                    "[green]Y[/green]",
                    "[green]Y[/green]" if f.e2e_validated else "[dim]-[/dim]",
                )

        console.print(table)


def get_feature_manager(project_path: str = ".") -> FeatureManager:
    """Get a feature manager instance."""
    return FeatureManager(project_path)
