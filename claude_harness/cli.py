"""CLI interface for Claude Harness.

Commands:
- init: Initialize harness in a project
- status: Show current status (features, progress)
- feature: Manage features (add, start, complete, list)
- progress: Manage session progress
- e2e: E2E testing commands
"""

import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .initializer import initialize_project
from .feature_manager import FeatureManager
from .progress_tracker import ProgressTracker
from .context_tracker import ContextTracker
from .detector import detect_stack


console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="claude-harness")
@click.pass_context
def main(ctx):
    """Claude Harness - AI Workflow Optimization Tool.

    Optimize your Claude Code sessions with:
    - Session continuity (progress tracking)
    - Feature management (one feature at a time)
    - Automated startup rituals
    - Git safety hooks
    - E2E testing with Playwright
    """
    ctx.ensure_object(dict)
    ctx.obj["project_path"] = str(Path.cwd())


# --- Init Command ---


@main.command()
@click.option(
    "--path",
    "-p",
    default=".",
    help="Project path (default: current directory)",
)
@click.option(
    "--non-interactive",
    "-y",
    is_flag=True,
    help="Use detected/default values without prompting",
)
def init(path: str, non_interactive: bool):
    """Initialize Claude Harness in a project.

    This will:
    - Detect your project stack
    - Ask configuration questions
    - Generate harness files (.claude-harness/)
    - Create init.sh startup script
    - Set up hooks and E2E testing
    """
    project_path = Path(path).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Path does not exist: {project_path}[/red]")
        sys.exit(1)

    # Check if already initialized
    harness_dir = project_path / ".claude-harness"
    if harness_dir.exists():
        if non_interactive:
            console.print("[yellow]Harness already initialized. Reinitializing in non-interactive mode...[/yellow]")
        elif not click.confirm(
            "Harness already initialized. Reinitialize?", default=False
        ):
            console.print("[yellow]Aborted.[/yellow]")
            return

    try:
        config = initialize_project(str(project_path), non_interactive=non_interactive)
        console.print(f"\n[green]Harness initialized for: {config.project_name}[/green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Initialization cancelled.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during initialization: {e}[/red]")
        sys.exit(1)


# --- Status Command ---


@main.command()
@click.option("--compact", "-c", is_flag=True, help="Show compact status")
@click.pass_context
def status(ctx, compact: bool):
    """Show current harness status.

    Displays:
    - Current feature in progress
    - Session progress summary
    - Context usage (if enabled)
    """
    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    # Show context status first (compact always)
    ct = ContextTracker(project_path)
    if ct.is_enabled():
        ct.show_status(compact=True)

    # Show feature status
    fm = FeatureManager(project_path)
    fm.show_status()

    # Show progress
    pt = ProgressTracker(project_path)
    pt.show_progress()


# --- Feature Commands ---


@main.group()
@click.pass_context
def feature(ctx):
    """Manage features and tasks."""
    pass


@feature.command("list")
@click.option("--all", "-a", "show_all", is_flag=True, help="Include completed features")
@click.option("--status", "-s", type=click.Choice(["pending", "in_progress", "blocked"]))
@click.pass_context
def feature_list(ctx, show_all: bool, status: str):
    """List features."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    if status:
        features = fm.list_features(status=status)
        for f in features:
            console.print(f"  {f.id}: {f.name} [{f.status}]")
    else:
        fm.show_table(include_completed=show_all)


@feature.command("info")
@click.argument("feature_id")
@click.pass_context
def feature_info(ctx, feature_id: str):
    """Show detailed information about a feature."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.get_feature(feature_id)

    if not feature:
        console.print(f"[red]Feature not found: {feature_id}[/red]")
        return

    # Header
    status_colors = {
        "pending": "blue",
        "in_progress": "yellow",
        "completed": "green",
        "blocked": "red",
    }
    status_color = status_colors.get(feature.status, "white")

    console.print()
    console.print(f"[bold]{feature.id}[/bold]: {feature.name}")
    console.print(f"  Status: [{status_color}]{feature.status}[/{status_color}]")
    console.print(f"  Priority: {feature.priority}")

    # Dates
    if feature.created_at:
        console.print(f"  Created: {feature.created_at[:16]}")
    if feature.completed_at:
        console.print(f"  Completed: {feature.completed_at[:16]}")

    # Blocked reason
    if feature.blocked_reason:
        console.print(f"  [red]Blocked: {feature.blocked_reason}[/red]")

    # Tests and E2E status
    tests_mark = "[green]Yes[/green]" if feature.tests_passing else "[red]No[/red]"
    e2e_mark = "[green]Yes[/green]" if feature.e2e_validated else "[red]No[/red]"
    console.print(f"  Tests Passing: {tests_mark}")
    console.print(f"  E2E Validated: {e2e_mark}")

    # Subtasks
    if feature.subtasks:
        console.print()
        console.print(f"  [bold]Subtasks ({feature.subtask_progress}):[/bold]")
        for i, subtask in enumerate(feature.subtasks):
            mark = "[green]x[/green]" if subtask.done else "[ ]"
            console.print(f"    {i}. {mark} {subtask.name}")

    # Notes
    if feature.notes:
        console.print()
        console.print(f"  [bold]Notes:[/bold]")
        console.print(f"    {feature.notes}")

    console.print()


