"""Context and token tracking for Claude Harness.

Tracks estimated token usage to help manage context window:
- Files read (characters → estimated tokens)
- Commands executed
- Tool calls made
- Session duration and activity

Note: These are estimates since we can't directly access Claude's token counts.
The goal is to provide awareness and help optimize context usage.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn


console = Console()


# Approximate token ratios (these are rough estimates)
CHARS_PER_TOKEN = 4  # English text averages ~4 chars per token
CODE_CHARS_PER_TOKEN = 3.5  # Code tends to be slightly more token-dense


@dataclass
class ContextMetrics:
    """Metrics for context usage tracking."""

    # Session info
    session_start: str = ""
    session_duration_minutes: float = 0.0
    session_id: str = ""  # Unique ID per session
    session_closed: bool = False  # Marked true when session ends

    # File operations
    files_read: List[str] = field(default_factory=list)
    files_read_chars: int = 0
    files_written: List[str] = field(default_factory=list)
    files_written_chars: int = 0

    # Commands/tools
    commands_executed: int = 0
    tool_calls: int = 0

    # Token estimates
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_total_tokens: int = 0

    # Context budget (configurable)
    context_budget: int = 200000  # Default ~200k tokens
    context_warning_threshold: float = 0.7  # Warn at 70%
    context_critical_threshold: float = 0.9  # Critical at 90%

    # Per-task tracking
    current_task_id: Optional[str] = None
    task_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Compaction tracking (estimated)
    estimated_compactions: int = 0
    peak_tokens: int = 0  # Highest token count observed
    compaction_events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.session_start:
            self.session_start = datetime.now(timezone.utc).isoformat()
        if not self.session_id:
            import uuid
            self.session_id = str(uuid.uuid4())[:8]

    @property
    def context_usage_percent(self) -> float:
        """Calculate context usage as percentage."""
        if self.context_budget <= 0:
            return 0.0
        return (self.estimated_total_tokens / self.context_budget) * 100

    @property
    def remaining_tokens(self) -> int:
        """Calculate remaining tokens in budget."""
        return max(0, self.context_budget - self.estimated_total_tokens)

    @property
    def status(self) -> str:
        """Get context status: ok, warning, critical."""
        usage = self.context_usage_percent / 100
        if usage >= self.context_critical_threshold:
            return "critical"
        elif usage >= self.context_warning_threshold:
            return "warning"
        return "ok"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_start": self.session_start,
            "session_duration_minutes": self.session_duration_minutes,
            "session_id": self.session_id,
            "session_closed": self.session_closed,
            "files_read": self.files_read,
            "files_read_chars": self.files_read_chars,
            "files_written": self.files_written,
            "files_written_chars": self.files_written_chars,
            "commands_executed": self.commands_executed,
            "tool_calls": self.tool_calls,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "context_budget": self.context_budget,
            "context_usage_percent": round(self.context_usage_percent, 1),
            "remaining_tokens": self.remaining_tokens,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "task_metrics": self.task_metrics,
            "estimated_compactions": self.estimated_compactions,
            "peak_tokens": self.peak_tokens,
            "compaction_events": self.compaction_events,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextMetrics":
        """Create from dictionary."""
        return cls(
            session_start=data.get("session_start", ""),
            session_duration_minutes=data.get("session_duration_minutes", 0.0),
            session_id=data.get("session_id", ""),
            session_closed=data.get("session_closed", False),
            files_read=data.get("files_read", []),
            files_read_chars=data.get("files_read_chars", 0),
            files_written=data.get("files_written", []),
            files_written_chars=data.get("files_written_chars", 0),
            commands_executed=data.get("commands_executed", 0),
            tool_calls=data.get("tool_calls", 0),
            estimated_input_tokens=data.get("estimated_input_tokens", 0),
            estimated_output_tokens=data.get("estimated_output_tokens", 0),
            estimated_total_tokens=data.get("estimated_total_tokens", 0),
            context_budget=data.get("context_budget", 200000),
            current_task_id=data.get("current_task_id"),
            task_metrics=data.get("task_metrics", {}),
            estimated_compactions=data.get("estimated_compactions", 0),
            peak_tokens=data.get("peak_tokens", 0),
            compaction_events=data.get("compaction_events", []),
        )


class ContextTracker:
    """Tracks context/token usage for Claude Code sessions."""

    def __init__(self, project_path: str):
        """Initialize with project path."""
        self.project_path = Path(project_path).resolve()
        self.metrics_file = self.project_path / ".claude-harness" / "context_metrics.json"
        self.config_file = self.project_path / ".claude-harness" / "config.json"
        self._metrics: Optional[ContextMetrics] = None
        self._start_time = time.time()

    def _load_config(self) -> dict:
        """Load harness config."""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        return {}

    def _load_metrics(self) -> ContextMetrics:
        """Load or create metrics.

        Handles session lifecycle:
        - If previous session was marked closed, starts fresh session
        - Archives previous session metrics before reset
        - Respects auto_reset_session config setting
        """
        if self._metrics is not None:
            return self._metrics

        config = self._load_config()
        context_config = config.get("context_tracking", {})
        auto_reset = context_config.get("auto_reset_session", True)

        previous_session = None

        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    data = json.load(f)
                loaded_metrics = ContextMetrics.from_dict(data)

                # Check if previous session was closed
                if loaded_metrics.session_closed and auto_reset:
                    # Archive previous session before reset
                    previous_session = loaded_metrics
                    self._archive_session(loaded_metrics)
                    # Start fresh session and persist it
                    self._metrics = ContextMetrics()
                    self._save_metrics()
                else:
                    self._metrics = loaded_metrics
                    # If resuming, mark as not closed and persist
                    if self._metrics.session_closed:
                        self._metrics.session_closed = False
                        self._save_metrics()
            except Exception:
                self._metrics = ContextMetrics()
        else:
            self._metrics = ContextMetrics()

        # Apply config settings
        if context_config.get("enabled", True):
            self._metrics.context_budget = context_config.get("budget", 200000)
            self._metrics.context_warning_threshold = context_config.get("warning_threshold", 0.7)
            self._metrics.context_critical_threshold = context_config.get("critical_threshold", 0.9)

        return self._metrics

    def _archive_session(self, metrics: ContextMetrics):
        """Archive a closed session's metrics to session history.

        Args:
            metrics: The metrics from the closed session to archive.
        """
        history_dir = self.project_path / ".claude-harness" / "session-history"
        history_dir.mkdir(parents=True, exist_ok=True)

        # Create archive filename with session ID and timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        session_id = metrics.session_id or "unknown"
        archive_file = history_dir / f"session_{session_id}_{timestamp}.json"

        try:
            with open(archive_file, "w") as f:
                json.dump(metrics.to_dict(), f, indent=2)
        except IOError:
            pass  # Fail silently on archive errors

    def _save_metrics(self):
        """Save metrics to file."""
        if self._metrics is None:
            return

        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Update duration
        self._metrics.session_duration_minutes = (time.time() - self._start_time) / 60

        # Check for compaction (context overflow)
        self._detect_compaction()

        with open(self.metrics_file, "w") as f:
            json.dump(self._metrics.to_dict(), f, indent=2)

    def _detect_compaction(self):
        """Detect when context likely compacted (exceeded 100%).

        Compaction detection strategy:
        1. Track peak token usage
        2. When estimated tokens exceed the budget, it indicates a compaction
           likely occurred or will occur soon
        3. Record each crossing of the 100% threshold as a compaction event

        Note: This is estimation-based. Claude Code's actual compaction is opaque.
        """
        if self._metrics is None:
            return

        current_tokens = self._metrics.estimated_total_tokens
        budget = self._metrics.context_budget

        # Update peak if current is higher
        if current_tokens > self._metrics.peak_tokens:
            self._metrics.peak_tokens = current_tokens

        # Detect threshold crossing (compaction indicator)
        # We count a compaction when tokens exceed budget for the first time
        # or when it exceeds budget * (compactions + 1)
        compaction_threshold = budget * (self._metrics.estimated_compactions + 1)

        if current_tokens >= compaction_threshold:
            # Record compaction event
            self._metrics.estimated_compactions += 1
            self._metrics.compaction_events.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tokens_at_compaction": current_tokens,
                "compaction_number": self._metrics.estimated_compactions,
                "files_read_count": len(self._metrics.files_read),
                "files_written_count": len(self._metrics.files_written),
                "commands_count": self._metrics.commands_executed,
            })

            # Log for activity tracking
            self._log_compaction_event()

    def _log_compaction_event(self):
        """Log compaction event to session activity log."""
        if self._metrics is None:
            return

        history_dir = self.project_path / ".claude-harness" / "session-history"
        history_dir.mkdir(parents=True, exist_ok=True)

        log_file = history_dir / f"activity-{datetime.now().strftime('%Y%m%d')}.log"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        log_entry = (
            f"[{timestamp}] COMPACTION #{self._metrics.estimated_compactions} detected | "
            f"Tokens: {self._metrics.estimated_total_tokens:,} | "
            f"Peak: {self._metrics.peak_tokens:,} | "
            f"Files: R={len(self._metrics.files_read)} W={len(self._metrics.files_written)}\n"
        )

        try:
            with open(log_file, "a") as f:
                f.write(log_entry)
        except IOError:
            pass  # Fail silently

    def _estimate_tokens(self, text: str, is_code: bool = False) -> int:
        """Estimate tokens from text."""
        chars_per_token = CODE_CHARS_PER_TOKEN if is_code else CHARS_PER_TOKEN
        return int(len(text) / chars_per_token)

    def _is_code_file(self, filepath: str) -> bool:
        """Check if file is code."""
        code_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
            ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".sh", ".bash", ".ps1", ".sql", ".json",
            ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".scss",
        }
        return Path(filepath).suffix.lower() in code_extensions

    # --- Public Tracking Methods ---

    def is_enabled(self) -> bool:
        """Check if context tracking is enabled."""
        config = self._load_config()
        return config.get("context_tracking", {}).get("enabled", True)

    def track_file_read(self, filepath: str, content_length: int):
        """Track a file read operation."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()

        if filepath not in metrics.files_read:
            metrics.files_read.append(filepath)

        metrics.files_read_chars += content_length
        is_code = self._is_code_file(filepath)
        tokens = self._estimate_tokens("x" * content_length, is_code)
        metrics.estimated_input_tokens += tokens
        metrics.estimated_total_tokens += tokens
        metrics.tool_calls += 1

        # Track per task
        if metrics.current_task_id:
            task = metrics.task_metrics.setdefault(metrics.current_task_id, {
                "files_read": 0,
                "tokens": 0,
            })
            task["files_read"] += 1
            task["tokens"] += tokens

        self._save_metrics()

    def track_file_write(self, filepath: str, content_length: int):
        """Track a file write operation."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()

        if filepath not in metrics.files_written:
            metrics.files_written.append(filepath)

        metrics.files_written_chars += content_length
        is_code = self._is_code_file(filepath)
        tokens = self._estimate_tokens("x" * content_length, is_code)
        metrics.estimated_output_tokens += tokens
        metrics.estimated_total_tokens += tokens
        metrics.tool_calls += 1

        self._save_metrics()

    def track_command(self, command: str, output_length: int = 0):
        """Track a command execution."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()
        metrics.commands_executed += 1
        metrics.tool_calls += 1

        # Estimate tokens for command and output
        cmd_tokens = self._estimate_tokens(command)
        out_tokens = self._estimate_tokens("x" * output_length)

        metrics.estimated_input_tokens += cmd_tokens
        metrics.estimated_output_tokens += out_tokens
        metrics.estimated_total_tokens += cmd_tokens + out_tokens

        self._save_metrics()

    def track_conversation(self, user_message_length: int, assistant_response_length: int):
        """Track a conversation turn."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()

        user_tokens = self._estimate_tokens("x" * user_message_length)
        assistant_tokens = self._estimate_tokens("x" * assistant_response_length)

        metrics.estimated_input_tokens += user_tokens
        metrics.estimated_output_tokens += assistant_tokens
        metrics.estimated_total_tokens += user_tokens + assistant_tokens

        self._save_metrics()

    def start_task(self, task_id: str):
        """Start tracking a specific task."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()
        metrics.current_task_id = task_id

        if task_id not in metrics.task_metrics:
            metrics.task_metrics[task_id] = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "files_read": 0,
                "files_written": 0,
                "commands": 0,
                "tokens": 0,
            }

        self._save_metrics()

    def end_task(self, task_id: str):
        """End tracking a specific task."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()

        if task_id in metrics.task_metrics:
            metrics.task_metrics[task_id]["ended_at"] = datetime.now(timezone.utc).isoformat()

        if metrics.current_task_id == task_id:
            metrics.current_task_id = None

        self._save_metrics()

    def reset_session(self, archive: bool = True):
        """Reset metrics for a new session.

        Args:
            archive: If True, archive current session before reset.
        """
        if archive and self._metrics is not None:
            self._archive_session(self._metrics)

        self._metrics = ContextMetrics()
        self._start_time = time.time()
        self._save_metrics()

    def mark_session_closed(self):
        """Mark the current session as closed.

        When a session is marked closed, the next session start will
        automatically reset metrics (if auto_reset_session is enabled).
        This is typically called by the Stop hook.
        """
        metrics = self._load_metrics()
        metrics.session_closed = True
        self._save_metrics()

    def get_session_info(self) -> dict:
        """Get information about the current session.

        Returns:
            dict with session_id, session_start, duration, closed status
        """
        metrics = self._load_metrics()
        return {
            "session_id": metrics.session_id,
            "session_start": metrics.session_start,
            "duration_minutes": metrics.session_duration_minutes,
            "closed": metrics.session_closed,
            "usage_percent": metrics.context_usage_percent,
            "estimated_compactions": metrics.estimated_compactions,
            "peak_tokens": metrics.peak_tokens,
            "compaction_events": metrics.compaction_events,
        }

    def get_metrics(self) -> ContextMetrics:
        """Get current metrics."""
        return self._load_metrics()

    # --- Display Methods ---

    def show_status(self, compact: bool = False):
        """Display context usage status."""
        if not self.is_enabled():
            console.print("[dim]Context tracking disabled[/dim]")
            return

        metrics = self._load_metrics()

        if compact:
            self._show_compact_status(metrics)
        else:
            self._show_full_status(metrics)

    def _show_compact_status(self, metrics: ContextMetrics):
        """Show compact one-line status."""
        usage = metrics.context_usage_percent
        remaining = metrics.remaining_tokens

        # Color based on status
        if metrics.status == "critical":
            color = "red"
            icon = "!!!"
        elif metrics.status == "warning":
            color = "yellow"
            icon = " ! "
        else:
            color = "green"
            icon = " * "

        # Show compaction indicator if any compactions detected
        compactions = metrics.estimated_compactions
        if compactions > 0:
            compaction_note = f" ({compactions} compaction{'s' if compactions > 1 else ''}) "
        else:
            compaction_note = " "

        console.print(
            f"[{color}][{icon}] Context: {usage:.1f}% used{compaction_note}| "
            f"~{remaining:,} tokens remaining | "
            f"{len(metrics.files_read)} files read | "
            f"{metrics.commands_executed} commands[/{color}]"
        )

    def _show_full_status(self, metrics: ContextMetrics):
        """Show full status panel."""
        usage = metrics.context_usage_percent

        # Use tracked compactions, not calculated from usage
        compactions = metrics.estimated_compactions
        compaction_info = ""
        if compactions > 0:
            compaction_info = f"\nCompactions detected: {compactions}"

        # Status color and text
        if usage > 100:
            status_color = "red"
            status_text = f"OVERFLOW ({usage:.0f}%) - New session recommended{compaction_info}"
        elif metrics.status == "critical":
            status_color = "red"
            status_text = "CRITICAL - Consider compacting or starting new session"
        elif metrics.status == "warning":
            status_color = "yellow"
            status_text = "WARNING - Context filling up"
        else:
            status_color = "green"
            status_text = "OK"

        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]Context Usage Tracking[/bold blue]\n"
                f"Status: [{status_color}]{status_text}[/{status_color}]",
                border_style=status_color,
            )
        )

        # Progress bar (cap at 100 for display)
        display_usage = min(usage, 100)
        usage_text = f"{usage:.1f}%" if usage <= 100 else f"{usage:.1f}% (overflow)"
        with Progress(
            TextColumn("[bold blue]Context"),
            BarColumn(bar_width=40),
            TextColumn(usage_text),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("", total=100)
            progress.update(task, completed=display_usage)

        # Metrics table
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Estimated Total Tokens", f"{metrics.estimated_total_tokens:,}")
        table.add_row("Context Budget", f"{metrics.context_budget:,}")
        table.add_row("Remaining", f"{metrics.remaining_tokens:,}")
        if metrics.peak_tokens > 0:
            table.add_row("Peak Tokens", f"{metrics.peak_tokens:,}")
        if compactions > 0:
            table.add_row("Compactions", str(compactions))
        table.add_row("", "")
        table.add_row("Session ID", metrics.session_id)
        table.add_row("Files Read", f"{len(metrics.files_read)}")
        table.add_row("Files Written", f"{len(metrics.files_written)}")
        table.add_row("Commands Executed", str(metrics.commands_executed))
        table.add_row("Tool Calls", str(metrics.tool_calls))
        table.add_row("", "")
        table.add_row("Session Duration", f"{metrics.session_duration_minutes:.1f} min")

        console.print(table)

        # Compaction history if available
        if metrics.compaction_events:
            console.print("\n[bold yellow]Compaction History:[/bold yellow]")
            compaction_table = Table()
            compaction_table.add_column("#", style="cyan", justify="right")
            compaction_table.add_column("Time", style="white")
            compaction_table.add_column("Tokens", style="yellow", justify="right")
            compaction_table.add_column("Files R/W", style="dim")

            for event in metrics.compaction_events[-5:]:  # Last 5
                timestamp = event.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M:%S")
                    except Exception:
                        time_str = timestamp[:19]
                else:
                    time_str = "?"

                compaction_table.add_row(
                    str(event.get("compaction_number", "?")),
                    time_str,
                    f"{event.get('tokens_at_compaction', 0):,}",
                    f"{event.get('files_read_count', 0)}/{event.get('files_written_count', 0)}",
                )

            console.print(compaction_table)

        # Task breakdown if available
        if metrics.task_metrics:
            console.print("\n[bold]Per-Task Usage:[/bold]")
            task_table = Table()
            task_table.add_column("Task", style="cyan")
            task_table.add_column("Files", justify="right")
            task_table.add_column("Est. Tokens", justify="right")

            for task_id, task_data in metrics.task_metrics.items():
                task_table.add_row(
                    task_id,
                    str(task_data.get("files_read", 0)),
                    f"{task_data.get('tokens', 0):,}",
                )

            console.print(task_table)

        # Recommendations
        if metrics.status in ("warning", "critical"):
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            console.print("  1. Update progress.md with current session summary")
            console.print("  2. Consider using /compact to summarize conversation")
            console.print("  3. Start a new session if continuing large task")
            console.print("  4. Use Task agents for exploration to reduce main context")

    def get_metadata_string(self) -> str:
        """Get metadata as a formatted string for embedding in outputs."""
        if not self.is_enabled():
            return ""

        metrics = self._load_metrics()

        return (
            f"\n---\n"
            f"**Context Metrics** | "
            f"Usage: {metrics.context_usage_percent:.1f}% | "
            f"Remaining: ~{metrics.remaining_tokens:,} tokens | "
            f"Files: {len(metrics.files_read)}R/{len(metrics.files_written)}W | "
            f"Commands: {metrics.commands_executed}\n"
        )

    def append_to_progress(self):
        """Append context metrics to progress.md."""
        if not self.is_enabled():
            return

        metrics = self._load_metrics()
        progress_file = self.project_path / ".claude-harness" / "progress.md"

        if not progress_file.exists():
            return

        content = progress_file.read_text()

        # Check if context section already exists
        if "### Context Usage" in content:
            # Update existing section
            import re
            pattern = r"### Context Usage\n.*?(?=\n###|\n---|\Z)"
            replacement = self._get_context_section(metrics)
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        else:
            # Add new section before "Files Modified"
            marker = "### Files Modified"
            if marker in content:
                content = content.replace(
                    marker,
                    self._get_context_section(metrics) + "\n" + marker
                )

        progress_file.write_text(content)

    def _get_context_section(self, metrics: ContextMetrics) -> str:
        """Generate context section for progress.md."""
        return f"""### Context Usage
