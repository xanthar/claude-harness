"""CLI interface for Claude Harness.

Commands:
- init: Initialize harness in a project
- status: Show current status (features, progress)
- feature: Manage features (add, start, complete, list)
- progress: Manage session progress
- e2e: E2E testing commands
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .initializer import initialize_project
from .feature_manager import FeatureManager
from .progress_tracker import ProgressTracker
from .context_tracker import ContextTracker
from .delegation_manager import DelegationManager, DelegationRule
from .detector import detect_stack
from .orchestration_engine import OrchestrationEngine, get_orchestration_engine
from .file_filter import FileFilter
from .output_compressor import OutputCompressor
from .exploration_cache import ExplorationCache, get_exploration_cache
from .file_read_optimizer import FileReadOptimizer
from .lazy_loader import LazyContextLoader, get_lazy_loader
from .discoveries import DiscoveryTracker, get_discovery_tracker


console = Console()


def _update_claude_md_from_config(project_path: Path):
    """Helper to update CLAUDE.md after config changes."""
    from .initializer import Initializer, HarnessConfig

    harness_dir = project_path / ".claude-harness"
    config_file = harness_dir / "config.json"

    config_data = json.loads(config_file.read_text())

    config = HarnessConfig(
        project_name=config_data.get("project_name", project_path.name),
        project_description=config_data.get("project_description", ""),
        language=config_data.get("stack", {}).get("language", "python"),
        framework=config_data.get("stack", {}).get("framework"),
        database=config_data.get("stack", {}).get("database"),
        test_framework=config_data.get("testing", {}).get("framework", "pytest"),
        venv_path=config_data.get("paths", {}).get("venv", ".venv"),
        port=config_data.get("startup", {}).get("port", 8000),
        health_endpoint=config_data.get("startup", {}).get("health_endpoint", "/health"),
        start_command=config_data.get("startup", {}).get("start_command", "python main.py"),
        protected_branches=config_data.get("git", {}).get("protected_branches", ["main", "master"]),
        branch_prefixes=config_data.get("git", {}).get("branch_prefixes", ["feat/", "fix/", "chore/", "docs/", "refactor/"]),
        e2e_enabled=config_data.get("e2e", {}).get("enabled", False),
        e2e_base_url=config_data.get("e2e", {}).get("base_url", f"http://localhost:{config_data.get('startup', {}).get('port', 8000)}"),
        unit_test_command=config_data.get("testing", {}).get("unit_command", "pytest tests/unit/ -v"),
        e2e_test_command=config_data.get("testing", {}).get("e2e_command", "pytest e2e/ -v"),
        coverage_threshold=config_data.get("testing", {}).get("coverage_threshold", 80),
        blocked_actions=config_data.get("blocked_actions", []),
        delegation_enabled=config_data.get("delegation", {}).get("enabled", False),
        orchestration_enabled=config_data.get("orchestration", {}).get("enabled", False),
        discoveries_enabled=config_data.get("discoveries", {}).get("enabled", False),
        documentation_enabled=config_data.get("documentation", {}).get("enabled", True),
        documentation_trigger=config_data.get("documentation", {}).get("trigger", "feature_complete"),
    )

    initializer = Initializer(str(project_path), config=config)
    initializer._update_claude_md()


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


# --- Refresh Command ---


@main.command()
@click.option(
    "--path",
    "-p",
    default=".",
    help="Project path (default: current directory)",
)
@click.option(
    "--update-claude-md",
    is_flag=True,
    help="Also update .claude/CLAUDE.md with latest harness section",
)
@click.pass_context
def refresh(ctx, path: str, update_claude_md: bool):
    """Refresh harness scripts without losing data.

    Regenerates:
    - scripts/init.sh (startup script)
    - .claude-harness/hooks/ (git safety hooks)

    Optionally (with --update-claude-md):
    - .claude/CLAUDE.md (harness integration section)

    Preserves:
    - features.json (feature tracking)
    - progress.md (session progress)
    - config.json (configuration)
    - context_metrics.json (context tracking)

    Use this after upgrading claude-harness to get latest script improvements.
    """
    from .initializer import Initializer, HarnessConfig
    import json

    project_path = Path(path).resolve()
    harness_dir = project_path / ".claude-harness"
    config_file = harness_dir / "config.json"

    if not harness_dir.exists() or not config_file.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    try:
        # Load existing config
        with open(config_file) as f:
            config_data = json.load(f)

        # Create HarnessConfig from existing data
        config = HarnessConfig(
            project_name=config_data.get("project_name", project_path.name),
            project_description=config_data.get("project_description", ""),
            language=config_data.get("stack", {}).get("language", "python"),
            framework=config_data.get("stack", {}).get("framework"),
            database=config_data.get("stack", {}).get("database"),
            test_framework=config_data.get("testing", {}).get("framework", "pytest"),
            venv_path=config_data.get("paths", {}).get("venv", ".venv"),
            port=config_data.get("startup", {}).get("port", 8000),
            health_endpoint=config_data.get("startup", {}).get("health_endpoint", "/health"),
            start_command=config_data.get("startup", {}).get("start_command", "python main.py"),
            protected_branches=config_data.get("git", {}).get("protected_branches", ["main", "master"]),
            branch_prefixes=config_data.get("git", {}).get("branch_prefixes", ["feat/", "fix/", "chore/", "docs/", "refactor/"]),
            e2e_enabled=config_data.get("e2e", {}).get("enabled", False),
            e2e_base_url=config_data.get("e2e", {}).get("base_url", f"http://localhost:{config_data.get('startup', {}).get('port', 8000)}"),
            # Testing config
            unit_test_command=config_data.get("testing", {}).get("unit_command", "pytest tests/unit/ -v"),
            e2e_test_command=config_data.get("testing", {}).get("e2e_command", "pytest e2e/ -v"),
            coverage_threshold=config_data.get("testing", {}).get("coverage_threshold", 80),
            # Blocked actions
            blocked_actions=config_data.get("blocked_actions", [
                "commit_to_protected_branch",
                "push_to_protected_branch_without_confirmation",
                "delete_backup_branches",
            ]),
            # Delegation
            delegation_enabled=config_data.get("delegation", {}).get("enabled", False),
            # Orchestration
            orchestration_enabled=config_data.get("orchestration", {}).get("enabled", False),
            # Discoveries
            discoveries_enabled=config_data.get("discoveries", {}).get("enabled", False),
            # Documentation
            documentation_enabled=config_data.get("documentation", {}).get("enabled", True),
            documentation_trigger=config_data.get("documentation", {}).get("trigger", "feature_complete"),
        )

        # Initialize with existing config
        initializer = Initializer(str(project_path), config=config)

        # Only regenerate scripts (not data files)
        console.print("[blue]Refreshing harness scripts...[/blue]")

        # Regenerate init.sh
        initializer._write_init_script()
        console.print("  [green]Refreshed:[/green] scripts/init.sh")

        # Regenerate hooks
        initializer._write_hooks()
        console.print("  [green]Refreshed:[/green] .claude-harness/hooks/")

        # Regenerate PowerShell init if on Windows or if it exists
        ps_init = project_path / "scripts" / "init.ps1"
        if ps_init.exists() or sys.platform == "win32":
            initializer._write_init_powershell()
            console.print("  [green]Refreshed:[/green] scripts/init.ps1")

        # Update .gitignore for session files
        initializer._update_gitignore()

        # Optionally update CLAUDE.md
        if update_claude_md:
            initializer._update_claude_md()

        console.print("\n[green]Harness scripts refreshed successfully![/green]")
        console.print("[dim]Data files (features.json, progress.md, config.json) were preserved.[/dim]")

    except Exception as e:
        console.print(f"[red]Error refreshing harness: {e}[/red]")
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
@click.option("--priority", "-p", type=int, help="Filter by priority level")
@click.option("--search", "-q", help="Search in feature names (case-insensitive)")
@click.pass_context
def feature_list(ctx, show_all: bool, status: str, priority: int, search: str):
    """List features with optional filters.

    Examples:
        claude-harness feature list
        claude-harness feature list --status pending
        claude-harness feature list --priority 1
        claude-harness feature list --search auth
        claude-harness feature list -s pending -p 1 -q login
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    # If any filter is applied, use filtered list view
    if status or priority is not None or search:
        features = fm.list_features(status=status)

        # Apply priority filter
        if priority is not None:
            features = [f for f in features if f.priority == priority]

        # Apply search filter
        if search:
            search_lower = search.lower()
            features = [f for f in features if search_lower in f.name.lower()]

        if not features:
            console.print("[yellow]No features match the filters[/yellow]")
            return

        console.print()
        for f in features:
            status_colors = {
                "pending": "blue",
                "in_progress": "yellow",
                "completed": "green",
                "blocked": "red",
            }
            color = status_colors.get(f.status, "white")
            console.print(f"  {f.id}: {f.name} [{color}]{f.status}[/{color}] (P{f.priority})")
        console.print(f"\n[dim]{len(features)} feature(s) found[/dim]")
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
@click.option("--subtask", "-s", multiple=True, help="Add subtask (can be used multiple times)")
@click.option("--notes", "-n", default="", help="Notes")
@click.pass_context
def feature_add(ctx, name: str, priority: int, subtask: tuple, notes: str):
    """Add a new feature.

    Examples:
        claude-harness feature add "User login"
        claude-harness feature add "Auth system" -p 1 -s "Design API" -s "Implement"
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    # BUG-003 fix: Handle validation error for empty names
    try:
        feature = fm.add_feature(
            name=name,
            priority=priority,
            subtasks=list(subtask),
            notes=notes,
        )
        console.print(f"[green]Added feature: {feature.id} - {feature.name}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@feature.command("start")
@click.argument("feature_ids", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation for multiple features")
@click.pass_context
def feature_start(ctx, feature_ids: tuple, yes: bool):
    """Start working on feature(s) (marks as in_progress).

    Can accept multiple feature IDs for bulk operations.

    Examples:
        claude-harness feature start F-001
        claude-harness feature start F-001 F-002 F-003
        claude-harness feature start F-001 F-002 --yes
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)
    pt = ProgressTracker(project_path)

    # BUG-004 fix: Check for completed features and warn
    completed_features = []
    for feature_id in feature_ids:
        feature = fm.get_feature(feature_id)
        if feature and feature.status == "completed":
            completed_features.append(feature)

    if completed_features and not yes:
        console.print("[yellow]Warning: The following features are already completed:[/yellow]")
        for f in completed_features:
            console.print(f"  {f.id}: {f.name}")
        console.print("[dim]Restarting will reset their test status.[/dim]")
        if not click.confirm("Continue anyway?"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Warn about multiple features (harness philosophy: one at a time)
    if len(feature_ids) > 1 and not yes:
        console.print(f"[yellow]Warning: Starting {len(feature_ids)} features at once.[/yellow]")
        console.print("[dim]The harness philosophy recommends ONE feature at a time.[/dim]")
        if not click.confirm("Continue anyway?"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    started = []
    not_found = []

    # BUG-001 fix: Use bulk method for multiple features
    if len(feature_ids) > 1:
        started = fm.start_features_bulk(list(feature_ids))
        started_ids = {f.id for f in started}
        not_found = [fid for fid in feature_ids if fid not in started_ids]
    else:
        # Single feature - use standard method (resets others)
        for feature_id in feature_ids:
            feature = fm.start_feature(feature_id)
            if feature:
                started.append(feature)
            else:
                not_found.append(feature_id)

    # Update progress tracking
    for feature in started:
        pt.add_in_progress(f"{feature.id}: {feature.name}")

    # Report results
    for feature in started:
        console.print(f"[green]Started: {feature.id} - {feature.name}[/green]")

    for fid in not_found:
        console.print(f"[red]Feature not found: {fid}[/red]")

    if len(started) > 1:
        console.print(f"\n[dim]{len(started)} feature(s) started[/dim]")


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
@click.argument("feature_ids", nargs=-1, required=True)
@click.option("--reason", "-r", required=True, help="Reason for blocking")
@click.pass_context
def feature_block(ctx, feature_ids: tuple, reason: str):
    """Mark feature(s) as blocked.

    Can accept multiple feature IDs for bulk operations.

    Examples:
        claude-harness feature block F-001 -r "Waiting for API"
        claude-harness feature block F-001 F-002 -r "Blocked by dependency"
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)
    pt = ProgressTracker(project_path)

    blocked = []
    not_found = []

    for feature_id in feature_ids:
        feature = fm.update_status(feature_id, "blocked", blocked_reason=reason)
        if feature:
            blocked.append(feature)
            pt.add_blocker(f"{feature.id}: {reason}")
        else:
            not_found.append(feature_id)

    # Report results
    for feature in blocked:
        console.print(f"[yellow]Blocked: {feature.id} - {feature.name}[/yellow]")

    if blocked:
        console.print(f"[yellow]Reason: {reason}[/yellow]")

    for fid in not_found:
        console.print(f"[red]Feature not found: {fid}[/red]")

    if len(blocked) > 1:
        console.print(f"\n[dim]{len(blocked)} feature(s) blocked[/dim]")


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
@click.argument("subtask_identifier")
@click.pass_context
def feature_done(ctx, feature_id: str, subtask_identifier: str):
    """Mark a subtask as done by index (0-indexed) or name.

    Examples:
        claude-harness feature done F-001 0
        claude-harness feature done F-001 "Login form"
        claude-harness feature done F-001 login  # Fuzzy match
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    # First get the feature to check subtasks
    feature = fm.get_feature(feature_id)
    if not feature:
        console.print(f"[red]Feature not found: {feature_id}[/red]")
        return

    if not feature.subtasks:
        console.print(f"[yellow]Feature {feature_id} has no subtasks[/yellow]")
        return

    # Determine if identifier is an index or name
    subtask_index = None

    # Try to parse as integer first
    try:
        subtask_index = int(subtask_identifier)
        if subtask_index < 0 or subtask_index >= len(feature.subtasks):
            console.print(f"[red]Subtask index {subtask_index} out of range (0-{len(feature.subtasks)-1})[/red]")
            return
    except ValueError:
        # Not an integer, search by name
        search_term = subtask_identifier.lower()
        matches = []

        for i, subtask in enumerate(feature.subtasks):
            if search_term == subtask.name.lower():
                # Exact match
                subtask_index = i
                break
            elif search_term in subtask.name.lower():
                # Partial match
                matches.append((i, subtask.name))

        if subtask_index is None:
            if len(matches) == 1:
                subtask_index = matches[0][0]
            elif len(matches) > 1:
                console.print(f"[yellow]Multiple subtasks match '{subtask_identifier}':[/yellow]")
                for idx, name in matches:
                    console.print(f"  {idx}. {name}")
                console.print("[dim]Use the index number to specify which one[/dim]")
                return
            else:
                console.print(f"[red]No subtask found matching '{subtask_identifier}'[/red]")
                console.print("[dim]Available subtasks:[/dim]")
                for i, subtask in enumerate(feature.subtasks):
                    mark = "[green]x[/green]" if subtask.done else "[ ]"
                    console.print(f"  {i}. {mark} {subtask.name}")
                return

    # Complete the subtask
    feature = fm.complete_subtask(feature_id, subtask_index)

    if feature:
        subtask = feature.subtasks[subtask_index]
        console.print(f"[green]Completed subtask: {subtask.name}[/green]")


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


@feature.command("note")
@click.argument("feature_id")
@click.argument("note_text")
@click.pass_context
def feature_note(ctx, feature_id: str, note_text: str):
    """Add a timestamped note to a feature.

    Examples:
        claude-harness feature note F-001 "Waiting for API specs"
        claude-harness feature note F-001 "Discussed with team, using approach B"
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)

    feature = fm.add_note(feature_id, note_text)

    if feature:
        console.print(f"[green]Added note to {feature.id}[/green]")
        console.print(f"[dim]{note_text}[/dim]")
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


@feature.command("sync")
@click.option("--no-auto-start", is_flag=True, help="Don't auto-start next pending feature")
@click.option("--dry-run", is_flag=True, help="Show what would be synced without making changes")
@click.pass_context
def feature_sync(ctx, no_auto_start: bool, dry_run: bool):
    """Sync feature status from modified files in progress.md.

    Matches modified files to subtasks and updates their status.
    Auto-starts the next pending feature if none is in progress.

    Examples:
        claude-harness feature sync
        claude-harness feature sync --dry-run
        claude-harness feature sync --no-auto-start
    """
    project_path = ctx.obj["project_path"]
    fm = FeatureManager(project_path)
    pt = ProgressTracker(project_path)

    # Get modified files from progress.md
    progress = pt.get_current_progress()
    modified_files = progress.files_modified

    if not modified_files:
        console.print("[yellow]No modified files found in progress.md[/yellow]")
        return

    console.print(f"[blue]Found {len(modified_files)} modified files[/blue]")

    if dry_run:
        console.print("\n[dim]Dry run - no changes will be made[/dim]")
        # Show what would be matched
        in_progress = fm.get_in_progress()
        if not in_progress:
            next_pending = fm.get_next_pending()
            if next_pending and not no_auto_start:
                console.print(f"[yellow]Would auto-start: {next_pending.id} - {next_pending.name}[/yellow]")
            else:
                console.print("[yellow]No feature in progress and auto-start disabled[/yellow]")
                return
            in_progress = next_pending

        console.print(f"\n[bold]Feature: {in_progress.id} - {in_progress.name}[/bold]")
        for subtask in in_progress.subtasks:
            if subtask.done:
                console.print(f"  [green]✓[/green] {subtask.name}")
            else:
                # Check if any file would match
                keywords = fm._extract_keywords(subtask.name.lower())
                matching_files = []
                for f in modified_files:
                    f_lower = f.lower()
                    for kw in keywords:
                        if kw in f_lower:
                            matching_files.append(f)
                            break
                if matching_files:
                    console.print(f"  [yellow]→[/yellow] {subtask.name}")
                    for mf in matching_files[:2]:
                        console.print(f"      [dim]matches: {mf}[/dim]")
                else:
                    console.print(f"  [ ] {subtask.name}")
        return

    # Perform sync
    results = fm.sync_from_files(modified_files, auto_start=not no_auto_start)

    # Report results
    if results['started']:
        for fid in results['started']:
            f = fm.get_feature(fid)
            console.print(f"[green]Auto-started: {fid} - {f.name if f else 'Unknown'}[/green]")

    if results['subtasks_completed']:
        console.print(f"\n[bold]Subtasks completed:[/bold]")
        for fid, subtask_name in results['subtasks_completed']:
            console.print(f"  [green]✓[/green] {fid}: {subtask_name}")

    if results['features_completed']:
        for fid in results['features_completed']:
            console.print(f"\n[bold green]Feature completed: {fid}[/bold green]")

    if not results['subtasks_completed'] and not results['started']:
        console.print("[yellow]No matches found for modified files[/yellow]")

    # Summary
    total_matched = len(results['subtasks_completed'])
    total_unmatched = len(results['no_match'])
    console.print(f"\n[dim]Matched: {total_matched}, Unmatched: {total_unmatched}[/dim]")


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


@progress.command("history")
@click.option("--limit", "-l", default=10, help="Number of sessions to show")
@click.option("--show", "-s", type=int, help="Show details of session at index (1-based)")
@click.pass_context
def progress_history(ctx, limit: int, show: int):
    """View session history.

    Examples:
        claude-harness progress history
        claude-harness progress history --limit 5
        claude-harness progress history --show 1  # Show most recent
    """
    project_path = ctx.obj["project_path"]
    pt = ProgressTracker(project_path)

    if show:
        pt.show_session(show)
    else:
        pt.show_history(limit)


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


@context.command("session-close")
@click.pass_context
def context_session_close(ctx):
    """Mark current session as closed.

    When a session is closed, the next Claude session will start with
    fresh metrics (if auto_reset_session is enabled in config).
    This is called by the Stop hook automatically.
    """
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    ct.mark_session_closed()
    session_info = ct.get_session_info()
    console.print(f"[yellow]Session {session_info['session_id']} marked as closed.[/yellow]")
    console.print(f"[dim]Usage at close: {session_info['usage_percent']:.1f}%[/dim]")


@context.command("session-info")
@click.pass_context
def context_session_info(ctx):
    """Show current session information."""
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    info = ct.get_session_info()
    console.print(f"[cyan]Session ID:[/cyan] {info['session_id']}")
    console.print(f"[cyan]Started:[/cyan] {info['session_start']}")
    console.print(f"[cyan]Duration:[/cyan] {info['duration_minutes']:.1f} minutes")
    console.print(f"[cyan]Usage:[/cyan] {info['usage_percent']:.1f}%")
    console.print(f"[cyan]Closed:[/cyan] {info['closed']}")
    if info['estimated_compactions'] > 0:
        console.print(f"[cyan]Est. Compactions:[/cyan] ~{info['estimated_compactions']}")


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


# --- Delegation Commands ---


@main.group()
@click.pass_context
def delegation(ctx):
    """Manage subagent delegation settings."""
    pass


@delegation.command("status")
@click.pass_context
def delegation_status(ctx):
    """Show delegation status and metrics."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)
    dm.show_status()


@delegation.command("enable")
@click.pass_context
def delegation_enable(ctx):
    """Enable subagent delegation."""
    project_path = Path(ctx.obj["project_path"])
    dm = DelegationManager(str(project_path))
    dm.enable()
    _update_claude_md_from_config(project_path)
    console.print("[green]Subagent delegation enabled[/green]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@delegation.command("disable")
@click.pass_context
def delegation_disable(ctx):
    """Disable subagent delegation."""
    project_path = Path(ctx.obj["project_path"])
    dm = DelegationManager(str(project_path))
    dm.disable()
    _update_claude_md_from_config(project_path)
    console.print("[yellow]Subagent delegation disabled[/yellow]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@delegation.command("rules")
@click.pass_context
def delegation_rules(ctx):
    """Show all delegation rules."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)
    dm.show_rules()


@delegation.command("add-rule")
@click.option("--name", "-n", required=True, help="Rule name")
@click.option("--patterns", "-p", required=True, help="Comma-separated task patterns (regex)")
@click.option("--type", "-t", "subagent_type", default="general",
              type=click.Choice(["explore", "test", "document", "review", "general"]),
              help="Subagent type")
@click.option("--priority", default=5, type=int, help="Priority (1-10, higher = more likely)")
@click.option("--constraints", "-c", default="", help="Comma-separated constraints")
@click.pass_context
def delegation_add_rule(ctx, name: str, patterns: str, subagent_type: str,
                        priority: int, constraints: str):
    """Add a custom delegation rule.

    Examples:
        claude-harness delegation add-rule -n migration -p "migrate.*,upgrade.*" -t explore
        claude-harness delegation add-rule -n api-tests -p "api.*test" -t test -c "Mock HTTP"
    """
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)

    pattern_list = [p.strip() for p in patterns.split(",") if p.strip()]
    constraint_list = [c.strip() for c in constraints.split(",") if c.strip()]

    rule = DelegationRule(
        name=name,
        task_patterns=pattern_list,
        subagent_type=subagent_type,
        priority=priority,
        constraints=constraint_list,
    )

    try:
        dm.add_rule(rule)
        console.print(f"[green]Added delegation rule: {name}[/green]")
        console.print(f"  Type: {subagent_type}")
        console.print(f"  Patterns: {', '.join(pattern_list)}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@delegation.command("remove-rule")
@click.argument("rule_name")
@click.pass_context
def delegation_remove_rule(ctx, rule_name: str):
    """Remove a delegation rule by name."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)

    if dm.remove_rule(rule_name):
        console.print(f"[green]Removed delegation rule: {rule_name}[/green]")
    else:
        console.print(f"[red]Rule not found: {rule_name}[/red]")


@delegation.command("enable-rule")
@click.argument("rule_name")
@click.pass_context
def delegation_enable_rule(ctx, rule_name: str):
    """Enable a specific delegation rule."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)

    if dm.enable_rule(rule_name):
        console.print(f"[green]Enabled rule: {rule_name}[/green]")
    else:
        console.print(f"[red]Rule not found: {rule_name}[/red]")


@delegation.command("disable-rule")
@click.argument("rule_name")
@click.pass_context
def delegation_disable_rule(ctx, rule_name: str):
    """Disable a specific delegation rule."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)

    if dm.disable_rule(rule_name):
        console.print(f"[yellow]Disabled rule: {rule_name}[/yellow]")
    else:
        console.print(f"[red]Rule not found: {rule_name}[/red]")


@delegation.command("suggest")
@click.argument("feature_id")
@click.pass_context
def delegation_suggest(ctx, feature_id: str):
    """Show delegation suggestions for a feature's subtasks."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)
    fm = FeatureManager(project_path)

    feature = fm.get_feature(feature_id)
    if not feature:
        console.print(f"[red]Feature not found: {feature_id}[/red]")
        return

    if not feature.subtasks:
        console.print(f"[yellow]Feature {feature_id} has no subtasks[/yellow]")
        return

    subtask_names = [st.name for st in feature.subtasks]
    suggestions = dm.get_delegation_suggestions(subtask_names)

    console.print()
    console.print(f"[bold]Delegation Suggestions for {feature.id}: {feature.name}[/bold]")
    console.print()

    if not suggestions:
        console.print("[dim]No subtasks match delegation rules[/dim]")
        return

    total_savings = 0
    for subtask_name, rule in suggestions:
        savings = dm.estimate_savings(subtask_name, rule)
        total_savings += savings
        console.print(f"  [green]DELEGATE[/green] {subtask_name}")
        console.print(f"    Type: {rule.subagent_type}")
        console.print(f"    Est. savings: ~{savings:,} tokens")

    console.print()
    console.print(f"[bold]Total estimated savings: ~{total_savings:,} tokens[/bold]")


@delegation.command("auto")
@click.option("--on/--off", default=None, help="Enable or disable auto-delegation")
@click.pass_context
def delegation_auto(ctx, on: bool):
    """Configure auto-delegation hints in CLAUDE.md."""
    project_path = ctx.obj["project_path"]
    dm = DelegationManager(project_path)

    if on is None:
        # Show current status
        config = dm.get_config()
        status = "[green]enabled[/green]" if config.auto_delegate else "[dim]disabled[/dim]"
        console.print(f"Auto-delegation: {status}")
    else:
        dm.set_auto_delegate(on)
        status = "enabled" if on else "disabled"
        console.print(f"[green]Auto-delegation {status}[/green]")


# --- Commands (Slash Commands) ---


@main.group()
@click.pass_context
def commands(ctx):
    """Manage Claude Code slash commands.

    Generate and manage slash commands that integrate
    claude-harness with Claude Code.
    """
    pass


@commands.command("generate")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing command files",
)
@click.pass_context
def commands_generate(ctx, force: bool):
    """Generate slash commands in .claude/commands/.

    This creates slash command files that allow using
    harness features directly inside Claude Code with
    commands like /harness-status, /harness-feature-add, etc.
    """
    from .command_generator import write_commands_to_directory, generate_commands_readme, get_command_list

    project_path = Path(ctx.obj["project_path"])
    commands_dir = project_path / ".claude" / "commands"

    if commands_dir.exists() and not force:
        existing = list(commands_dir.glob("harness-*.md"))
        if existing:
            if not click.confirm(
                f"Found {len(existing)} existing harness commands. Overwrite?",
                default=False
            ):
                console.print("[yellow]Aborted.[/yellow]")
                return

    commands_dir.mkdir(parents=True, exist_ok=True)

    created = write_commands_to_directory(commands_dir)
    generate_commands_readme(commands_dir)

    console.print(f"[green]Generated {len(created)} slash commands in .claude/commands/[/green]")
    console.print()
    console.print("[bold]Available commands:[/bold]")
    for cmd in get_command_list()[:10]:
        console.print(f"  {cmd['name']} - {cmd['description']}")
    console.print(f"  ... and {len(get_command_list()) - 10} more")
    console.print()
    console.print("[dim]See .claude/commands/README.md for full list[/dim]")


@commands.command("list")
@click.pass_context
def commands_list(ctx):
    """List all available slash commands."""
    from .command_generator import get_command_list
    from rich.table import Table

    cmds = get_command_list()

    table = Table(title="Available Slash Commands", show_lines=False)
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    for cmd in cmds:
        table.add_row(cmd["name"], cmd["description"])

    console.print(table)
    console.print(f"\n[dim]Total: {len(cmds)} commands[/dim]")


# --- Optimize Commands ---


@main.group()
@click.pass_context
def optimize(ctx):
    """Context optimization commands.

    Tools to reduce token usage and optimize context:
    - File filtering (skip irrelevant files)
    - Output compression (summarize verbose outputs)
    - Exploration caching (avoid re-reading files)
    - Context pruning (remove stale references)
    """
    pass


@optimize.command("status")
@click.pass_context
def optimize_status(ctx):
    """Show optimization status and potential savings.

    Displays statistics from all optimization tools:
    - File filter configuration
    - Compression rules
    - Cache entries and savings
    - Context tracker status
    """
    from rich.table import Table
    from rich.panel import Panel

    project_path = ctx.obj["project_path"]

    console.print()
    console.print(Panel.fit("[bold blue]Context Optimization Status[/bold blue]"))
    console.print()

    # File Filter stats
    file_filter = FileFilter()
    filter_stats = file_filter.get_statistics()

    console.print("[bold]File Filter[/bold]")
    console.print(f"  Enabled: {'[green]Yes[/green]' if filter_stats['enabled'] else '[red]No[/red]'}")
    console.print(f"  Built-in patterns: {filter_stats['builtin_patterns']}")
    console.print(f"  Custom excludes: {filter_stats['custom_excludes']}")
    console.print(f"  Custom includes: {filter_stats['custom_includes']}")
    console.print(f"  Total patterns: {filter_stats['total_excludes']}")
    console.print()

    # Output Compressor stats
    compressor = OutputCompressor()
    compressor_stats = compressor.get_statistics()

    console.print("[bold]Output Compressor[/bold]")
    console.print(f"  Enabled: {'[green]Yes[/green]' if compressor_stats['enabled'] else '[red]No[/red]'}")
    console.print(f"  Min compress length: {compressor_stats['min_compress_length']:,} chars")
    console.print(f"  Supported commands: {compressor_stats['rules_count']}")
    console.print()

    # Exploration Cache stats
    cache = get_exploration_cache(project_path)
    cache_stats = cache.get_stats()

    console.print("[bold]Exploration Cache[/bold]")
    console.print(f"  Total entries: {cache_stats['total_entries']}")
    console.print(f"  Valid entries: {cache_stats['valid_entries']}")
    console.print(f"  Expired entries: {cache_stats['expired_entries']}")
    console.print(f"  Files cached: {cache_stats['total_files_cached']}")
    console.print(f"  Est. tokens saved: [green]~{cache_stats['estimated_tokens_saved']:,}[/green]")
    console.print()

    # Context Tracker compact summary
    ct = ContextTracker(project_path)
    if ct.is_enabled():
        summary = ct.get_compact_summary()
        console.print("[bold]Context Tracker[/bold]")
        console.print(f"  {summary}")
    else:
        console.print("[bold]Context Tracker[/bold]")
        console.print("  [dim]Disabled[/dim]")
    console.print()

    # Total savings estimate
    total_savings = cache_stats['estimated_tokens_saved']
    console.print(f"[bold]Total Estimated Savings: [green]~{total_savings:,} tokens[/green][/bold]")


@optimize.command("filter")
@click.argument("files", nargs=-1)
@click.option("--directory", "-d", default=".", help="Directory to scan (if no files provided)")
@click.pass_context
def optimize_filter(ctx, files, directory: str):
    """Filter files to show which would be tracked/skipped.

    Without arguments, scans the current directory.
    With file arguments, shows the status of each file.

    Examples:
        claude-harness optimize filter
        claude-harness optimize filter src/app.py node_modules/lodash/index.js
        claude-harness optimize filter -d ./src
    """
    from rich.table import Table
    import os

    project_path = ctx.obj["project_path"]
    file_filter = FileFilter()

    # If no files provided, scan the directory
    if not files:
        scan_path = Path(directory).resolve()
        if not scan_path.exists():
            console.print(f"[red]Directory not found: {scan_path}[/red]")
            sys.exit(1)

        # Walk directory and collect files (limit to avoid overwhelming output)
        files_list = []
        for root, dirs, filenames in os.walk(scan_path):
            # Skip common ignored directories at walk time
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}]

            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), scan_path)
                files_list.append(rel_path)
                if len(files_list) >= 500:  # Limit
                    break
            if len(files_list) >= 500:
                break
        files = files_list

    if not files:
        console.print("[yellow]No files found to analyze[/yellow]")
        return

    # Filter and get details
    result = file_filter.filter_with_details(list(files))

    # Create table
    table = Table(title="File Filter Results")
    table.add_column("Status", style="bold", width=8)
    table.add_column("File")
    table.add_column("Reason", style="dim")

    # Show tracked files
    for filepath in result.tracked[:50]:  # Limit display
        table.add_row("[green]TRACK[/green]", filepath, "")

    # Show skipped files
    for filepath in result.skipped[:50]:  # Limit display
        reason = result.skip_reasons.get(filepath, "Filtered")
        table.add_row("[yellow]SKIP[/yellow]", filepath, reason)

    console.print(table)

    # Summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Tracked: [green]{len(result.tracked)}[/green] files")
    console.print(f"  Skipped: [yellow]{len(result.skipped)}[/yellow] files")
    console.print(f"  Est. tokens saved: [green]~{result.tokens_saved_estimate:,}[/green]")

    if len(files) > 100:
        console.print(f"\n[dim]Showing first 50 of each category. Total files: {len(files)}[/dim]")


@optimize.command("compress")
@click.argument("command")
@click.argument("output_file", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Force compression even for small outputs")
@click.pass_context
def optimize_compress(ctx, command: str, output_file: str, force: bool):
    """Compress command output from a file.

    Reads the output file and applies intelligent compression
    based on the command type (pytest, npm, git, etc.).

    Examples:
        claude-harness optimize compress pytest /tmp/test_output.txt
        claude-harness optimize compress "npm install" /tmp/npm_output.txt
        claude-harness optimize compress mypy /tmp/mypy_output.txt --force
    """
    compressor = OutputCompressor()

    # Read the output file
    try:
        with open(output_file, 'r') as f:
            output_content = f.read()
    except IOError as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        sys.exit(1)

    # Check if there's a compression rule
    rule = compressor.get_compression_rule(command)
    if rule:
        console.print(f"[dim]Using compression rule for: {command}[/dim]")
    else:
        console.print(f"[dim]No specific rule for '{command}', using default compression[/dim]")

    # Compress
    result = compressor.compress_with_details(command, output_content, force=force)

    # Show results
    console.print()
    console.print("[bold]Compression Results:[/bold]")
    console.print(f"  Original: {result.original_lines} lines ({len(output_content):,} chars)")
    console.print(f"  Compressed: {result.compressed_lines} lines ({len(result.output):,} chars)")
    console.print(f"  Ratio: {result.compression_ratio:.1%}")
    console.print(f"  [green]Tokens saved: ~{result.tokens_saved:,}[/green]")

    if result.errors_found:
        console.print(f"\n[bold]Errors found:[/bold] {len(result.errors_found)}")
        for err in result.errors_found[:5]:
            console.print(f"  [red]{err[:100]}...[/red]" if len(err) > 100 else f"  [red]{err}[/red]")
        if len(result.errors_found) > 5:
            console.print(f"  ... and {len(result.errors_found) - 5} more")

    if result.summary_found:
        console.print("\n[bold]Summary extracted:[/bold]")
        console.print(f"  {result.summary_found[:200]}..." if len(result.summary_found) > 200 else f"  {result.summary_found}")

    # Print compressed output
    console.print("\n[bold]Compressed Output:[/bold]")
    console.print("-" * 60)
    console.print(result.output)
    console.print("-" * 60)


@optimize.command("cache")
@click.pass_context
def optimize_cache_list(ctx):
    """List cached explorations.

    Shows all cached exploration results with their age,
    validity status, and estimated token savings.
    """
    from rich.table import Table

    project_path = ctx.obj["project_path"]
    cache = get_exploration_cache(project_path)

    entries = cache.list_cached()

    if not entries:
        console.print("[yellow]No cached explorations found.[/yellow]")
        console.print("[dim]Cache explorations using the exploration_cache module.[/dim]")
        return

    table = Table(title="Cached Explorations")
    table.add_column("Name", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Age", justify="right")
    table.add_column("Status")

    for entry in entries:
        age_str = f"{entry.age_hours:.1f}h"

        if entry.is_valid():
            remaining = entry.time_remaining_hours
            if remaining == float("inf"):
                status = "[green]Valid (no expiry)[/green]"
            else:
                status = f"[green]Valid ({remaining:.1f}h left)[/green]"
        else:
            status = "[red]Expired[/red]"

        table.add_row(
            entry.name[:40] + "..." if len(entry.name) > 40 else entry.name,
            str(len(entry.files_found)),
            f"~{entry.estimated_tokens:,}",
            age_str,
            status,
        )

    console.print(table)

    # Summary
    stats = cache.get_stats()
    console.print()
    console.print(f"[bold]Total: {stats['total_entries']} entries, ~{stats['estimated_tokens_saved']:,} tokens saved[/bold]")


@optimize.command("cache-clear")
@click.option("--expired-only", is_flag=True, help="Only clear expired entries")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def optimize_cache_clear(ctx, expired_only: bool, yes: bool):
    """Clear exploration cache.

    By default, clears all cache entries. Use --expired-only
    to only remove expired entries.

    Examples:
        claude-harness optimize cache-clear
        claude-harness optimize cache-clear --expired-only
        claude-harness optimize cache-clear -y
    """
    project_path = ctx.obj["project_path"]
    cache = get_exploration_cache(project_path)

    if expired_only:
        removed = cache.cleanup_expired()
        console.print(f"[green]Removed {removed} expired cache entries.[/green]")
    else:
        stats = cache.get_stats()

        if not yes and stats['total_entries'] > 0:
            if not click.confirm(
                f"Clear all {stats['total_entries']} cache entries (~{stats['estimated_tokens_saved']:,} tokens)?",
                default=False
            ):
                console.print("[yellow]Aborted.[/yellow]")
                return

        removed = cache.invalidate_all()
        console.print(f"[green]Cleared {removed} cache entries.[/green]")


@optimize.command("prune")
@click.option("--max-files", default=30, help="Max tracked files to keep")
@click.option("--max-age", default=30, help="Max age in minutes for tracked files")
@click.pass_context
def optimize_prune(ctx, max_files: int, max_age: int):
    """Prune stale context references.

    Removes old file references from context tracking to reduce
    token estimates and clean up stale data.

    Examples:
        claude-harness optimize prune
        claude-harness optimize prune --max-files 20
        claude-harness optimize prune --max-age 60
    """
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    if not ct.is_enabled():
        console.print("[yellow]Context tracking is disabled.[/yellow]")
        return

    result = ct.prune_stale_context(max_files=max_files, max_age_minutes=max_age)

    if result['pruned_files']:
        console.print(f"[green]Pruned {len(result['pruned_files'])} stale file references.[/green]")
        console.print(f"[green]Estimated tokens freed: ~{result['tokens_freed']:,}[/green]")
        console.print()
        console.print("[dim]Pruned files:[/dim]")
        for filepath in result['pruned_files'][:10]:
            console.print(f"  - {filepath}")
        if len(result['pruned_files']) > 10:
            console.print(f"  ... and {len(result['pruned_files']) - 10} more")
    else:
        console.print("[dim]No stale files to prune.[/dim]")


@optimize.command("summary")
@click.pass_context
def optimize_summary(ctx):
    """Show compact context summary.

    Displays a concise one-line summary of context usage,
    suitable for status bars or quick checks.
    """
    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    if not ct.is_enabled():
        console.print("[dim]Context tracking disabled[/dim]")
        return

    summary = ct.get_compact_summary()
    console.print(summary)


@optimize.command("categorize")
@click.pass_context
def optimize_categorize(ctx):
    """Show tracked files by category.

    Groups tracked files into categories (code, config, docs, tests, other)
    for better context awareness.
    """
    from rich.table import Table

    project_path = ctx.obj["project_path"]
    ct = ContextTracker(project_path)

    if not ct.is_enabled():
        console.print("[yellow]Context tracking is disabled.[/yellow]")
        return

    categories = ct.categorize_tracked_files()

    # Count totals
    total = sum(len(files) for files in categories.values())

    if total == 0:
        console.print("[yellow]No files tracked yet.[/yellow]")
        return

    table = Table(title="Tracked Files by Category")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Files")

    category_colors = {
        "code": "cyan",
        "config": "yellow",
        "docs": "green",
        "tests": "magenta",
        "other": "white",
    }

    for category, files in categories.items():
        color = category_colors.get(category, "white")
        files_preview = ", ".join(Path(f).name for f in files[:5])
        if len(files) > 5:
            files_preview += f" +{len(files) - 5} more"

        table.add_row(
            f"[{color}]{category.title()}[/{color}]",
            str(len(files)),
            files_preview or "[dim]none[/dim]",
        )

    console.print(table)
    console.print(f"\n[bold]Total tracked files: {total}[/bold]")


@optimize.command("loading-plan")
@click.argument("files", nargs=-1)
@click.option("--task-type", "-t", default=None, help="Task type (test, docs, feature)")
@click.option("--directory", "-d", default=None, help="Directory to scan")
@click.pass_context
def optimize_loading_plan(ctx, files, task_type: str, directory: str):
    """Get a loading plan for files.

    Uses the lazy loader to prioritize which files should be loaded
    immediately vs deferred.

    Examples:
        claude-harness optimize loading-plan src/*.py
        claude-harness optimize loading-plan -d ./src -t test
        claude-harness optimize loading-plan README.md app.py test_app.py
    """
    from rich.table import Table
    import glob as globmodule

    project_path = ctx.obj["project_path"]
    loader = get_lazy_loader(project_path)

    # Collect files
    files_list = list(files)

    # If directory provided, scan it
    if directory:
        dir_path = Path(directory).resolve()
        if dir_path.exists():
            for filepath in dir_path.rglob("*"):
                if filepath.is_file():
                    files_list.append(str(filepath.relative_to(Path(project_path))))

    # Expand globs
    expanded_files = []
    for f in files_list:
        if "*" in f or "?" in f:
            expanded_files.extend(globmodule.glob(f, recursive=True))
        else:
            expanded_files.append(f)

    if not expanded_files:
        console.print("[yellow]No files to analyze.[/yellow]")
        return

    # Get loading plan
    plan = loader.get_loading_plan(expanded_files, task_type=task_type)

    # Display immediate files
    if plan['immediate']:
        console.print("[bold]Immediate (load now):[/bold]")
        for item in plan['immediate'][:15]:
            console.print(f"  [green]{item['priority']}[/green] {item['filepath']}")
            console.print(f"      [dim]{item['reason']}[/dim]")
        if len(plan['immediate']) > 15:
            console.print(f"  ... and {len(plan['immediate']) - 15} more")
        console.print()

    # Display deferred files
    if plan['deferred']:
        console.print("[bold]Deferred (load on demand):[/bold]")
        for item in plan['deferred'][:10]:
            console.print(f"  [yellow]{item['priority']}[/yellow] {item['filepath']}")
            console.print(f"      [dim]{item['reason']}[/dim]")
        if len(plan['deferred']) > 10:
            console.print(f"  ... and {len(plan['deferred']) - 10} more")
        console.print()

    # Display skipped files
    if plan['skipped']:
        console.print("[bold]Skipped (not loaded):[/bold]")
        for item in plan['skipped'][:5]:
            console.print(f"  [red]{item['priority']}[/red] {item['filepath']}")
        if len(plan['skipped']) > 5:
            console.print(f"  ... and {len(plan['skipped']) - 5} more")
        console.print()

    # Summary
    summary = plan['summary']
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Total files: {summary['total_files']}")
    console.print(f"  Immediate: [green]{summary['immediate_count']}[/green] (~{plan['tokens_immediate']:,} tokens)")
    console.print(f"  Deferred/Skipped: [yellow]{summary['deferred_count'] + summary['skipped_count']}[/yellow] ([green]~{plan['tokens_saved']:,} tokens saved[/green])")


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


# --- Orchestration Commands ---


@main.group()
@click.pass_context
def orchestrate(ctx):
    """Orchestration commands for automatic subagent delegation."""
    pass


@orchestrate.command("status")
@click.pass_context
def orchestrate_status(ctx):
    """Show orchestration status and metrics."""
    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(project_path)
    is_enabled = engine.is_enabled()
    status = engine.get_status()

    # Enabled/Disabled display
    console.print()
    console.print("[bold]Orchestration Engine[/bold]")
    if is_enabled:
        console.print("  [green]Status: enabled[/green]")
    else:
        console.print("  [yellow]Status: disabled[/yellow]")
        console.print("[dim]  Run 'claude-harness orchestrate enable' to enable.[/dim]")

    # State display
    state = status.get("state", "idle")
    state_colors = {
        "idle": "green",
        "evaluating": "yellow",
        "delegating": "blue",
        "waiting": "cyan",
        "integrating": "magenta",
    }
    state_color = state_colors.get(state, "white")

    console.print(f"  State: [{state_color}]{state.upper()}[/{state_color}]")
    console.print(
        f"  Delegation available: "
        f"{'[green]Yes[/green]' if status.get('delegation_available') else '[dim]No[/dim]'}"
    )

    # Metrics
    metrics = status.get("metrics", {})
    limits = status.get("limits", {})

    console.print()
    console.print("[bold]Session Metrics:[/bold]")
    console.print(f"  Delegations: {limits.get('session_used', 0)}/{limits.get('session_max', 20)}")
    console.print(f"  Completed: {metrics.get('completed_delegations', 0)}")
    console.print(f"  Failed: {metrics.get('failed_delegations', 0)}")
    console.print(f"  Tokens saved: {metrics.get('total_tokens_saved', 0):,}")

    success_rate = metrics.get("success_rate", 0.0)
    if metrics.get("total_delegations", 0) > 0:
        console.print(f"  Success rate: {success_rate:.0%}")

    # Active delegations
    active = status.get("active", [])
    if active:
        console.print()
        console.print(f"[bold yellow]Active Delegations ({len(active)}):[/bold yellow]")
        for d in active:
            console.print(f"  [{d['id']}] {d['subtask_name']} ({d['subagent_type']})")

    # Queued delegations
    queued = status.get("queued", [])
    if queued:
        console.print()
        console.print(f"[bold blue]Queued ({len(queued)}):[/bold blue]")
        for d in queued[:5]:
            console.print(f"  [{d['id']}] {d['subtask_name']} (priority: {d['priority']})")
        if len(queued) > 5:
            console.print(f"  [dim]... and {len(queued) - 5} more[/dim]")

    console.print()


@orchestrate.command("enable")
@click.pass_context
def orchestrate_enable(ctx):
    """Enable automatic orchestration."""
    project_path = Path(ctx.obj["project_path"])

    # Check if initialized
    harness_dir = project_path / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(str(project_path))

    # Check if delegation is enabled (orchestration depends on delegation)
    dm = DelegationManager(str(project_path))
    if not dm.is_enabled():
        console.print("[yellow]Warning: Delegation is disabled. Orchestration requires delegation to work.[/yellow]")
        console.print("[dim]Run 'claude-harness delegation enable' first.[/dim]")

    engine.enable()
    _update_claude_md_from_config(project_path)
    console.print("[green]Orchestration enabled[/green]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@orchestrate.command("disable")
@click.pass_context
def orchestrate_disable(ctx):
    """Disable automatic orchestration."""
    project_path = Path(ctx.obj["project_path"])

    # Check if initialized
    harness_dir = project_path / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(str(project_path))
    engine.disable()
    _update_claude_md_from_config(project_path)
    console.print("[yellow]Orchestration disabled[/yellow]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@orchestrate.command("evaluate")
@click.pass_context
def orchestrate_evaluate(ctx):
    """Evaluate if auto-delegation should trigger."""
    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(project_path)
    result = engine.evaluate()

    console.print()
    console.print("[bold]Orchestration Evaluation[/bold]")
    console.print()

    # Context info
    context_usage = result.get("context_usage", 0.0)
    threshold = result.get("threshold", 0.5)
    context_met = context_usage >= threshold

    context_color = "green" if context_met else "yellow"
    console.print(f"  Context usage: [{context_color}]{context_usage:.1%}[/{context_color}]")
    console.print(f"  Threshold: {threshold:.0%}")

    # Feature info
    if result.get("feature_id"):
        console.print(f"  Feature: {result['feature_id']} - {result.get('feature_name', '')}")

    # Delegatable subtasks
    delegatable = result.get("delegatable_subtasks", [])
    if delegatable:
        console.print()
        console.print(f"[bold]Delegatable Subtasks ({len(delegatable)}):[/bold]")
        for st in delegatable:
            console.print(
                f"  - {st['name']} [dim]({st['subagent_type']}, rule: {st['rule']}, "
                f"priority: {st['priority']})[/dim]"
            )

    # Recommendation
    console.print()
    should_delegate = result.get("should_delegate", False)
    if should_delegate:
        console.print("[green bold]Recommendation: DELEGATE[/green bold]")
        console.print("[dim]Run 'claude-harness orchestrate queue' to generate delegation queue[/dim]")
    else:
        console.print("[yellow]Recommendation: Do not delegate[/yellow]")
        reasons = result.get("reasons", [])
        if reasons:
            console.print("[dim]Reasons:[/dim]")
            for reason in reasons:
                console.print(f"  - {reason}")

    console.print()


@orchestrate.command("queue")
@click.argument("feature_id", required=False)
@click.pass_context
def orchestrate_queue(ctx, feature_id):
    """Generate delegation queue for a feature."""
    from rich.table import Table

    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(project_path)

    # Generate queue
    queue = engine.generate_delegation_queue(feature_id)

    if not queue:
        console.print("[yellow]No delegatable subtasks found.[/yellow]")
        console.print("[dim]Ensure you have a feature in progress with subtasks matching delegation rules.[/dim]")
        return

    # Display queue table
    table = Table(title="Delegation Queue")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Subtask", style="white")
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Priority", justify="center", width=8)
    table.add_column("Est. Savings", justify="right", width=12)

    total_savings = 0
    for item in queue:
        table.add_row(
            item.id,
            item.subtask_name[:40] + ("..." if len(item.subtask_name) > 40 else ""),
            item.subagent_type,
            str(item.priority),
            f"{item.estimated_tokens_saved:,}",
        )
        total_savings += item.estimated_tokens_saved

    console.print()
    console.print(table)
    console.print()
    console.print(f"[bold]Total estimated savings: ~{total_savings:,} tokens[/bold]")
    console.print()

    # Show prompts preview
    console.print("[dim]To start a delegation, run:[/dim]")
    console.print("  claude-harness orchestrate start <DELEGATION_ID>")
    console.print()

    # Show first prompt as example
    if queue:
        prompt_preview = queue[0].prompt[:200] + "..." if len(queue[0].prompt) > 200 else queue[0].prompt
        console.print("[bold]Example prompt for first delegation:[/bold]")
        console.print(f"[dim]{prompt_preview}[/dim]")

    console.print()


@orchestrate.command("start")
@click.argument("delegation_id")
@click.pass_context
def orchestrate_start(ctx, delegation_id):
    """Mark a delegation as started."""
    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(project_path)
    item = engine.start_delegation(delegation_id)

    if not item:
        console.print(f"[red]Delegation not found in queue: {delegation_id}[/red]")
        console.print("[dim]Run 'claude-harness orchestrate queue' to see available delegations.[/dim]")
        return

    console.print()
    console.print(f"[green]Started delegation: {item.id}[/green]")
    console.print(f"  Feature: {item.feature_id} - {item.feature_name}")
    console.print(f"  Subtask: {item.subtask_name}")
    console.print(f"  Type: {item.subagent_type}")
    console.print()
    console.print("[bold]Delegation Prompt:[/bold]")
    console.print()
    console.print(item.prompt)
    console.print()
    console.print("[dim]When complete, run:[/dim]")
    console.print(f"  claude-harness orchestrate complete {item.id} -s \"<summary>\"")
    console.print()


@orchestrate.command("complete")
@click.argument("delegation_id")
@click.option("-s", "--summary", required=True, help="Result summary")
@click.option("-f", "--files-created", multiple=True, help="Files created")
@click.option("-m", "--files-modified", multiple=True, help="Files modified")
@click.pass_context
def orchestrate_complete(ctx, delegation_id, summary, files_created, files_modified):
    """Complete a delegation with results."""
    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(project_path)
    item = engine.complete_delegation(
        delegation_id=delegation_id,
        result_summary=summary,
        files_created=list(files_created) if files_created else None,
        files_modified=list(files_modified) if files_modified else None,
    )

    if not item:
        console.print(f"[red]Active delegation not found: {delegation_id}[/red]")
        console.print("[dim]Run 'claude-harness orchestrate status' to see active delegations.[/dim]")
        return

    console.print()
    console.print(f"[green]Completed delegation: {item.id}[/green]")
    console.print(f"  Subtask: {item.subtask_name}")
    console.print(f"  Summary: {summary}")

    if item.files_created:
        console.print(f"  Files created: {len(item.files_created)}")
        for f in item.files_created[:5]:
            console.print(f"    - {f}")

    if item.files_modified:
        console.print(f"  Files modified: {len(item.files_modified)}")
        for f in item.files_modified[:5]:
            console.print(f"    - {f}")

    console.print(f"  Tokens saved: ~{item.estimated_tokens_saved:,}")
    console.print()

    # Show updated metrics
    status = engine.get_status()
    metrics = status.get("metrics", {})
    console.print("[dim]Session totals:[/dim]")
    console.print(f"  Completed: {metrics.get('completed_delegations', 0)}")
    console.print(f"  Total tokens saved: {metrics.get('total_tokens_saved', 0):,}")
    console.print()


@orchestrate.command("reset")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def orchestrate_reset(ctx, yes):
    """Reset orchestration session."""
    project_path = ctx.obj["project_path"]

    # Check if initialized
    harness_dir = Path(project_path) / ".claude-harness"
    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    engine = get_orchestration_engine(project_path)

    # Get current status for confirmation
    status = engine.get_status()
    metrics = status.get("metrics", {})

    if not yes:
        console.print("[yellow]This will reset:[/yellow]")
        console.print(f"  - {metrics.get('total_delegations', 0)} total delegations")
        console.print(f"  - {metrics.get('completed_delegations', 0)} completed delegations")
        console.print(f"  - {metrics.get('total_tokens_saved', 0):,} tokens saved tracking")
        console.print("  - All queued and active delegations")
        console.print()
        if not click.confirm("Continue?", default=False):
            console.print("[yellow]Aborted.[/yellow]")
            return

    engine.reset_session()
    console.print("[green]Orchestration session reset.[/green]")


# ==================== DISCOVERY COMMANDS ====================


@main.group()
@click.pass_context
def discovery(ctx):
    """Track discoveries, findings, and new requirements."""
    pass


@discovery.command("add")
@click.argument("summary")
@click.option("--context", "-c", default="", help="What was happening when discovered")
@click.option("--details", "-d", default="", help="Detailed explanation")
@click.option("--impact", "-i", default="", help="What this affects")
@click.option("--tags", "-t", multiple=True, help="Tags for categorization")
@click.option("--feature", "-f", default="", help="Related feature ID")
@click.pass_context
def discovery_add(ctx, summary: str, context: str, details: str, impact: str, tags, feature: str):
    """Add a new discovery.

    Example:
        claude-harness discovery add "Need X-API-Key header for auth" -t auth -t api
    """
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    discovery = tracker.add_discovery(
        summary=summary,
        context=context,
        details=details,
        impact=impact,
        tags=list(tags),
        related_feature=feature,
        source="manual",
    )

    console.print(f"[green]Added discovery {discovery.id}:[/green] {summary}")
    if tags:
        console.print(f"[dim]Tags: {', '.join(tags)}[/dim]")


@discovery.command("list")
@click.option("--tag", "-t", default=None, help="Filter by tag")
@click.option("--feature", "-f", default=None, help="Filter by feature ID")
@click.option("--limit", "-n", default=0, type=int, help="Max items to show (0=all)")
@click.option("--compact", is_flag=True, help="Compact display")
@click.pass_context
def discovery_list(ctx, tag: str, feature: str, limit: int, compact: bool):
    """List discoveries."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    discoveries = tracker.list_discoveries(tag=tag, feature=feature, limit=limit)
    tracker.show_discoveries(discoveries, compact=compact)


@discovery.command("show")
@click.argument("discovery_id")
@click.pass_context
def discovery_show(ctx, discovery_id: str):
    """Show a specific discovery."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    discovery = tracker.get_discovery(discovery_id)
    if discovery:
        tracker.show_discoveries([discovery])
    else:
        console.print(f"[red]Discovery {discovery_id} not found.[/red]")


@discovery.command("search")
@click.argument("query")
@click.option("--compact", is_flag=True, help="Compact display")
@click.pass_context
def discovery_search(ctx, query: str, compact: bool):
    """Search discoveries by keyword."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    discoveries = tracker.search_discoveries(query)
    if discoveries:
        console.print(f"[green]Found {len(discoveries)} matches for '{query}':[/green]")
        console.print()
        tracker.show_discoveries(discoveries, compact=compact)
    else:
        console.print(f"[yellow]No discoveries matching '{query}'[/yellow]")


@discovery.command("delete")
@click.argument("discovery_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def discovery_delete(ctx, discovery_id: str, yes: bool):
    """Delete a discovery."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    discovery = tracker.get_discovery(discovery_id)
    if not discovery:
        console.print(f"[red]Discovery {discovery_id} not found.[/red]")
        return

    if not yes:
        console.print(f"[yellow]About to delete:[/yellow] {discovery.summary}")
        if not click.confirm("Continue?", default=False):
            console.print("[yellow]Aborted.[/yellow]")
            return

    if tracker.delete_discovery(discovery_id):
        console.print(f"[green]Deleted discovery {discovery_id}.[/green]")
    else:
        console.print(f"[red]Failed to delete discovery {discovery_id}.[/red]")


@discovery.command("tags")
@click.pass_context
def discovery_tags(ctx):
    """List all tags used in discoveries."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    stats = tracker.get_stats()
    tags = stats.get("tags", [])
    counts = stats.get("tag_counts", {})

    if not tags:
        console.print("[dim]No tags found.[/dim]")
        return

    console.print("[bold]Discovery Tags:[/bold]")
    for tag in tags:
        count = counts.get(tag, 0)
        console.print(f"  - {tag} ({count})")


@discovery.command("stats")
@click.pass_context
def discovery_stats(ctx):
    """Show discovery statistics."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    stats = tracker.get_stats()

    console.print("[bold]Discovery Statistics:[/bold]")
    console.print(f"  Total discoveries: {stats['total']}")
    console.print()

    by_source = stats.get("by_source", {})
    if by_source:
        console.print("  By source:")
        for source, count in by_source.items():
            console.print(f"    - {source}: {count}")

    tags = stats.get("tags", [])
    if tags:
        console.print()
        console.print(f"  Tags: {', '.join(tags[:10])}")
        if len(tags) > 10:
            console.print(f"    ... and {len(tags) - 10} more")


@discovery.command("summary")
@click.pass_context
def discovery_summary(ctx):
    """Generate a summary for context/handoff."""
    project_path = ctx.obj["project_path"]
    tracker = get_discovery_tracker(project_path)

    summary = tracker.generate_summary_for_context()
    if summary:
        console.print(summary)
    else:
        console.print("[dim]No discoveries to summarize.[/dim]")


@discovery.command("enable")
@click.pass_context
def discovery_enable(ctx):
    """Enable discoveries tracking."""
    project_path = Path(ctx.obj["project_path"])
    harness_dir = project_path / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    tracker = get_discovery_tracker(str(project_path))
    tracker.enable()
    _update_claude_md_from_config(project_path)
    console.print("[green]Discoveries tracking enabled[/green]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@discovery.command("disable")
@click.pass_context
def discovery_disable(ctx):
    """Disable discoveries tracking."""
    project_path = Path(ctx.obj["project_path"])
    harness_dir = project_path / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    tracker = get_discovery_tracker(str(project_path))
    tracker.disable()
    _update_claude_md_from_config(project_path)
    console.print("[yellow]Discoveries tracking disabled[/yellow]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@discovery.command("status")
@click.pass_context
def discovery_status(ctx):
    """Show whether discoveries tracking is enabled."""
    project_path = ctx.obj["project_path"]
    harness_dir = Path(project_path) / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    tracker = get_discovery_tracker(project_path)
    enabled = tracker.is_enabled()

    if enabled:
        console.print("[green]Discoveries tracking: enabled[/green]")
    else:
        console.print("[yellow]Discoveries tracking: disabled[/yellow]")
        console.print("[dim]Run 'claude-harness discovery enable' to enable.[/dim]")


# ==================== DOCUMENTATION COMMANDS ====================


@main.group("docs")
@click.pass_context
def docs(ctx):
    """Configure documentation update reminders."""
    pass


@docs.command("enable")
@click.pass_context
def docs_enable(ctx):
    """Enable documentation reminders after feature completion."""
    project_path = Path(ctx.obj["project_path"])
    harness_dir = project_path / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    config_path = harness_dir / "config.json"
    config = json.loads(config_path.read_text())

    if "documentation" not in config:
        config["documentation"] = {}
    config["documentation"]["enabled"] = True

    config_path.write_text(json.dumps(config, indent=2))
    _update_claude_md_from_config(project_path)
    console.print("[green]Documentation reminders enabled[/green]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@docs.command("disable")
@click.pass_context
def docs_disable(ctx):
    """Disable documentation reminders."""
    project_path = Path(ctx.obj["project_path"])
    harness_dir = project_path / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    config_path = harness_dir / "config.json"
    config = json.loads(config_path.read_text())

    if "documentation" not in config:
        config["documentation"] = {}
    config["documentation"]["enabled"] = False

    config_path.write_text(json.dumps(config, indent=2))
    _update_claude_md_from_config(project_path)
    console.print("[yellow]Documentation reminders disabled[/yellow]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


@docs.command("status")
@click.pass_context
def docs_status(ctx):
    """Show documentation reminder settings."""
    project_path = ctx.obj["project_path"]
    harness_dir = Path(project_path) / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    config_path = harness_dir / "config.json"
    config = json.loads(config_path.read_text())

    doc_config = config.get("documentation", {"enabled": True, "trigger": "feature_complete"})
    enabled = doc_config.get("enabled", True)
    trigger = doc_config.get("trigger", "feature_complete")

    if enabled:
        console.print(f"[green]Documentation reminders: enabled[/green]")
        console.print(f"[dim]Trigger: {trigger}[/dim]")
    else:
        console.print("[yellow]Documentation reminders: disabled[/yellow]")
        console.print("[dim]Run 'claude-harness docs enable' to enable.[/dim]")


@docs.command("trigger")
@click.argument("when", type=click.Choice(["feature_complete", "session_end"]))
@click.pass_context
def docs_trigger(ctx, when: str):
    """Set when documentation reminders appear.

    WHEN: feature_complete or session_end
    """
    project_path = Path(ctx.obj["project_path"])
    harness_dir = project_path / ".claude-harness"

    if not harness_dir.exists():
        console.print("[red]Error: Harness not initialized. Run 'claude-harness init' first.[/red]")
        sys.exit(1)

    config_path = harness_dir / "config.json"
    config = json.loads(config_path.read_text())

    if "documentation" not in config:
        config["documentation"] = {}
    config["documentation"]["trigger"] = when

    config_path.write_text(json.dumps(config, indent=2))
    _update_claude_md_from_config(project_path)
    console.print(f"[green]Documentation trigger set to: {when}[/green]")
    console.print("[dim]CLAUDE.md updated.[/dim]")


if __name__ == "__main__":
    main()