@feature.command("add")
@click.argument("name")
@click.option("--priority", "-p", default=0, help="Priority (lower = higher priority)")
@click.option("--subtask", "-s", multiple=True, help="Add subtasks")
@click.option("--notes", "-n", default="", help="Notes")
@click.pass_context
def feature_add(ctx, name: str, priority: int, subtask: tuple, notes: str):
    """Add a new feature."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.add_feature(
        name=name,
        priority=priority,
        subtasks=list(subtask),
        notes=notes,
    )

    console.print(f"[green]Added feature: {feature.id} - {feature.name}[/green]")


@feature.command("start")
@click.argument("feature_id")
@click.pass_context
def feature_start(ctx, feature_id: str):
    """Start working on a feature (marks as in_progress)."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.start_feature(feature_id)

    if feature:
        console.print(f"[green]Started: {feature.id} - {feature.name}[/green]")

        # Also update progress
        pt = ProgressTracker(project_path)
        pt.add_in_progress(f"{feature.id}: {feature.name}")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("complete")
@click.argument("feature_id")
@click.pass_context
def feature_complete(ctx, feature_id: str):
    """Mark a feature as completed."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.complete_feature(feature_id)

    if feature:
        console.print(f"[green]Completed: {feature.id} - {feature.name}[/green]")

        # Also update progress
        pt = ProgressTracker(project_path)
        pt.mark_completed(f"{feature.id}: {feature.name}")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("block")
@click.argument("feature_id")
@click.option("--reason", "-r", required=True, help="Reason for blocking")
@click.pass_context
def feature_block(ctx, feature_id: str, reason: str):
    """Mark a feature as blocked."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.update_status(feature_id, "blocked", blocked_reason=reason)

    if feature:
        console.print(f"[yellow]Blocked: {feature.id} - {feature.name}[/yellow]")
        console.print(f"[yellow]Reason: {reason}[/yellow]")

        # Add blocker to progress
        pt = ProgressTracker(project_path)
        pt.add_blocker(f"{feature.id}: {reason}")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("unblock")
@click.argument("feature_id")
@click.pass_context
def feature_unblock(ctx, feature_id: str):
    """Unblock a blocked feature (moves back to pending)."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    # Get the feature first to check if it's actually blocked
    feature = fm.get_feature(feature_id)

    if not feature:
        console.print(f"[red]Feature not found: {feature_id}[/red]")
        return

    if feature.status != "blocked":
        console.print(f"[yellow]Feature {feature_id} is not blocked (status: {feature.status})[/yellow]")
        return

    # Move from blocked to pending
    feature = fm.update_status(feature_id, "pending")

    if feature:
        console.print(f"[green]Unblocked: {feature.id} - {feature.name}[/green]")
        console.print("[dim]Feature moved back to pending status[/dim]")


@feature.command("subtask")
@click.argument("feature_id")
@click.argument("subtask_name")
@click.pass_context
def feature_subtask(ctx, feature_id: str, subtask_name: str):
    """Add a subtask to a feature."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.add_subtask(feature_id, subtask_name)

    if feature:
        console.print(f"[green]Added subtask to {feature.id}: {subtask_name}[/green]")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("done")
@click.argument("feature_id")
@click.argument("subtask_index", type=int)
@click.pass_context
def feature_done(ctx, feature_id: str, subtask_index: int):
    """Mark a subtask as done (0-indexed)."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.complete_subtask(feature_id, subtask_index)

    if feature:
        if subtask_index < len(feature.subtasks):
            subtask = feature.subtasks[subtask_index]
            console.print(f"[green]Completed subtask: {subtask.name}[/green]")
        else:
            console.print(f"[red]Subtask index out of range[/red]")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("tests")
@click.argument("feature_id")
@click.option("--passing/--failing", default=True, help="Mark tests as passing or failing")
@click.pass_context
def feature_tests(ctx, feature_id: str, passing: bool):
    """Mark feature tests as passing/failing."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.set_tests_passing(feature_id, passing)

    if feature:
        status = "passing" if passing else "failing"
        console.print(f"[green]Marked {feature.id} tests as {status}[/green]")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("e2e")