- Estimated tokens used: {metrics.estimated_total_tokens:,} / {metrics.context_budget:,} ({metrics.context_usage_percent:.1f}%)
- Files read: {len(metrics.files_read)}
- Commands executed: {metrics.commands_executed}
- Status: {metrics.status.upper()}

"""


    def generate_summary(self) -> str:
        """Generate a compressed summary of the current session.

        This creates a concise summary that can be used for:
        - Quick session overview
        - Context handoff between sessions
        - Progress documentation
        """
        metrics = self._load_metrics()

        # Get progress data
        progress_file = self.project_path / ".claude-harness" / "progress.md"
        features_file = self.project_path / ".claude-harness" / "features.json"

        progress_data = {}
        features_data = {}

        if progress_file.exists():
            from .progress_tracker import ProgressTracker
            pt = ProgressTracker(str(self.project_path))
            progress = pt.get_current_progress()
            progress_data = {
                "completed": progress.completed,
                "in_progress": progress.in_progress,
                "blockers": progress.blockers,
                "files_modified": progress.files_modified,
            }

        if features_file.exists():
            import json
            with open(features_file) as f:
                features_data = json.load(f)

        # Build summary
        lines = [
            "# Session Summary",
            "",
            f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Context Usage",
            f"- Tokens used: {metrics.estimated_total_tokens:,} / {metrics.context_budget:,} ({metrics.context_usage_percent:.1f}%)",
            f"- Files read: {len(metrics.files_read)}",
            f"- Files written: {len(metrics.files_written)}",
            f"- Commands: {metrics.commands_executed}",
            f"- Status: {metrics.status.upper()}",
            "",
        ]

        # Current feature
        if features_data.get("features"):
            in_progress = [f for f in features_data["features"] if f.get("status") == "in_progress"]
            if in_progress:
                feat = in_progress[0]
                lines.extend([
                    "## Current Feature",
                    f"**{feat.get('id', 'N/A')}**: {feat.get('name', 'Unknown')}",
                    "",
                ])
                if feat.get("subtasks"):
                    done = sum(1 for s in feat["subtasks"] if s.get("done"))
                    total = len(feat["subtasks"])
                    lines.append(f"Progress: {done}/{total} subtasks completed")
                    lines.append("")
                    for i, st in enumerate(feat["subtasks"]):
                        status = "x" if st.get("done") else " "
                        lines.append(f"  [{status}] {st.get('name', 'Unknown')}")
                    lines.append("")

        # Progress summary
        if progress_data.get("completed"):
            lines.extend([
                "## Completed This Session",
            ])
            for item in progress_data["completed"][:10]:  # Limit to 10
                lines.append(f"- {item}")
            if len(progress_data["completed"]) > 10:
                lines.append(f"- ... and {len(progress_data['completed']) - 10} more")
            lines.append("")

        if progress_data.get("in_progress"):
            lines.extend([
                "## In Progress",
            ])
            for item in progress_data["in_progress"]:
                lines.append(f"- {item}")
            lines.append("")

        if progress_data.get("blockers") and progress_data["blockers"] != ["None"]:
            lines.extend([
                "## Blockers",
            ])
            for item in progress_data["blockers"]:
                lines.append(f"- {item}")
            lines.append("")

        # Key files modified
        if progress_data.get("files_modified"):
            lines.extend([
                "## Key Files Modified",
            ])
            for item in progress_data["files_modified"][:15]:  # Limit to 15
                lines.append(f"- {item}")
            if len(progress_data["files_modified"]) > 15:
                lines.append(f"- ... and {len(progress_data['files_modified']) - 15} more")
            lines.append("")

        return "\n".join(lines)

    def generate_handoff(self) -> str:
        """Generate a comprehensive handoff document for continuing in a new session.

        This creates a detailed document that includes everything needed to
        continue work in a fresh context window.
        """
        summary = self.generate_summary()
        metrics = self._load_metrics()

        # Load additional context
        config_file = self.project_path / ".claude-harness" / "config.json"
        features_file = self.project_path / ".claude-harness" / "features.json"

        config_data = {}
        features_data = {}

        if config_file.exists():
            import json
            with open(config_file) as f:
                config_data = json.load(f)

        if features_file.exists():
            import json
            with open(features_file) as f:
                features_data = json.load(f)

        lines = [
            "# Session Handoff Document",
            "",
            "**Purpose:** Continue work in a new Claude Code session",
            "",
            f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "---",
            "",
        ]

        # Project context
        if config_data:
            lines.extend([
                "## Project Context",
                "",
                f"**Project:** {config_data.get('project_name', 'Unknown')}",
                "",
            ])
            stack = config_data.get("stack", {})
            if stack:
                lines.append(f"**Stack:** {stack.get('language', 'Unknown')} / {stack.get('framework', 'None')} / {stack.get('database', 'None')}")
                lines.append("")

        # Add summary
        lines.extend([
            "---",
            "",
            summary,
            "",
            "---",
            "",
        ])

        # Pending features
        if features_data.get("features"):
            pending = [f for f in features_data["features"] if f.get("status") == "pending"]
            if pending:
                lines.extend([
                    "## Pending Features (Next Up)",
                    "",
                ])
                for feat in pending[:5]:  # Top 5
                    lines.append(f"- **{feat.get('id')}**: {feat.get('name')}")
                lines.append("")

        # Recommended next steps
        lines.extend([
            "## Recommended Actions for New Session",
            "",
            "1. Run `./scripts/init.sh` to verify environment",
            "2. Run `claude-harness status` to see current state",
            "3. Read this handoff document for context",
            "4. Continue work on the current feature or pick next pending",
            "5. Update progress.md when work is complete",
            "",
        ])

        # Important notes
        if metrics.status in ("warning", "critical"):
            lines.extend([
                "## Important Notes",
                "",
                f"- Previous session hit {metrics.context_usage_percent:.0f}% context usage",
                "- Consider breaking large tasks into smaller chunks",
                "- Use Task agents for code exploration to save context",
                "",
            ])

        return "\n".join(lines)

    def save_handoff(self, filename: str = None) -> str:
        """Generate and save handoff document to a file.

        Args:
            filename: Optional filename (default: handoff_YYYYMMDD_HHMM.md)

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
            filename = f"handoff_{timestamp}.md"

        handoff_dir = self.project_path / ".claude-harness" / "session-history"
        handoff_dir.mkdir(parents=True, exist_ok=True)

        filepath = handoff_dir / filename
        content = self.generate_handoff()

        with open(filepath, "w") as f:
            f.write(content)

        return str(filepath)

    def compress_session(self) -> dict:
        """Compress current session: save handoff, reset metrics, archive progress.

        Returns:
            Dictionary with paths to saved files
        """
        results = {}

        # Save handoff document
        handoff_path = self.save_handoff()
        results["handoff"] = handoff_path

        # Archive current progress
        from .progress_tracker import ProgressTracker
        pt = ProgressTracker(str(self.project_path))
        pt.start_new_session()
        results["progress_archived"] = True

        # Reset context metrics
        self.reset_session()
        results["metrics_reset"] = True

        return results

    # --- Pruning and Optimization Methods ---

    def prune_stale_context(self, max_files: int = 30, max_age_minutes: int = 30) -> dict:
        """Remove stale file references from tracking.

        Prunes tracked files based on:
        - Maximum number of files to keep (most recent)
        - Files older than max_age_minutes are considered stale

        Args:
            max_files: Maximum number of tracked files to retain (default: 30)
            max_age_minutes: Files accessed longer ago than this are stale (default: 30)

        Returns:
            dict with 'pruned_files' list and 'tokens_freed' estimate
        """
        if not self.is_enabled():
            return {"pruned_files": [], "tokens_freed": 0}

        metrics = self._load_metrics()
        pruned_files = []
        tokens_freed = 0

        # Get file stats to determine age (using mtime as proxy)
        file_stats = []
        for filepath in metrics.files_read:
            try:
                path = Path(filepath)
                if path.exists():
                    mtime = path.stat().st_mtime
                    age_minutes = (time.time() - mtime) / 60
                    file_stats.append({
                        "path": filepath,
                        "mtime": mtime,
                        "age_minutes": age_minutes,
                    })
                else:
                    # File no longer exists - mark for removal
                    file_stats.append({
                        "path": filepath,
                        "mtime": 0,
                        "age_minutes": float("inf"),
                    })
            except OSError:
                # Cannot access file - mark for removal
                file_stats.append({
                    "path": filepath,
                    "mtime": 0,
                    "age_minutes": float("inf"),
                })

        # Sort by mtime descending (most recent first)
        file_stats.sort(key=lambda x: x["mtime"], reverse=True)

        # Determine which files to prune
        files_to_keep = []
        for i, fs in enumerate(file_stats):
            # Keep if within max_files limit and not too old
            if i < max_files and fs["age_minutes"] < max_age_minutes:
                files_to_keep.append(fs["path"])
            else:
                pruned_files.append(fs["path"])
                # Estimate tokens freed (assume average file size)
                # Using a conservative estimate of ~1000 tokens per file
                tokens_freed += 1000

        # Update metrics with pruned list
        if pruned_files:
            metrics.files_read = files_to_keep
            # Adjust estimated tokens (rough estimate)
            metrics.estimated_input_tokens = max(
                0, metrics.estimated_input_tokens - tokens_freed
            )
            metrics.estimated_total_tokens = max(
                0, metrics.estimated_total_tokens - tokens_freed
            )
            self._save_metrics()

        return {
            "pruned_files": pruned_files,
            "tokens_freed": tokens_freed,
        }

    def get_compact_summary(self) -> str:
        """Get compact context summary (essential info only, <500 chars).

        Returns a concise one-line summary suitable for status bars,
        log headers, or quick context checks.

        Returns:
            Compact string summary under 500 characters
        """
        if not self.is_enabled():
            return "Context tracking disabled"

        metrics = self._load_metrics()

        # Build compact status indicator
        if metrics.status == "critical":
            status_icon = "[!]"
        elif metrics.status == "warning":
            status_icon = "[*]"
        else:
            status_icon = "[ok]"

        # Get current feature if available
        feature_info = ""
        features_file = self.project_path / ".claude-harness" / "features.json"
        if features_file.exists():
            try:
                import json
                with open(features_file) as f:
                    features_data = json.load(f)
                in_progress = [
                    f for f in features_data.get("features", [])
                    if f.get("status") == "in_progress"
                ]
                if in_progress:
                    feat_id = in_progress[0].get("id", "?")
                    feature_info = f" | Feat:{feat_id}"
            except Exception:
                pass

        # Format remaining tokens in human-readable form
        remaining = metrics.remaining_tokens
        if remaining >= 1000000:
            remaining_str = f"{remaining / 1000000:.1f}M"
        elif remaining >= 1000:
            remaining_str = f"{remaining / 1000:.0f}k"
        else:
            remaining_str = str(remaining)

        # Build the summary (aim for <500 chars)
        summary = (
            f"{status_icon} "
            f"{metrics.context_usage_percent:.0f}% used "
            f"({remaining_str} left) | "
            f"R:{len(metrics.files_read)} W:{len(metrics.files_written)} "
            f"C:{metrics.commands_executed}"
            f"{feature_info}"
        )

        # Truncate if somehow over 500 chars
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return summary

    def categorize_tracked_files(self) -> dict:
        """Categorize tracked files by type.

        Groups files into logical categories for better context awareness:
        - code: Source code files (.py, .js, .ts, etc.)
        - config: Configuration files (.json, .yaml, .toml, etc.)
        - docs: Documentation files (.md, .rst, .txt, etc.)
        - tests: Test files (test_*.py, *_test.py, etc.)
        - other: Everything else

        Returns:
            dict mapping category names to lists of file paths
        """
        metrics = self._load_metrics()

        categories = {
            "code": [],
            "config": [],
            "docs": [],
            "tests": [],
            "other": [],
        }

        # Extension mappings
        code_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
            ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".sh", ".bash", ".ps1", ".sql",
        }

        config_extensions = {
            ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg",
            ".env", ".properties", ".conf",
        }

        doc_extensions = {
            ".md", ".rst", ".txt", ".adoc", ".html", ".htm",
        }

        # Test file patterns (case-insensitive checks)
        test_patterns = ("test_", "_test.", "tests/", "/tests/", "spec_", "_spec.")

        for filepath in metrics.files_read:
            path = Path(filepath)
            suffix = path.suffix.lower()
            name_lower = path.name.lower()
            filepath_lower = filepath.lower()

            # Check for test files first (they may be .py but are tests)
            is_test = any(pattern in filepath_lower for pattern in test_patterns)

            if is_test:
                categories["tests"].append(filepath)
            elif suffix in code_extensions:
                categories["code"].append(filepath)
            elif suffix in config_extensions:
                categories["config"].append(filepath)
            elif suffix in doc_extensions:
                categories["docs"].append(filepath)
            else:
                categories["other"].append(filepath)

        return categories


def get_context_tracker(project_path: str = ".") -> ContextTracker:
    """Get a context tracker instance."""
    return ContextTracker(project_path)
