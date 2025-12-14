"""Progress tracking for session continuity in Claude Harness.

Manages the progress.md file to maintain context between sessions:
- What was done last session
- Current work in progress
- Blockers and issues
- Next steps
- Files modified
"""

import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown


console = Console()


@dataclass
class SessionProgress:
    """Progress data for a session."""

    session_date: str = ""
    completed: List[str] = field(default_factory=list)
    in_progress: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    context_notes: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.session_date:
            self.session_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


class ProgressTracker:
    """Manages session progress in progress.md."""

    SECTION_MARKERS = {
        "completed": "### Completed This Session",
        "in_progress": "### Current Work In Progress",
        "blockers": "### Blockers",
        "next_steps": "### Next Session Should",
        "context_notes": "### Context Notes",
        "files_modified": "### Files Modified This Session",
        "previous": "## Previous Sessions",
    }

    def __init__(self, project_path: str):
        """Initialize with project path."""
        self.project_path = Path(project_path).resolve()
        self.progress_file = self.project_path / ".claude-harness" / "progress.md"
        self.history_dir = self.project_path / ".claude-harness" / "session-history"

    def _ensure_file(self):
        """Ensure progress file exists."""
        if not self.progress_file.exists():
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            self._write_initial()

    def _write_initial(self):
        """Write initial progress file."""
        content = """# Session Progress Log

## Last Session: (No previous session)

### Completed This Session
- [ ] No tasks completed yet

### Current Work In Progress
- [ ] No tasks in progress

### Blockers
- None

### Next Session Should
1. Run `./scripts/init.sh` to verify environment
2. Check `.claude-harness/features.json` for pending features
3. Pick ONE feature to work on

### Context Notes
- Project initialized with Claude Harness

### Files Modified This Session
- (none)

---
## Previous Sessions
(No previous sessions)
"""
        with open(self.progress_file, "w") as f:
            f.write(content)

    def _read_file(self) -> str:
        """Read progress file content."""
        self._ensure_file()
        return self.progress_file.read_text()

    def _write_file(self, content: str):
        """Write progress file content."""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, "w") as f:
            f.write(content)

    def _parse_list_items(self, content: str, start_marker: str, end_markers: List[str]) -> List[str]:
        """Parse list items between markers."""
        items = []

        # Find start position
        start_pos = content.find(start_marker)
        if start_pos == -1:
            return items

        # Find end position (next section)
        end_pos = len(content)
        for marker in end_markers:
            pos = content.find(marker, start_pos + len(start_marker))
            if pos != -1 and pos < end_pos:
                end_pos = pos

        # Extract section content
        section = content[start_pos + len(start_marker):end_pos]

        # Parse list items
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                # Remove checkbox if present
                item = re.sub(r"^\[[ x]\]\s*", "", line[2:])
                # Filter out placeholder texts
                placeholders = ("None", "(none)", "No tasks in progress", "No tasks completed yet")
                if item and item not in placeholders:
                    items.append(item)
            elif line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                # Numbered list
                item = re.sub(r"^\d+\.\s*", "", line)
                if item:
                    items.append(item)

        return items

    def get_current_progress(self) -> SessionProgress:
        """Get current session progress."""
        content = self._read_file()

        progress = SessionProgress()

        # Parse session date
        date_match = re.search(r"## Last Session: (.+)", content)
        if date_match:
            progress.session_date = date_match.group(1).strip()

        # Parse sections
        all_markers = list(self.SECTION_MARKERS.values())

        progress.completed = self._parse_list_items(
            content,
            self.SECTION_MARKERS["completed"],
            all_markers,
        )

        progress.in_progress = self._parse_list_items(
            content,
            self.SECTION_MARKERS["in_progress"],
            all_markers,
        )

        progress.blockers = self._parse_list_items(
            content,
            self.SECTION_MARKERS["blockers"],
            all_markers,
        )

        progress.next_steps = self._parse_list_items(
            content,
            self.SECTION_MARKERS["next_steps"],
            all_markers,
        )

        progress.context_notes = self._parse_list_items(
            content,
            self.SECTION_MARKERS["context_notes"],
            all_markers,
        )

        progress.files_modified = self._parse_list_items(
            content,
            self.SECTION_MARKERS["files_modified"],
            all_markers,
        )

        return progress

    def update_progress(
        self,
        completed: Optional[List[str]] = None,
        in_progress: Optional[List[str]] = None,
        blockers: Optional[List[str]] = None,
        next_steps: Optional[List[str]] = None,
        context_notes: Optional[List[str]] = None,
        files_modified: Optional[List[str]] = None,
        archive_previous: bool = True,
    ):
        """Update progress file with new information."""
        current = self.get_current_progress()

        # Archive previous session if needed
        if archive_previous and current.session_date != "(No previous session)":
            self._archive_session(current)

        # Create new progress
        new_progress = SessionProgress(
            session_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC",
            completed=completed if completed is not None else current.completed,
            in_progress=in_progress if in_progress is not None else current.in_progress,
            blockers=blockers if blockers is not None else current.blockers,
            next_steps=next_steps if next_steps is not None else current.next_steps,
            context_notes=context_notes if context_notes is not None else current.context_notes,
            files_modified=files_modified if files_modified is not None else current.files_modified,
        )

        # Generate new content
        content = self._generate_content(new_progress)
        self._write_file(content)

    def _archive_session(self, progress: SessionProgress):
        """Archive a session to history."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from date
        date_str = progress.session_date.replace(" ", "_").replace(":", "")
        archive_file = self.history_dir / f"session_{date_str}.md"

        content = self._generate_content(progress, include_header=False)

        with open(archive_file, "w") as f:
            f.write(content)

    def _generate_content(self, progress: SessionProgress, include_header: bool = True) -> str:
        """Generate progress.md content."""
        lines = []

        if include_header:
            lines.append("# Session Progress Log")
            lines.append("")

        lines.append(f"## Last Session: {progress.session_date}")
        lines.append("")

        # Completed
        lines.append(self.SECTION_MARKERS["completed"])
        if progress.completed:
            for item in progress.completed:
                lines.append(f"- [x] {item}")
        else:
            lines.append("- [ ] No tasks completed yet")
        lines.append("")

        # In Progress
        lines.append(self.SECTION_MARKERS["in_progress"])
        if progress.in_progress:
            for item in progress.in_progress:
                lines.append(f"- [ ] {item}")
        else:
            lines.append("- [ ] No tasks in progress")
        lines.append("")

        # Blockers
        lines.append(self.SECTION_MARKERS["blockers"])
        if progress.blockers:
            for item in progress.blockers:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.append("")

        # Next Steps
        lines.append(self.SECTION_MARKERS["next_steps"])
        if progress.next_steps:
            for i, item in enumerate(progress.next_steps, 1):
                lines.append(f"{i}. {item}")
        else:
            lines.append("1. Run `./scripts/init.sh` to verify environment")
            lines.append("2. Check `.claude-harness/features.json` for pending features")
            lines.append("3. Pick ONE feature to work on")
        lines.append("")

        # Context Notes
        lines.append(self.SECTION_MARKERS["context_notes"])
        if progress.context_notes:
            for item in progress.context_notes:
                lines.append(f"- {item}")
        else:
            lines.append("- (none)")
        lines.append("")

        # Files Modified
        lines.append(self.SECTION_MARKERS["files_modified"])
        if progress.files_modified:
            for item in progress.files_modified:
                lines.append(f"- {item}")
        else:
            lines.append("- (none)")
        lines.append("")

        if include_header:
            lines.append("---")
            lines.append("## Previous Sessions")
            lines.append("(See .claude-harness/session-history/ for archived sessions)")

        return "\n".join(lines)

    # --- Convenience Methods ---

    def add_completed(self, item: str):
        """Add a completed item."""
        current = self.get_current_progress()
        current.completed.append(item)
        self.update_progress(
            completed=current.completed,
            archive_previous=False,
        )

    def add_in_progress(self, item: str):
        """Add an in-progress item."""
        current = self.get_current_progress()
        current.in_progress.append(item)
        self.update_progress(
            in_progress=current.in_progress,
            archive_previous=False,
        )

    def add_blocker(self, item: str):
        """Add a blocker."""
        current = self.get_current_progress()
        current.blockers.append(item)
        self.update_progress(
            blockers=current.blockers,
            archive_previous=False,
        )

    def add_file_modified(self, filepath: str):
        """Add a modified file."""
        current = self.get_current_progress()
        if filepath not in current.files_modified:
            current.files_modified.append(filepath)
            self.update_progress(
                files_modified=current.files_modified,
                archive_previous=False,
            )

    def mark_completed(self, item: str):
        """Move item from in_progress to completed."""
        current = self.get_current_progress()

        # Find and remove from in_progress
        for i, ip in enumerate(current.in_progress):
            if item.lower() in ip.lower():
                current.in_progress.pop(i)
                break

        # Add to completed
        current.completed.append(item)

        self.update_progress(
            completed=current.completed,
            in_progress=current.in_progress,
            archive_previous=False,
        )

    def start_new_session(self):
        """Start a new session (archives previous)."""
        self.update_progress(
            completed=[],
            in_progress=[],
            blockers=[],
            next_steps=[
                "Run `./scripts/init.sh` to verify environment",
                "Check `.claude-harness/features.json` for pending features",
                "Pick ONE feature to work on",
            ],
            context_notes=[],
            files_modified=[],
            archive_previous=True,
        )

    # --- Display Methods ---

    def show_progress(self):
        """Display current progress."""
        progress = self.get_current_progress()

        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]Session Progress[/bold blue]\n"
                f"Last updated: {progress.session_date}",
                border_style="blue",
            )
        )

        # Completed
        if progress.completed:
            console.print("\n[bold green]Completed:[/bold green]")
            for item in progress.completed:
                console.print(f"  [green]x[/green] {item}")

        # In Progress
        if progress.in_progress:
            console.print("\n[bold yellow]In Progress:[/bold yellow]")
            for item in progress.in_progress:
                console.print(f"  [ ] {item}")

        # Blockers
        if progress.blockers and progress.blockers != ["None"]:
            console.print("\n[bold red]Blockers:[/bold red]")
            for item in progress.blockers:
                console.print(f"  [red]![/red] {item}")

        # Next Steps
        if progress.next_steps:
            console.print("\n[bold blue]Next Steps:[/bold blue]")
            for i, item in enumerate(progress.next_steps, 1):
                console.print(f"  {i}. {item}")

        # Context Notes
        if progress.context_notes and progress.context_notes != ["(none)"]:
            console.print("\n[bold cyan]Context:[/bold cyan]")
            for item in progress.context_notes:
                console.print(f"  - {item}")

        # Files Modified
        if progress.files_modified and progress.files_modified != ["(none)"]:
            console.print("\n[bold magenta]Files Modified:[/bold magenta]")
            for item in progress.files_modified[:10]:  # Limit display
                console.print(f"  - {item}")
            if len(progress.files_modified) > 10:
                console.print(f"  [dim]... and {len(progress.files_modified) - 10} more[/dim]")

    def show_raw(self):
        """Display raw progress.md content."""
        content = self._read_file()
        console.print(Markdown(content))

    def list_history(self, limit: int = 10) -> List[dict]:
        """List archived session files.

        Returns:
            List of dicts with 'filename', 'date', 'path' keys, sorted newest first.
        """
        if not self.history_dir.exists():
            return []

        sessions = []
        for filepath in self.history_dir.glob("session_*.md"):
            # Extract date from filename: session_2025-12-12_1930_UTC.md
            filename = filepath.stem
            date_part = filename.replace("session_", "").replace("_", " ")
            sessions.append({
                "filename": filepath.name,
                "date": date_part,
                "path": filepath,
            })

        # Sort by filename (which contains date) descending
        sessions.sort(key=lambda x: x["filename"], reverse=True)

        return sessions[:limit]

    def show_history(self, limit: int = 10):
        """Display session history summary."""
        sessions = self.list_history(limit)

        if not sessions:
            console.print("[yellow]No session history found[/yellow]")
            console.print("[dim]Sessions are archived when you start a new session[/dim]")
            return

        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]Session History[/bold blue]\n"
                f"Showing {len(sessions)} most recent sessions",
                border_style="blue",
            )
        )

        for i, session in enumerate(sessions):
            # Try to read and parse the session file for summary
            try:
                content = session["path"].read_text()
                # Count completed items
                completed_count = content.count("- [x]")
                # Get first line of completed section
                completed_preview = ""
                if "### Completed This Session" in content:
                    section_start = content.find("### Completed This Session")
                    section = content[section_start:section_start + 500]
                    lines = section.split("\n")[1:4]  # Get first 3 items
                    items = [l.strip() for l in lines if l.strip().startswith("- [")]
                    if items:
                        completed_preview = items[0].replace("- [x] ", "")[:50]

                console.print(f"\n[bold]{i + 1}. {session['date']}[/bold]")
                console.print(f"   Completed: {completed_count} items")
                if completed_preview:
                    console.print(f"   [dim]First: {completed_preview}...[/dim]")
            except Exception:
                console.print(f"\n[bold]{i + 1}. {session['date']}[/bold]")
                console.print(f"   [dim]Unable to read session details[/dim]")

        console.print()
        console.print(f"[dim]History directory: {self.history_dir}[/dim]")

    def show_session(self, index: int):
        """Show details of a specific historical session by index (1-based)."""
        sessions = self.list_history(100)  # Get more to allow higher indices

        if not sessions:
            console.print("[yellow]No session history found[/yellow]")
            return

        if index < 1 or index > len(sessions):
            console.print(f"[red]Invalid session index. Valid range: 1-{len(sessions)}[/red]")
            return

        session = sessions[index - 1]

        try:
            content = session["path"].read_text()
            console.print()
            console.print(f"[bold blue]Session: {session['date']}[/bold blue]")
            console.print()
            console.print(Markdown(content))
        except Exception as e:
            console.print(f"[red]Error reading session: {e}[/red]")


def get_progress_tracker(project_path: str = ".") -> ProgressTracker:
    """Get a progress tracker instance."""
    return ProgressTracker(project_path)