@click.argument("feature_id")
@click.option("--validated/--not-validated", default=True, help="Mark E2E as validated")
@click.pass_context
def feature_e2e(ctx, feature_id: str, validated: bool):
    """Mark feature E2E validation status."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.set_e2e_validated(feature_id, validated)

    if feature:
        status = "validated" if validated else "not validated"
        console.print(f"[green]Marked {feature.id} E2E as {status}[/green]")
    else:
        console.print(f"[red]Feature not found: {feature_id}[/red]")


@feature.command("phase")
@click.argument("phase_name")
@click.pass_context
def feature_phase(ctx, phase_name: str):
    """Set current phase name."""
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    fm.set_current_phase(phase_name)
    console.print(f"[green]Set phase to: {phase_name}[/green]")


# --- Progress Commands ---


@main.group()
@click.pass_context
def progress(ctx):
    """Manage session progress."""
    pass


@progress.command("show")
@click.option("--raw", is_flag=True, help="Show raw markdown content")
@click.pass_context
def progress_show(ctx, raw: bool):
    """Show current session progress."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    if raw:
        pt.show_raw()
    else:
        pt.show_progress()


@progress.command("completed")
@click.argument("item")
@click.pass_context
def progress_completed(ctx, item: str):
    """Add a completed item."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    pt.add_completed(item)
    console.print(f"[green]Added to completed: {item}[/green]")


@progress.command("wip")
@click.argument("item")
@click.pass_context
def progress_wip(ctx, item: str):
    """Add a work-in-progress item."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    pt.add_in_progress(item)
    console.print(f"[yellow]Added to in-progress: {item}[/yellow]")


@progress.command("blocker")
@click.argument("item")
@click.pass_context
def progress_blocker(ctx, item: str):
    """Add a blocker."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    pt.add_blocker(item)
    console.print(f"[red]Added blocker: {item}[/red]")


@progress.command("file")
@click.argument("filepath")
@click.pass_context
def progress_file(ctx, filepath: str):
    """Add a modified file."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    pt.add_file_modified(filepath)
    console.print(f"[blue]Added modified file: {filepath}[/blue]")


@progress.command("new-session")
@click.pass_context
def progress_new_session(ctx):
    """Start a new session (archives previous)."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    pt.start_new_session()
    console.print("[green]Started new session. Previous session archived.[/green]")


@progress.command("update")
@click.option("--completed", "-c", multiple=True, help="Completed items")
@click.option("--wip", "-w", multiple=True, help="Work in progress items")
@click.option("--blocker", "-b", multiple=True, help="Blockers")
@click.option("--next", "-n", "next_steps", multiple=True, help="Next steps")
@click.option("--note", multiple=True, help="Context notes")
@click.pass_context
def progress_update(ctx, completed, wip, blocker, next_steps, note):
    """Update multiple progress fields at once."""
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    pt.update_progress(
        completed=list(completed) if completed else None,
        in_progress=list(wip) if wip else None,
        blockers=list(blocker) if blocker else None,
        next_steps=list(next_steps) if next_steps else None,
        context_notes=list(note) if note else None,
        archive_previous=False,
    )

    console.print("[green]Progress updated.[/green]")


# --- Detect Command ---


@main.command()
@click.option("--path", "-p", default=".", help="Project path")
def detect(path: str):
    """Detect project stack without initializing.

    Useful for previewing what will be detected.
    """
    project_path = Path(path).resolve()

    console.print(f"[yellow]Detecting stack in: {project_path}[/yellow]\n")

    detected = detect_stack(str(project_path))

    console.print("[bold]Detection Results:[/bold]")
    console.print(f"  Language: {detected.language or 'Unknown'}")
    console.print(f"  Framework: {detected.framework or 'None'}")
    console.print(f"  Database: {detected.database or 'None'}")
    console.print(f"  ORM: {detected.orm or 'None'}")
    console.print(f"  Test Framework: {detected.test_framework or 'Unknown'}")
    console.print(f"  Source Dir: {detected.source_directory or '.'}")
    console.print(f"  Git: {'Yes' if detected.has_git else 'No'}")
    console.print(f"  Docker: {'Yes' if detected.has_docker else 'No'}")
    console.print(f"  Kubernetes: {'Yes' if detected.has_kubernetes else 'No'}")
    console.print(f"  CI: {detected.ci_provider or 'None'}")
    console.print(f"  Existing CLAUDE.md: {'Yes' if detected.has_claude_md else 'No'}")
    console.print(f"\n  Confidence: {detected.confidence * 100:.0f}%")

    if detected.detection_notes:
        console.print("\n[bold]Notes:[/bold]")
        for note in detected.detection_notes:
            console.print(f"  - {note}")


# --- E2E Commands ---


@main.group()
@click.pass_context
def e2e(ctx):
    """E2E testing with Playwright."""
    pass


@e2e.command("install")
def e2e_install():
    """Install Playwright and browsers."""
    import subprocess

    console.print("[yellow]Installing Playwright...[/yellow]")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            check=True,
        )
        console.print("[green]Playwright installed.[/green]")

        console.print("[yellow]Installing browsers...[/yellow]")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install"],
            check=True,
        )
        console.print("[green]Browsers installed.[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@e2e.command("run")
@click.option("--headed", is_flag=True, help="Run with visible browser")
@click.option("--slow", is_flag=True, help="Run in slow motion")
@click.pass_context
def e2e_run(ctx, headed: bool, slow: bool):
    """Run E2E tests."""
    import subprocess

    project_path = ctx.obj["project_path"]
    e2e_dir = Path(project_path) / "e2e"

    if not e2e_dir.exists():
        console.print("[red]E2E directory not found. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    cmd = ["pytest", str(e2e_dir), "-v"]

    if headed:
        cmd.extend(["--headed"])
    if slow:
        cmd.extend(["--slowmo", "500"])

    console.print(f"[yellow]Running: {' '.join(cmd)}[/yellow]")

    try:
        subprocess.run(cmd, check=True, cwd=project_path)
    except subprocess.CalledProcessError:
        sys.exit(1)


@e2e.command("generate")
@click.argument("feature_id")
@click.pass_context
def e2e_generate(ctx, feature_id: str):
    """Generate E2E test skeleton for a feature."""
    project_path = ctx.obj["project_path"]

    fm = FeatureManager(project_path)
    feature = fm.get_feature(feature_id)

    if not feature:
        console.print(f"[red]Feature not found: {feature_id}[/red]")
        sys.exit(1)

    # Generate test file
    e2e_tests_dir = Path(project_path) / "e2e" / "tests"
    e2e_tests_dir.mkdir(parents=True, exist_ok=True)

    test_filename = f"test_{feature_id.lower().replace('-', '_')}.py"
    test_path = e2e_tests_dir / test_filename

    # Generate test content
    test_content = f'''"""E2E tests for feature: {feature.id} - {feature.name}"""
import pytest
from playwright.sync_api import Page, expect


class Test{feature.id.replace("-", "")}:
    """E2E tests for {feature.name}."""

'''

    # Add test for each subtask
    if feature.subtasks:
        for i, subtask in enumerate(feature.subtasks):
            test_name = subtask.name.lower().replace(" ", "_").replace("-", "_")
            test_name = "".join(c for c in test_name if c.isalnum() or c == "_")

            test_content += f'''    def test_{test_name}(self, page: Page):
        """Test: {subtask.name}"""
        # TODO: Implement test for: {subtask.name}
        # page.goto("/...")
        # expect(page.locator("...")).to_be_visible()
        pass

'''
    else:
        test_content += f'''    def test_{feature.id.lower().replace("-", "_")}_basic(self, page: Page):
        """Basic test for {feature.name}."""
        # TODO: Implement E2E test
        # page.goto("/...")
        # expect(page.locator("...")).to_be_visible()
        pass
'''

    with open(test_path, "w") as f:
        f.write(test_content)

    console.print(f"[green]Generated: {test_path}[/green]")


# --- Context Commands ---


@main.group()
@click.pass_context
def context(ctx):
    """Context/token usage tracking."""
    pass


@context.command("show")
@click.option("--full", "-f", is_flag=True, help="Show full details")
@click.pass_context
def context_show(ctx, full: bool):
    """Show context usage status."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    if not ct.is_enabled():
        console.print("[yellow]Context tracking is disabled in config.[/yellow]")
        return

    ct.show_status(compact=not full)


@context.command("reset")
@click.pass_context
def context_reset(ctx):
    """Reset context metrics for new session."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    ct.reset_session()
    console.print("[green]Context metrics reset for new session.[/green]")


@context.command("track-file")
@click.argument("filepath")
@click.argument("chars", type=int)
@click.option("--write", "-w", is_flag=True, help="Track as write (default: read)")
@click.pass_context
def context_track_file(ctx, filepath: str, chars: int, write: bool):
    """Manually track a file operation (for hooks)."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    if write:
        ct.track_file_write(filepath, chars)
        console.print(f"[dim]Tracked file write: {filepath} ({chars} chars)[/dim]")
    else:
        ct.track_file_read(filepath, chars)
        console.print(f"[dim]Tracked file read: {filepath} ({chars} chars)[/dim]")


@context.command("track-command")
@click.argument("command")
@click.option("--output-chars", "-o", default=0, type=int, help="Output character count")
@click.pass_context
def context_track_command(ctx, command: str, output_chars: int):
    """Manually track a command execution (for hooks)."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    ct.track_command(command, output_chars)
    console.print(f"[dim]Tracked command: {command[:50]}...[/dim]")


@context.command("start-task")
@click.argument("task_id")
@click.pass_context
def context_start_task(ctx, task_id: str):
    """Start tracking a specific task."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    ct.start_task(task_id)
    console.print(f"[green]Started tracking task: {task_id}[/green]")


@context.command("end-task")
@click.argument("task_id")
@click.pass_context
def context_end_task(ctx, task_id: str):
    """End tracking a specific task."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    ct.end_task(task_id)
    console.print(f"[green]Ended tracking task: {task_id}[/green]")


@context.command("budget")
@click.argument("tokens", type=int)
@click.pass_context
def context_budget(ctx, tokens: int):
    """Set context budget (tokens)."""
    import json

    project_path = ctx.obj["project_path"]
    config_file = Path(project_path) / ".claude-harness" / "config.json"

    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)

        config.setdefault("context_tracking", {})["budget"] = tokens

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        console.print(f"[green]Set context budget to {tokens:,} tokens[/green]")
    else:
        console.print("[red]Config not found. Run 'claude-harness init' first.[/red]")


@context.command("metadata")
@click.pass_context
def context_metadata(ctx):
    """Output context metadata string (for embedding in outputs)."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    metadata = ct.get_metadata_string()
    if metadata:
        console.print(metadata)
    else:
        console.print("[dim]Context tracking disabled[/dim]")


@context.command("summary")
@click.pass_context
def context_summary(ctx):
    """Generate a compressed session summary."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    summary = ct.generate_summary()
    console.print(summary)


@context.command("handoff")
@click.option("--save", "-s", is_flag=True, help="Save to file in session-history/")
@click.option("--filename", "-f", default=None, help="Custom filename")
@click.pass_context
def context_handoff(ctx, save: bool, filename: str):
    """Generate a handoff document for continuing in a new session.

    Use this when context is filling up and you need to continue
    work in a fresh Claude Code session.
    """
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    if save:
        filepath = ct.save_handoff(filename)
        console.print(f"[green]Handoff document saved to: {filepath}[/green]")
        console.print("[dim]Share this file with your next session for seamless continuation.[/dim]")
    else:
        handoff = ct.generate_handoff()
        console.print(handoff)


@context.command("compress")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def context_compress(ctx, yes: bool):
    """Compress current session and prepare for handoff.

    This will:
    1. Generate and save a handoff document
    2. Archive current progress
    3. Reset context metrics

    Use this when ending a long session or hitting context limits.
    """
    project_path = ctx.obj["project_path"]

    if not yes:
        console.print("[yellow]This will:[/yellow]")
        console.print("  1. Save a handoff document to session-history/")
        console.print("  2. Archive current progress.md")
        console.print("  3. Reset context metrics")
        console.print()
        if not click.confirm("Continue?", default=True):
            console.print("[yellow]Aborted.[/yellow]")
            return

    ct = ContextTracker(project_path)
    results = ct.compress_session()

    console.print()
    console.print("[green]Session compressed successfully![/green]")
    console.print(f"  Handoff saved: {results['handoff']}")
    console.print("  Progress archived: Yes")
    console.print("  Metrics reset: Yes")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Start a new Claude Code session")
    console.print(f"  2. Read the handoff document: {results['handoff']}")
    console.print("  3. Run `./scripts/init.sh` to verify environment")


# --- Run Commands ---


@main.command("run")
@click.pass_context
def run_init(ctx):
    """Run init.sh startup script."""
    import subprocess

    project_path = ctx.obj["project_path"]
    init_script = Path(project_path) / "scripts" / "init.sh"

    if not init_script.exists():
        console.print("[red]init.sh not found. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    try:
        subprocess.run(["bash", str(init_script)], cwd=project_path)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
