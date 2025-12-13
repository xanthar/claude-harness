"""Interactive project initializer for Claude Harness.

Guides users through setup with intelligent questions based on:
- Detected stack (for existing projects)
- User preferences (for new projects)
"""

import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from jinja2 import Environment, PackageLoader, select_autoescape

from .detector import StackDetector, DetectedStack
from .command_generator import write_commands_to_directory, generate_commands_readme


console = Console()


@dataclass
class HarnessConfig:
    """Complete harness configuration."""

    # Project info
    project_name: str = ""
    project_description: str = ""

    # Stack
    language: str = "python"
    language_version: str = "3.11+"
    framework: Optional[str] = None
    database: Optional[str] = None
    orm: Optional[str] = None

    # Paths
    source_directory: str = "."
    backend_directory: Optional[str] = None
    venv_path: Optional[str] = None
    env_file: Optional[str] = ".env"
    test_directory: str = "tests"

    # Startup
    port: int = 8000
    health_endpoint: str = "/health"
    start_command: str = ""
    pre_checks: list = field(default_factory=lambda: ["venv_active", "db_connected"])

    # Git
    protected_branches: list = field(default_factory=lambda: ["main", "master"])
    branch_prefixes: list = field(
        default_factory=lambda: ["feat/", "fix/", "chore/", "docs/", "refactor/"]
    )
    require_merge_confirmation: bool = True

    # Testing
    test_framework: str = "pytest"
    unit_test_command: str = "pytest tests/unit/ -v"
    e2e_test_command: str = "pytest e2e/ -v"
    coverage_threshold: int = 80

    # Blocked actions
    blocked_actions: list = field(
        default_factory=lambda: [
            "commit_to_protected_branch",
            "push_to_protected_branch_without_confirmation",
            "delete_backup_branches",
        ]
    )

    # E2E
    e2e_enabled: bool = True
    e2e_base_url: str = "http://localhost:8000"
    e2e_browser: str = "chromium"

    # Context Tracking
    context_tracking_enabled: bool = True
    context_budget: int = 200000  # ~200k tokens default
    context_warning_threshold: float = 0.7  # Warn at 70%
    context_critical_threshold: float = 0.9  # Critical at 90%
    show_context_in_status: bool = True  # Show in status output
    auto_reset_session: bool = True  # Reset context on new session
    auto_save_handoff: bool = True  # Auto-save handoff on session end

    # Output Control (to reduce terminal scrolling issues)
    output_compact_mode: bool = False  # Use compact output by default
    output_max_lines: int = 50  # Max lines before truncation (0 = unlimited)
    output_max_files_shown: int = 20  # Max files to show in lists
    output_truncate_long_values: bool = True  # Truncate long values in tables

    # Subagent Delegation
    delegation_enabled: bool = False  # Enable subagent delegation hints
    delegation_auto: bool = False  # Auto-generate delegation hints in CLAUDE.md
    delegation_parallel_limit: int = 3  # Max concurrent subagent suggestions

    # Claude Code Integration
    create_claude_hooks: bool = False  # Auto-create .claude/settings.local.json with hooks

    # Features
    initial_phase: str = "Phase 1"
    initial_features: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_name": self.project_name,
            "project_description": self.project_description,
            "stack": {
                "language": self.language,
                "language_version": self.language_version,
                "framework": self.framework,
                "database": self.database,
                "orm": self.orm,
            },
            "paths": {
                "source": self.source_directory,
                "backend": self.backend_directory,
                "venv": self.venv_path,
                "env_file": self.env_file,
                "tests": self.test_directory,
            },
            "startup": {
                "port": self.port,
                "health_endpoint": self.health_endpoint,
                "start_command": self.start_command,
                "pre_checks": self.pre_checks,
            },
            "git": {
                "protected_branches": self.protected_branches,
                "branch_prefixes": self.branch_prefixes,
                "require_merge_confirmation": self.require_merge_confirmation,
            },
            "testing": {
                "framework": self.test_framework,
                "unit_command": self.unit_test_command,
                "e2e_command": self.e2e_test_command,
                "coverage_threshold": self.coverage_threshold,
            },
            "blocked_actions": self.blocked_actions,
            "e2e": {
                "enabled": self.e2e_enabled,
                "base_url": self.e2e_base_url,
                "browser": self.e2e_browser,
            },
            "context_tracking": {
                "enabled": self.context_tracking_enabled,
                "budget": self.context_budget,
                "warning_threshold": self.context_warning_threshold,
                "critical_threshold": self.context_critical_threshold,
                "show_in_status": self.show_context_in_status,
                "auto_reset_session": self.auto_reset_session,
                "auto_save_handoff": self.auto_save_handoff,
            },
            "output": {
                "compact_mode": self.output_compact_mode,
                "max_lines": self.output_max_lines,
                "max_files_shown": self.output_max_files_shown,
                "truncate_long_values": self.output_truncate_long_values,
            },
            "delegation": {
                "enabled": self.delegation_enabled,
                "auto_delegate": self.delegation_auto,
                "parallel_limit": self.delegation_parallel_limit,
            },
        }


class Initializer:
    """Interactive project initializer."""

    LANGUAGE_CHOICES = [
        {"name": "Python", "value": "python"},
        {"name": "JavaScript", "value": "javascript"},
        {"name": "TypeScript", "value": "typescript"},
        {"name": "Go", "value": "go"},
        {"name": "Rust", "value": "rust"},
        {"name": "Other", "value": "other"},
    ]

    FRAMEWORK_CHOICES = {
        "python": [
            {"name": "Flask", "value": "flask"},
            {"name": "Django", "value": "django"},
            {"name": "FastAPI", "value": "fastapi"},
            {"name": "None/CLI", "value": None},
        ],
        "javascript": [
            {"name": "Express.js", "value": "express"},
            {"name": "Next.js", "value": "nextjs"},
            {"name": "React (frontend)", "value": "react"},
            {"name": "Vue.js", "value": "vue"},
            {"name": "None/Vanilla", "value": None},
        ],
        "typescript": [
            {"name": "Express.js", "value": "express"},
            {"name": "Next.js", "value": "nextjs"},
            {"name": "NestJS", "value": "nestjs"},
            {"name": "React (frontend)", "value": "react"},
            {"name": "None", "value": None},
        ],
    }

    DATABASE_CHOICES = [
        {"name": "PostgreSQL", "value": "postgresql"},
        {"name": "MySQL", "value": "mysql"},
        {"name": "SQLite", "value": "sqlite"},
        {"name": "MongoDB", "value": "mongodb"},
        {"name": "Redis", "value": "redis"},
        {"name": "None", "value": None},
    ]

    TEST_FRAMEWORK_CHOICES = {
        "python": [
            {"name": "pytest", "value": "pytest"},
            {"name": "unittest", "value": "unittest"},
        ],
        "javascript": [
            {"name": "Jest", "value": "jest"},
            {"name": "Vitest", "value": "vitest"},
            {"name": "Mocha", "value": "mocha"},
        ],
        "typescript": [
            {"name": "Jest", "value": "jest"},
            {"name": "Vitest", "value": "vitest"},
        ],
    }

    def __init__(self, project_path: str, non_interactive: bool = False):
        """Initialize with project path.

        Args:
            project_path: Path to the project directory
            non_interactive: If True, skip prompts and use detected/default values
        """
        self.project_path = Path(project_path).resolve()
        self.detected: Optional[DetectedStack] = None
        self.config = HarnessConfig()
        self.is_existing_project = False
        self.non_interactive = non_interactive

        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=PackageLoader("claude_harness", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def run(self) -> HarnessConfig:
        """Run the initialization process.

        If non_interactive is True, uses detected/default values without prompts.
        """
        self._print_header()
        self._detect_existing_stack()

        if self.non_interactive:
            self._apply_defaults()
        else:
            self._ask_questions()

        self._generate_files()
        self._print_summary()

        return self.config

    def _apply_defaults(self):
        """Apply detected/default values without prompting (non-interactive mode)."""
        console.print("[yellow]Non-interactive mode: using detected/default values[/yellow]\n")

        # Project name - use directory name
        self.config.project_name = self.project_path.name

        # Use detected values if available, otherwise use defaults
        if self.detected:
            self.config.language = self.detected.language or "python"
            self.config.framework = self.detected.framework
            self.config.database = self.detected.database
            self.config.orm = self.detected.orm
            self.config.source_directory = self.detected.source_directory or "."
            self.config.venv_path = self.detected.venv_path or "venv"
            self.config.env_file = self.detected.env_file or ".env"
            self.config.test_directory = self.detected.test_directory or "tests"
            self.config.test_framework = self.detected.test_framework or "pytest"
        else:
            # Pure defaults for empty/new projects
            self.config.language = "python"
            self.config.source_directory = "."
            self.config.venv_path = "venv"
            self.config.env_file = ".env"
            self.config.test_directory = "tests"
            self.config.test_framework = "pytest"

        # Set port and start command based on detected/default stack
        self.config.port = self._get_default_port()
        self.config.start_command = self._get_default_start_command()
        self.config.e2e_base_url = f"http://localhost:{self.config.port}"

        # Set test commands
        self._set_test_commands()

        # Enable standard features
        self.config.e2e_enabled = True
        self.config.create_claude_hooks = True
        self.config.context_tracking_enabled = True

        # Log what was configured
        console.print("[bold]Configuration applied:[/bold]")
        console.print(f"  Project: {self.config.project_name}")
        console.print(f"  Language: {self.config.language}")
        console.print(f"  Framework: {self.config.framework or 'None'}")
        console.print(f"  Database: {self.config.database or 'None'}")
        console.print(f"  Port: {self.config.port}")
        console.print(f"  Test Framework: {self.config.test_framework}")
        console.print()

    def _print_header(self):
        """Print welcome header."""
        console.print()
        console.print(
            Panel.fit(
                "[bold blue]Claude Harness[/bold blue] - Project Initialization\n"
                "[dim]Optimizing your Claude Code workflow[/dim]",
                border_style="blue",
            )
        )
        console.print()

    def _detect_existing_stack(self):
        """Run stack detection and show results."""
        console.print("[yellow]Analyzing project...[/yellow]")

        detector = StackDetector(str(self.project_path))
        self.detected = detector.detect()

        # Determine if this is an existing project
        self.is_existing_project = (
            self.detected.language is not None or self.detected.has_git
        )

        if self.is_existing_project and self.detected.confidence > 0.3:
            self._show_detection_results()
        else:
            console.print(
                "[dim]New project detected - will ask for full configuration[/dim]\n"
            )

    def _show_detection_results(self):
        """Display what was detected."""
        console.print()
        table = Table(title="Detected Configuration", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Detected Value", style="green")

        if self.detected.language:
            table.add_row("Language", self.detected.language)
        if self.detected.framework:
            table.add_row("Framework", self.detected.framework)
        if self.detected.database:
            table.add_row("Database", self.detected.database)
        if self.detected.test_framework:
            table.add_row("Test Framework", self.detected.test_framework)
        if self.detected.source_directory:
            table.add_row("Source Directory", self.detected.source_directory)
        if self.detected.venv_path:
            table.add_row("Virtual Env", self.detected.venv_path)
        if self.detected.has_git:
            table.add_row("Git", "Yes")
        if self.detected.has_kubernetes:
            table.add_row("Kubernetes", "Yes")
        if self.detected.has_claude_md:
            table.add_row("Existing CLAUDE.md", "Yes (will enhance)")

        console.print(table)
        console.print(
            f"[dim]Detection confidence: {self.detected.confidence * 100:.0f}%[/dim]\n"
        )

        for note in self.detected.detection_notes:
            console.print(f"  [dim]- {note}[/dim]")
        console.print()

    def _ask_questions(self):
        """Ask interactive questions."""
        # Project name
        default_name = self.project_path.name
        self.config.project_name = questionary.text(
            "Project name:",
            default=default_name,
        ).ask()

        # Project description
        self.config.project_description = questionary.text(
            "Short description (optional):",
            default="",
        ).ask()

        # Language - use detected or ask
        if self.detected and self.detected.language:
            use_detected = questionary.confirm(
                f"Use detected language ({self.detected.language})?",
                default=True,
            ).ask()

            if use_detected:
                self.config.language = self.detected.language
            else:
                self._ask_language()
        else:
            self._ask_language()

        # Framework
        if self.detected and self.detected.framework:
            use_detected = questionary.confirm(
                f"Use detected framework ({self.detected.framework})?",
                default=True,
            ).ask()

            if use_detected:
                self.config.framework = self.detected.framework
            else:
                self._ask_framework()
        else:
            self._ask_framework()

        # Database
        if self.detected and self.detected.database:
            use_detected = questionary.confirm(
                f"Use detected database ({self.detected.database})?",
                default=True,
            ).ask()

            if use_detected:
                self.config.database = self.detected.database
            else:
                self._ask_database()
        else:
            self._ask_database()

        # Paths
        self._ask_paths()

        # Startup configuration
        self._ask_startup()

        # Testing
        self._ask_testing()

        # Git workflow
        self._ask_git()

        # Initial features (optional)
        self._ask_initial_features()

        # Claude Code hooks
        self._ask_claude_hooks()

    def _ask_language(self):
        """Ask for programming language."""
        choice = questionary.select(
            "Primary programming language:",
            choices=[c["name"] for c in self.LANGUAGE_CHOICES],
        ).ask()

        for c in self.LANGUAGE_CHOICES:
            if c["name"] == choice:
                self.config.language = c["value"]
                break

    def _ask_framework(self):
        """Ask for framework based on language."""
        frameworks = self.FRAMEWORK_CHOICES.get(self.config.language, [])

        if frameworks:
            choice = questionary.select(
                "Framework:",
                choices=[c["name"] for c in frameworks],
            ).ask()

            for c in frameworks:
                if c["name"] == choice:
                    self.config.framework = c["value"]
                    break

    def _ask_database(self):
        """Ask for database."""
        choice = questionary.select(
            "Database:",
            choices=[c["name"] for c in self.DATABASE_CHOICES],
        ).ask()

        for c in self.DATABASE_CHOICES:
            if c["name"] == choice:
                self.config.database = c["value"]
                break

    def _ask_paths(self):
        """Ask for project paths."""
        console.print("\n[bold]Project Paths[/bold]")

        # Source directory
        default_source = self.detected.source_directory if self.detected else "."
        self.config.source_directory = questionary.text(
            "Source directory:",
            default=default_source or ".",
        ).ask()

        # Backend directory (for monorepos)
        if self.detected and self.detected.source_directory:
            if "backend" in self.detected.source_directory:
                self.config.backend_directory = questionary.text(
                    "Backend directory (if separate):",
                    default="backend",
                ).ask()

        # Virtual environment
        if self.config.language == "python":
            default_venv = self.detected.venv_path if self.detected else "venv"
            self.config.venv_path = questionary.text(
                "Virtual environment path:",
                default=default_venv or "venv",
            ).ask()

        # Env file
        default_env = self.detected.env_file if self.detected else ".env"
        self.config.env_file = questionary.text(
            "Environment file:",
            default=default_env or ".env",
        ).ask()

        # Test directory
        default_tests = self.detected.test_directory if self.detected else "tests"
        self.config.test_directory = questionary.text(
            "Test directory:",
            default=default_tests or "tests",
        ).ask()

    def _ask_startup(self):
        """Ask for startup configuration."""
        console.print("\n[bold]Startup Configuration[/bold]")

        # Port
        default_port = self._get_default_port()
        port_str = questionary.text(
            "Development server port:",
            default=str(default_port),
        ).ask()
        self.config.port = int(port_str)

        # Health endpoint
        self.config.health_endpoint = questionary.text(
            "Health check endpoint:",
            default="/api/v1/health" if self.config.framework else "/health",
        ).ask()

        # Start command
        default_start = self._get_default_start_command()
        self.config.start_command = questionary.text(
            "Start command:",
            default=default_start,
        ).ask()

        # E2E base URL
        self.config.e2e_base_url = f"http://localhost:{self.config.port}"

    def _get_default_port(self) -> int:
        """Get default port based on framework."""
        port_defaults = {
            "flask": 5000,
            "django": 8000,
            "fastapi": 8000,
            "express": 3000,
            "nextjs": 3000,
            "react": 3000,
            "vue": 8080,
        }
        return port_defaults.get(self.config.framework or "", 8000)

    def _get_default_start_command(self) -> str:
        """Get default start command based on stack."""
        if self.config.language == "python":
            if self.config.framework == "flask":
                return "python run.py"
            elif self.config.framework == "django":
                return "python manage.py runserver"
            elif self.config.framework == "fastapi":
                return "uvicorn main:app --reload"
            else:
                return "python main.py"
        elif self.config.language in ("javascript", "typescript"):
            return "npm run dev"
        else:
            return "./run.sh"

    def _ask_testing(self):
        """Ask for testing configuration."""
        console.print("\n[bold]Testing Configuration[/bold]")

        # Test framework
        frameworks = self.TEST_FRAMEWORK_CHOICES.get(self.config.language, [])
        default_framework = self.detected.test_framework if self.detected else None

        if frameworks:
            if default_framework:
                self.config.test_framework = default_framework
                console.print(f"[dim]Using detected test framework: {default_framework}[/dim]")
            else:
                choice = questionary.select(
                    "Test framework:",
                    choices=[c["name"] for c in frameworks],
                ).ask()

                for c in frameworks:
                    if c["name"] == choice:
                        self.config.test_framework = c["value"]
                        break

        # Coverage threshold
        coverage_str = questionary.text(
            "Minimum coverage threshold (%):",
            default="80",
        ).ask()
        self.config.coverage_threshold = int(coverage_str)

        # E2E enabled
        self.config.e2e_enabled = questionary.confirm(
            "Enable E2E testing with Playwright?",
            default=True,
        ).ask()

        # Set test commands
        self._set_test_commands()

    def _set_test_commands(self):
        """Set test commands based on framework."""
        test_dir = self.config.test_directory

        if self.config.test_framework == "pytest":
            self.config.unit_test_command = f"pytest {test_dir}/unit/ -v"
            self.config.e2e_test_command = "pytest e2e/ -v"
        elif self.config.test_framework == "jest":
            self.config.unit_test_command = "npm test"
            self.config.e2e_test_command = "npm run test:e2e"
        elif self.config.test_framework == "vitest":
            self.config.unit_test_command = "npm run test:unit"
            self.config.e2e_test_command = "npm run test:e2e"

    def _ask_git(self):
        """Ask for Git workflow configuration."""
        console.print("\n[bold]Git Workflow[/bold]")

        # Protected branches
        branches = questionary.text(
            "Protected branches (comma-separated):",
            default="main, master",
        ).ask()
        self.config.protected_branches = [b.strip() for b in branches.split(",")]

        # Require confirmation
        self.config.require_merge_confirmation = questionary.confirm(
            "Require explicit confirmation before merging to protected branches?",
            default=True,
        ).ask()

    def _ask_initial_features(self):
        """Ask for initial features to track."""
        console.print("\n[bold]Initial Feature Setup[/bold]")

        add_features = questionary.confirm(
            "Add initial features to track?",
            default=False,
        ).ask()

        if add_features:
            self.config.initial_phase = questionary.text(
                "Current phase name:",
                default="Phase 1",
            ).ask()

            console.print("[dim]Enter features one per line. Empty line to finish.[/dim]")
            features = []

            while True:
                feature = questionary.text(
                    f"Feature {len(features) + 1}:",
                    default="",
                ).ask()

                if not feature:
                    break

                features.append(
                    {
                        "id": f"F-{len(features) + 1:03d}",
                        "name": feature,
                        "status": "pending",
                        "tests_passing": False,
                        "e2e_validated": False,
                        "subtasks": [],
                    }
                )

            self.config.initial_features = features

    def _ask_claude_hooks(self):
        """Ask about auto-creating Claude Code hooks configuration."""
        console.print("\n[bold]Claude Code Hooks[/bold]")
        console.print(
            "[dim]Hooks integrate with Claude Code for automatic tracking and safety enforcement.[/dim]"
        )

        self.config.create_claude_hooks = questionary.confirm(
            "Auto-create .claude/settings.local.json with harness hooks?",
            default=True,
        ).ask()

        if self.config.create_claude_hooks:
            console.print(
                "[dim]  Will create hooks for: git safety, context tracking, activity logging[/dim]"
            )

    def _generate_files(self):
        """Generate all harness files."""
        console.print("\n[yellow]Generating harness files...[/yellow]")

        # Create directories
        harness_dir = self.project_path / ".claude-harness"
        harness_dir.mkdir(exist_ok=True)
        (harness_dir / "hooks").mkdir(exist_ok=True)
        (harness_dir / "session-history").mkdir(exist_ok=True)

        scripts_dir = self.project_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        if self.config.e2e_enabled:
            e2e_dir = self.project_path / "e2e"
            e2e_dir.mkdir(exist_ok=True)
            (e2e_dir / "tests").mkdir(exist_ok=True)

        # Generate config.json
        self._write_config()

        # Generate features.json
        self._write_features()

        # Generate progress.md
        self._write_progress()

        # Generate init.sh
        self._write_init_script()

        # Generate init.ps1 (PowerShell)
        self._write_init_powershell()

        # Generate hooks
        self._write_hooks()

        # Update/create CLAUDE.md
        self._update_claude_md()

        # Create Claude Code settings with hooks if requested
        if self.config.create_claude_hooks:
            self._write_claude_settings()

        # Generate E2E setup if enabled
        if self.config.e2e_enabled:
            self._write_e2e_setup()

        # Generate slash commands for Claude Code integration
        self._write_slash_commands()

    def _write_config(self):
        """Write config.json."""
        config_path = self.project_path / ".claude-harness" / "config.json"
        config_data = self.config.to_dict()

        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        console.print(f"  [green]Created:[/green] .claude-harness/config.json")

    def _write_features(self):
        """Write features.json."""
        features_path = self.project_path / ".claude-harness" / "features.json"

        features_data = {
            "current_phase": self.config.initial_phase,
            "features": self.config.initial_features,
            "completed": [],
            "blocked": [],
        }

        with open(features_path, "w") as f:
            json.dump(features_data, f, indent=2)

        console.print(f"  [green]Created:[/green] .claude-harness/features.json")

    def _write_progress(self):
        """Write progress.md."""
        progress_path = self.project_path / ".claude-harness" / "progress.md"

        from datetime import datetime, timezone

        content = f"""# Session Progress Log

## Last Session: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC

### Completed This Session
- [x] Initialized Claude Harness

### Current Work In Progress
- [ ] No tasks in progress

### Blockers
- None

### Next Session Should
1. Run `./scripts/init.sh` to verify environment
2. Check `.claude-harness/features.json` for pending features
3. Pick ONE feature to work on

### Context Notes
- Project: {self.config.project_name}
- Stack: {self.config.language} / {self.config.framework or "None"}
- Database: {self.config.database or "None"}

### Files Modified This Session
- .claude-harness/config.json (created)
- .claude-harness/features.json (created)
- .claude-harness/progress.md (created)
- scripts/init.sh (created)

---
## Previous Sessions
(No previous sessions)
"""

        with open(progress_path, "w") as f:
            f.write(content)

        console.print(f"  [green]Created:[/green] .claude-harness/progress.md")

    def _write_init_script(self):
        """Write init.sh startup script."""
        init_path = self.project_path / "scripts" / "init.sh"

        # Build script based on config
        script = self._build_init_script()

        with open(init_path, "w") as f:
            f.write(script)

        # Make executable
        os.chmod(init_path, 0o755)

        console.print(f"  [green]Created:[/green] scripts/init.sh")

    def _build_init_script(self) -> str:
        """Build the init.sh script content."""
        backend_dir = self.config.backend_directory or self.config.source_directory
        if backend_dir == ".":
            backend_dir = ""

        script = f'''#!/bin/bash
# Claude Harness - Session Initialization Script
# Project: {self.config.project_name}
# Generated by claude-harness

set -e

# Colors
GREEN='\\033[0;32m'
RED='\\033[0;31m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

HARNESS_DIR=".claude-harness"
CONFIG="$HARNESS_DIR/config.json"

echo ""
echo -e "${{BLUE}}=======================================================${{NC}}"
echo -e "${{BLUE}}  CLAUDE HARNESS - Session Initialization${{NC}}"
echo -e "${{BLUE}}  Project: {self.config.project_name}${{NC}}"
echo -e "${{BLUE}}=======================================================${{NC}}"
echo ""

# Check harness exists
if [[ ! -f "$CONFIG" ]]; then
    echo -e "${{RED}}ERROR: Harness not initialized. Run 'claude-harness init' first.${{NC}}"
    exit 1
fi

# 1. Git Status
echo -e "${{YELLOW}}[1/6] GIT STATUS${{NC}}"
if command -v git &> /dev/null && [[ -d ".git" ]]; then
    BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    PROTECTED_BRANCHES="{" ".join(self.config.protected_branches)}"

    if [[ " $PROTECTED_BRANCHES " =~ " $BRANCH " ]]; then
        echo -e "${{RED}}  WARNING: On protected branch '$BRANCH'!${{NC}}"
        echo -e "${{RED}}  Create a feature branch before making changes.${{NC}}"
    else
        echo -e "${{GREEN}}  Branch: $BRANCH${{NC}}"
    fi

    # Check for uncommitted changes
    if [[ -n $(git status --porcelain 2>/dev/null) ]]; then
        echo -e "${{YELLOW}}  Uncommitted changes detected${{NC}}"
    fi
else
    echo -e "${{YELLOW}}  Git not available or not a repository${{NC}}"
fi
echo ""
'''

        # Python-specific setup
        if self.config.language == "python" and self.config.venv_path:
            venv_activate = f"{backend_dir}/{self.config.venv_path}/bin/activate" if backend_dir else f"{self.config.venv_path}/bin/activate"
            venv_activate = venv_activate.lstrip("/")

            script += f'''
# 2. Virtual Environment
echo -e "${{YELLOW}}[2/6] VIRTUAL ENVIRONMENT${{NC}}"
VENV_PATH="{venv_activate}"
if [[ -f "$VENV_PATH" ]]; then
    source "$VENV_PATH" 2>/dev/null
    echo -e "${{GREEN}}  Activated: {self.config.venv_path}${{NC}}"
else
    echo -e "${{RED}}  Virtual environment not found at {self.config.venv_path}${{NC}}"
    echo -e "${{YELLOW}}  Run: python -m venv {self.config.venv_path}${{NC}}"
fi
echo ""
'''
        else:
            script += '''
# 2. Environment (skip for non-Python)
echo -e "${YELLOW}[2/6] ENVIRONMENT${NC}"
echo -e "${GREEN}  No virtual environment needed${NC}"
echo ""
'''

        # App status check
        script += f'''
# 3. Application Status
echo -e "${{YELLOW}}[3/6] APPLICATION${{NC}}"
PORT={self.config.port}
HEALTH_URL="http://localhost:$PORT{self.config.health_endpoint}"

if curl -s "$HEALTH_URL" > /dev/null 2>&1; then
    echo -e "${{GREEN}}  App running on port $PORT${{NC}}"
    APP_RUNNING=true
else
    echo -e "${{YELLOW}}  App not running on port $PORT${{NC}}"
    APP_RUNNING=false

    # Offer to start
    read -p "  Start the application? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
'''

        # Start command based on stack
        if backend_dir:
            script += f'''        cd {backend_dir}
'''

        if self.config.env_file:
            env_file_path = self.config.env_file
            if backend_dir and not self.config.env_file.startswith(backend_dir):
                env_file_path = self.config.env_file
            script += f'''        if [[ -f "{env_file_path}" ]]; then
            export $(grep -v '^#' {env_file_path} | xargs) 2>/dev/null
        fi
'''

        script += f'''        echo -e "${{YELLOW}}  Starting: {self.config.start_command}${{NC}}"
        nohup {self.config.start_command} > /tmp/{self.config.project_name.lower().replace(" ", "_")}.log 2>&1 &
        sleep 3

        if curl -s "$HEALTH_URL" > /dev/null 2>&1; then
            echo -e "${{GREEN}}  App started successfully${{NC}}"
        else
            echo -e "${{RED}}  Failed to start. Check /tmp/{self.config.project_name.lower().replace(" ", "_")}.log${{NC}}"
        fi
'''

        if backend_dir:
            script += '''        cd - > /dev/null
'''

        script += '''    fi
fi
echo ""
'''

        # Database check (for Python with SQLAlchemy)
        if self.config.database and self.config.language == "python":
            script += f'''
# 4. Database Connection
echo -e "${{YELLOW}}[4/6] DATABASE ({self.config.database})${{NC}}"
'''
            if backend_dir:
                script += f'''cd {backend_dir}
'''
            script += '''python3 -c "
try:
    from app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        db.engine.connect()
        print('  Connected successfully')
except Exception as e:
    print(f'  Connection failed: {e}')
" 2>/dev/null || echo -e "${YELLOW}  Could not verify database connection${NC}"
'''
            if backend_dir:
                script += '''cd - > /dev/null
'''
            script += '''echo ""
'''
        else:
            script += '''
# 4. Database (skip)
echo -e "${YELLOW}[4/6] DATABASE${NC}"
echo -e "${GREEN}  No database configured${NC}"
echo ""
'''

        # Test status
        script += f'''
# 5. Test Status
echo -e "${{YELLOW}}[5/6] TESTS${{NC}}"
'''
        if backend_dir:
            script += f'''cd {backend_dir}
'''

        if self.config.test_framework == "pytest":
            script += f'''if command -v pytest &> /dev/null; then
    UNIT_RESULT=$({self.config.unit_test_command} --tb=no -q 2>&1 | tail -3)
    echo -e "  $UNIT_RESULT"
else
    echo -e "${{YELLOW}}  pytest not available${{NC}}"
fi
'''
        else:
            script += f'''echo -e "${{YELLOW}}  Run: {self.config.unit_test_command}${{NC}}"
'''

        if backend_dir:
            script += '''cd - > /dev/null
'''
        script += '''echo ""
'''

        # Session progress
        script += '''
# 6. Session Progress
echo -e "${YELLOW}[6/6] SESSION PROGRESS${NC}"
PROGRESS_FILE="$HARNESS_DIR/progress.md"
FEATURES_FILE="$HARNESS_DIR/features.json"

if [[ -f "$PROGRESS_FILE" ]]; then
    echo ""
    echo -e "${BLUE}--- Last Session Summary ---${NC}"
    # Show relevant sections from progress.md
    sed -n '/^## Last Session/,/^## Previous/p' "$PROGRESS_FILE" | head -25
    echo -e "${BLUE}----------------------------${NC}"
fi

if [[ -f "$FEATURES_FILE" ]] && command -v jq &> /dev/null; then
    echo ""
    CURRENT_PHASE=$(jq -r '.current_phase' "$FEATURES_FILE")
    echo -e "  Current Phase: ${GREEN}$CURRENT_PHASE${NC}"

    IN_PROGRESS=$(jq -r '.features[] | select(.status == "in_progress") | "\\(.id): \\(.name)"' "$FEATURES_FILE" 2>/dev/null | head -1)
    if [[ -n "$IN_PROGRESS" ]]; then
        echo -e "  In Progress: ${YELLOW}$IN_PROGRESS${NC}"
    else
        NEXT_PENDING=$(jq -r '.features[] | select(.status == "pending") | "\\(.id): \\(.name)"' "$FEATURES_FILE" 2>/dev/null | head -1)
        if [[ -n "$NEXT_PENDING" ]]; then
            echo -e "  Next Pending: ${BLUE}$NEXT_PENDING${NC}"
        fi
    fi
fi

echo ""
echo -e "${BLUE}}=======================================================${NC}"
echo -e "${GREEN}  Ready to work!${NC}"
echo -e "${BLUE}  Read .claude-harness/progress.md for full context${NC}"
echo -e "${BLUE}=======================================================${NC}"
echo ""
'''

        return script

    def _write_init_powershell(self):
        """Write init.ps1 PowerShell startup script."""
        init_path = self.project_path / "scripts" / "init.ps1"

        script = self._build_init_powershell()

        with open(init_path, "w") as f:
            f.write(script)

        console.print(f"  [green]Created:[/green] scripts/init.ps1")

    def _build_init_powershell(self) -> str:
        """Build the init.ps1 PowerShell script content."""
        backend_dir = self.config.backend_directory or self.config.source_directory
        if backend_dir == ".":
            backend_dir = ""

        script = f'''#Requires -Version 7.0
<#
.SYNOPSIS
    Claude Harness - Session Initialization Script (PowerShell)
.DESCRIPTION
    Project: {self.config.project_name}
    Generated by claude-harness
.NOTES
    Run this at the start of each Claude Code session
#>

$ErrorActionPreference = 'Continue'

# Configuration
$HarnessDir = ".claude-harness"
$ConfigFile = "$HarnessDir/config.json"

function Write-ColorOutput {{
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}}

# Header
Write-Host ""
Write-ColorOutput "=======================================================" "Blue"
Write-ColorOutput "  CLAUDE HARNESS - Session Initialization" "Blue"
Write-ColorOutput "  Project: {self.config.project_name}" "Blue"
Write-ColorOutput "=======================================================" "Blue"
Write-Host ""

# Check harness exists
if (-not (Test-Path $ConfigFile)) {{
    Write-ColorOutput "ERROR: Harness not initialized. Run 'claude-harness init' first." "Red"
    exit 1
}}

# 1. Git Status
Write-ColorOutput "[1/6] GIT STATUS" "Yellow"
if (Get-Command git -ErrorAction SilentlyContinue) {{
    if (Test-Path ".git") {{
        $branch = git branch --show-current 2>$null
        $protectedBranches = @({", ".join(f'"{b}"' for b in self.config.protected_branches)})

        if ($protectedBranches -contains $branch) {{
            Write-ColorOutput "  WARNING: On protected branch '$branch'!" "Red"
            Write-ColorOutput "  Create a feature branch before making changes." "Red"
        }} else {{
            Write-ColorOutput "  Branch: $branch" "Green"
        }}

        # Check for uncommitted changes
        $status = git status --porcelain 2>$null
        if ($status) {{
            Write-ColorOutput "  Uncommitted changes detected" "Yellow"
        }}
    }} else {{
        Write-ColorOutput "  Not a git repository" "Yellow"
    }}
}} else {{
    Write-ColorOutput "  Git not available" "Yellow"
}}
Write-Host ""
'''

        # Python-specific setup
        if self.config.language == "python" and self.config.venv_path:
            venv_activate = f"{backend_dir}/{self.config.venv_path}/Scripts/Activate.ps1" if backend_dir else f"{self.config.venv_path}/Scripts/Activate.ps1"
            venv_activate = venv_activate.lstrip("/")

            script += f'''
# 2. Virtual Environment
Write-ColorOutput "[2/6] VIRTUAL ENVIRONMENT" "Yellow"
$venvActivate = "{venv_activate}"
if (Test-Path $venvActivate) {{
    try {{
        & $venvActivate
        Write-ColorOutput "  Activated: {self.config.venv_path}" "Green"
    }} catch {{
        Write-ColorOutput "  Failed to activate venv: $_" "Red"
    }}
}} else {{
    Write-ColorOutput "  Virtual environment not found at {self.config.venv_path}" "Red"
    Write-ColorOutput "  Run: python -m venv {self.config.venv_path}" "Yellow"
}}
Write-Host ""
'''
        else:
            script += '''
# 2. Environment (skip for non-Python)
Write-ColorOutput "[2/6] ENVIRONMENT" "Yellow"
Write-ColorOutput "  No virtual environment needed" "Green"
Write-Host ""
'''

        # App status check
        script += f'''
# 3. Application Status
Write-ColorOutput "[3/6] APPLICATION" "Yellow"
$port = {self.config.port}
$healthUrl = "http://localhost:$port{self.config.health_endpoint}"

try {{
    $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    Write-ColorOutput "  App running on port $port" "Green"
    $appRunning = $true
}} catch {{
    Write-ColorOutput "  App not running on port $port" "Yellow"
    $appRunning = $false

    $startApp = Read-Host "  Start the application? (y/N)"
    if ($startApp -eq 'y' -or $startApp -eq 'Y') {{
'''

        # Start command based on stack
        if backend_dir:
            script += f'''        Push-Location "{backend_dir}"
'''

        if self.config.env_file:
            script += f'''        # Load environment from .env
        if (Test-Path "{self.config.env_file}") {{
            Get-Content "{self.config.env_file}" | ForEach-Object {{
                if ($_ -match '^([^#][^=]+)=(.*)$') {{
                    [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
                }}
            }}
        }}
'''

        script += f'''        Write-ColorOutput "  Starting: {self.config.start_command}" "Yellow"
        Start-Process -FilePath "pwsh" -ArgumentList "-Command", "{self.config.start_command}" -WindowStyle Hidden
        Start-Sleep -Seconds 3

        try {{
            $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            Write-ColorOutput "  App started successfully" "Green"
        }} catch {{
            Write-ColorOutput "  Failed to start. Check logs." "Red"
        }}
'''

        if backend_dir:
            script += '''        Pop-Location
'''

        script += '''    }
}
Write-Host ""
'''

        # Database check
        if self.config.database and self.config.language == "python":
            script += f'''
# 4. Database Connection
Write-ColorOutput "[4/6] DATABASE ({self.config.database})" "Yellow"
'''
            if backend_dir:
                script += f'''Push-Location "{backend_dir}"
'''
            script += '''try {
    $result = python -c @"
try:
    from app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        db.engine.connect()
        print('Connected successfully')
except Exception as e:
    print(f'Connection failed: {e}')
"@
    Write-ColorOutput "  $result" "Green"
} catch {
    Write-ColorOutput "  Could not verify database connection" "Yellow"
}
'''
            if backend_dir:
                script += '''Pop-Location
'''
            script += '''Write-Host ""
'''
        else:
            script += '''
# 4. Database (skip)
Write-ColorOutput "[4/6] DATABASE" "Yellow"
Write-ColorOutput "  No database configured" "Green"
Write-Host ""
'''

        # Test status
        script += f'''
# 5. Test Status
Write-ColorOutput "[5/6] TESTS" "Yellow"
'''
        if backend_dir:
            script += f'''Push-Location "{backend_dir}"
'''

        if self.config.test_framework == "pytest":
            script += f'''if (Get-Command pytest -ErrorAction SilentlyContinue) {{
    try {{
        $testResult = pytest {self.config.test_directory}/unit/ -q --tb=no 2>&1 | Select-Object -Last 3
        Write-Host "  $testResult"
    }} catch {{
        Write-ColorOutput "  Could not run tests" "Yellow"
    }}
}} else {{
    Write-ColorOutput "  pytest not available" "Yellow"
}}
'''
        else:
            script += f'''Write-ColorOutput "  Run: {self.config.unit_test_command}" "Yellow"
'''

        if backend_dir:
            script += '''Pop-Location
'''
        script += '''Write-Host ""
'''

        # Session progress
        script += '''
# 6. Session Progress
Write-ColorOutput "[6/6] SESSION PROGRESS" "Yellow"
$progressFile = "$HarnessDir/progress.md"
$featuresFile = "$HarnessDir/features.json"

if (Test-Path $progressFile) {
    Write-Host ""
    Write-ColorOutput "--- Last Session Summary ---" "Blue"
    $content = Get-Content $progressFile -Raw
    # Show the Last Session section
    if ($content -match '(?s)## Last Session.*?(?=## Previous|$)') {
        $matches[0] -split "`n" | Select-Object -First 25 | ForEach-Object { Write-Host $_ }
    }
    Write-ColorOutput "----------------------------" "Blue"
}

if (Test-Path $featuresFile) {
    Write-Host ""
    $features = Get-Content $featuresFile | ConvertFrom-Json
    Write-ColorOutput "  Current Phase: $($features.current_phase)" "Green"

    $inProgress = $features.features | Where-Object { $_.status -eq "in_progress" } | Select-Object -First 1
    if ($inProgress) {
        Write-ColorOutput "  In Progress: $($inProgress.id): $($inProgress.name)" "Yellow"
    } else {
        $nextPending = $features.features | Where-Object { $_.status -eq "pending" } | Select-Object -First 1
        if ($nextPending) {
            Write-ColorOutput "  Next Pending: $($nextPending.id): $($nextPending.name)" "Blue"
        }
    }
}

Write-Host ""
Write-ColorOutput "=======================================================" "Blue"
Write-ColorOutput "  Ready to work!" "Green"
Write-ColorOutput "  Read .claude-harness/progress.md for full context" "Blue"
Write-ColorOutput "=======================================================" "Blue"
Write-Host ""
'''

        return script

    def _write_hooks(self):
        """Write Claude Code hooks that read JSON from stdin."""
        hooks_dir = self.project_path / ".claude-harness" / "hooks"

        # Git safety hook - PreToolUse for Bash commands
        # Reads JSON from stdin, extracts command, checks for dangerous operations
        git_safety = f'''#!/bin/bash
# Claude Harness - Git Safety Hook (PreToolUse)
# Blocks dangerous git operations
# Input: JSON via stdin with tool_input.command

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract the command from tool_input
COMMAND=$(echo "$INPUT_JSON" | jq -r '.tool_input.command // empty' 2>/dev/null)

# If no command found, allow
[ -z "$COMMAND" ] && exit 0

PROTECTED_BRANCHES="{" ".join(self.config.protected_branches)}"

# Check current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# Block commits on protected branches
for branch in $PROTECTED_BRANCHES; do
    if [ "$CURRENT_BRANCH" = "$branch" ]; then
        if echo "$COMMAND" | grep -qE "^git commit"; then
            echo "BLOCKED: Cannot commit on protected branch '$branch'. Create a feature branch first." >&2
            exit 2
        fi
    fi
done

# Block force pushes to protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$COMMAND" | grep -qE "git push.*(-f|--force).*($branch|origin/$branch)"; then
        echo "BLOCKED: Cannot force push to protected branch '$branch'." >&2
        exit 2
    fi
done

# Block destructive rebase on protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$COMMAND" | grep -qE "git rebase.*(origin/)?$branch"; then
        if [ "$CURRENT_BRANCH" = "$branch" ]; then
            echo "BLOCKED: Cannot rebase on protected branch '$branch'." >&2
            exit 2
        fi
    fi
done

exit 0
'''

        git_safety_path = hooks_dir / "check-git-safety.sh"
        with open(git_safety_path, "w") as f:
            f.write(git_safety)
        os.chmod(git_safety_path, 0o755)

        # Track Read hook - PostToolUse for Read tool
        track_read = '''#!/bin/bash
# Claude Harness - Track File Read (PostToolUse)
# Tracks files read for context estimation
# Input: JSON via stdin with tool_input.file_path

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Skip if no file path or harness not initialized
[ -z "$FILE_PATH" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

# Get file size for token estimation
if [ -f "$FILE_PATH" ]; then
    CHAR_COUNT=$(wc -c < "$FILE_PATH" 2>/dev/null || echo 1000)
    claude-harness context track-file "$FILE_PATH" "$CHAR_COUNT" 2>/dev/null || true
fi

exit 0
'''

        track_read_path = hooks_dir / "track-read.sh"
        with open(track_read_path, "w") as f:
            f.write(track_read)
        os.chmod(track_read_path, 0o755)

        # Track Write hook - PostToolUse for Write tool
        track_write = '''#!/bin/bash
# Claude Harness - Track File Write (PostToolUse)
# Tracks files written for progress tracking
# Input: JSON via stdin with tool_input.file_path

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Skip if no file path or harness not initialized
[ -z "$FILE_PATH" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

# Skip harness internal files
case "$FILE_PATH" in
    */.claude-harness/*|*/.git/*|*.log|*.pyc|*/__pycache__/*|*/node_modules/*|*.env*)
        exit 0
        ;;
esac

# Track the file in progress
claude-harness progress file "$FILE_PATH" 2>/dev/null || true

# Also track in context (estimate tokens for content written)
CONTENT_LENGTH=$(echo "$INPUT_JSON" | jq -r '.tool_input.content // empty' 2>/dev/null | wc -c)
if [ "$CONTENT_LENGTH" -gt 0 ]; then
    claude-harness context track-file "$FILE_PATH" "$CONTENT_LENGTH" 2>/dev/null || true
fi

exit 0
'''

        track_write_path = hooks_dir / "track-write.sh"
        with open(track_write_path, "w") as f:
            f.write(track_write)
        os.chmod(track_write_path, 0o755)

        # Track Edit hook - PostToolUse for Edit tool
        track_edit = '''#!/bin/bash
# Claude Harness - Track File Edit (PostToolUse)
# Tracks files edited for progress tracking
# Input: JSON via stdin with tool_input.file_path

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Skip if no file path or harness not initialized
[ -z "$FILE_PATH" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

# Skip harness internal files
case "$FILE_PATH" in
    */.claude-harness/*|*/.git/*|*.log|*.pyc|*/__pycache__/*|*/node_modules/*|*.env*)
        exit 0
        ;;
esac

# Track the file in progress
claude-harness progress file "$FILE_PATH" 2>/dev/null || true

# Estimate tokens for edit (old_string + new_string)
OLD_LEN=$(echo "$INPUT_JSON" | jq -r '.tool_input.old_string // empty' 2>/dev/null | wc -c)
NEW_LEN=$(echo "$INPUT_JSON" | jq -r '.tool_input.new_string // empty' 2>/dev/null | wc -c)
TOTAL_LEN=$((OLD_LEN + NEW_LEN))
if [ "$TOTAL_LEN" -gt 0 ]; then
    claude-harness context track-file "$FILE_PATH" "$TOTAL_LEN" 2>/dev/null || true
fi

exit 0
'''

        track_edit_path = hooks_dir / "track-edit.sh"
        with open(track_edit_path, "w") as f:
            f.write(track_edit)
        os.chmod(track_edit_path, 0o755)

        # Activity logger hook - PostToolUse for Bash
        activity_logger = '''#!/bin/bash
# Claude Harness - Activity Logger (PostToolUse)
# Logs bash commands for session tracking
# Input: JSON via stdin with tool_input.command

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract command
COMMAND=$(echo "$INPUT_JSON" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Skip if no command or harness not initialized
[ -z "$COMMAND" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

LOG_DIR=".claude-harness/session-history"
LOG_FILE="$LOG_DIR/activity-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
echo "[$(date -Iseconds)] Bash: ${COMMAND:0:200}" >> "$LOG_FILE"

# Track command execution in context
COMMAND_LEN=${#COMMAND}
claude-harness context track-command "$COMMAND_LEN" 2>/dev/null || true

exit 0
'''

        logger_path = hooks_dir / "log-activity.sh"
        with open(logger_path, "w") as f:
            f.write(activity_logger)
        os.chmod(logger_path, 0o755)

        # Session stop hook - shows summary, saves handoff, marks session closed
        session_stop = '''#!/bin/bash
# Claude Harness - Session Stop Hook
# Shows summary, saves handoff, and marks session closed when Claude stops

[ -f ".claude-harness/config.json" ] || exit 0

echo ""
echo "=== Session Summary ==="
claude-harness context show 2>/dev/null || true
echo "---"
claude-harness progress show 2>/dev/null || true
echo "======================="

# Check if auto_save_handoff is enabled (default: true)
AUTO_HANDOFF=$(cat .claude-harness/config.json 2>/dev/null | grep -o '"auto_save_handoff"[[:space:]]*:[[:space:]]*false' || echo "")
if [ -z "$AUTO_HANDOFF" ]; then
    # Auto-save handoff document
    echo ""
    echo "Saving session handoff..."
    claude-harness context handoff --save 2>/dev/null || true
fi

# Mark session as closed for clean restart
claude-harness context session-close 2>/dev/null || true

exit 0
'''

        session_stop_path = hooks_dir / "session-stop.sh"
        with open(session_stop_path, "w") as f:
            f.write(session_stop)
        os.chmod(session_stop_path, 0o755)

        console.print(f"  [green]Created:[/green] .claude-harness/hooks/check-git-safety.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/track-read.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/track-write.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/track-edit.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/log-activity.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/session-stop.sh")

    def _get_default_permissions(self) -> list:
        """Generate default permissions based on detected stack.

        Returns a list of permission patterns that allow common development
        commands without requiring manual approval each session.
        """
        # Common permissions for all projects
        permissions = [
            # Harness commands
            "Bash(claude-harness:*)",
            "Bash(.claude-harness/hooks/*:*)",

            # Git operations
            "Bash(git:*)",

            # Common shell utilities
            "Bash(cat:*)",
            "Bash(ls:*)",
            "Bash(echo:*)",
            "Bash(grep:*)",
            "Bash(find:*)",
            "Bash(tree:*)",
            "Bash(wc:*)",
            "Bash(head:*)",
            "Bash(tail:*)",
            "Bash(mkdir:*)",
            "Bash(cp:*)",
            "Bash(mv:*)",
            "Bash(rm:*)",
            "Bash(chmod:*)",
            "Bash(touch:*)",
            "Bash(diff:*)",
            "Bash(sort:*)",
            "Bash(uniq:*)",
            "Bash(which:*)",
            "Bash(pwd)",
            "Bash(env:*)",
            "Bash(export:*)",
            "Bash(timeout:*)",
            "Bash(bash:*)",
            "Bash(sh:*)",

            # Web tools
            "WebSearch",
            "WebFetch(domain:*)",
        ]

        # Python-specific permissions
        if self.config.language == "python":
            permissions.extend([
                "Bash(python:*)",
                "Bash(python3:*)",
                "Bash(pip:*)",
                "Bash(pip3:*)",
                "Bash(source:*)",
                "Bash(.venv/bin/*:*)",
                "Bash(venv/bin/*:*)",
                "Bash(alembic:*)",
                "Bash(flask:*)",
                "Bash(django-admin:*)",
                "Bash(uvicorn:*)",
                "Bash(gunicorn:*)",
                "Bash(pytest:*)",
                "Bash(mypy:*)",
                "Bash(ruff:*)",
                "Bash(black:*)",
                "Bash(isort:*)",
                "Bash(bandit:*)",
                "Bash(coverage:*)",
            ])

        # JavaScript/TypeScript-specific permissions
        if self.config.language in ["javascript", "typescript"]:
            permissions.extend([
                "Bash(node:*)",
                "Bash(npm:*)",
                "Bash(npx:*)",
                "Bash(yarn:*)",
                "Bash(pnpm:*)",
                "Bash(jest:*)",
                "Bash(vitest:*)",
                "Bash(eslint:*)",
                "Bash(prettier:*)",
                "Bash(tsc:*)",
            ])

        # Go-specific permissions
        if self.config.language == "go":
            permissions.extend([
                "Bash(go:*)",
            ])

        # Rust-specific permissions
        if self.config.language == "rust":
            permissions.extend([
                "Bash(cargo:*)",
                "Bash(rustc:*)",
            ])

        # Docker permissions (if detected)
        if self.config.framework and "docker" in str(self.config.framework).lower():
            permissions.extend([
                "Bash(docker:*)",
                "Bash(docker-compose:*)",
            ])

        # Add write-unit-tests skill if available
        permissions.append("Skill(write-unit-tests)")

        return permissions

    def _write_claude_settings(self):
        """Write Claude Code settings.local.json with harness hooks.

        Uses settings.local.json (project-specific, not committed) rather than
        settings.json to keep harness hooks local to each project instance.
        """
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        settings_path = claude_dir / "settings.local.json"

        # Correct Claude Code hooks format - hooks receive JSON via stdin
        hooks_config = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": ".claude-harness/hooks/check-git-safety.sh"
                            }
                        ]
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [
                            {
                                "type": "command",
                                "command": ".claude-harness/hooks/track-read.sh"
                            }
                        ]
                    },
                    {
                        "matcher": "Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": ".claude-harness/hooks/track-write.sh"
                            }
                        ]
                    },
                    {
                        "matcher": "Edit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": ".claude-harness/hooks/track-edit.sh"
                            }
                        ]
                    },
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": ".claude-harness/hooks/log-activity.sh"
                            }
                        ]
                    }
                ],
                "SessionEnd": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": ".claude-harness/hooks/session-stop.sh"
                            }
                        ]
                    }
                ]
            },
            "permissions": {
                "allow": self._get_default_permissions()
            }
        }

        if settings_path.exists():
            # Merge with existing settings
            try:
                existing = json.loads(settings_path.read_text())

                # Merge hooks - add our hooks to existing
                if "hooks" not in existing:
                    existing["hooks"] = {}

                for hook_type, hook_list in hooks_config["hooks"].items():
                    if hook_type not in existing["hooks"]:
                        existing["hooks"][hook_type] = []
                    # Add our hooks if not already present
                    for hook in hook_list:
                        if hook not in existing["hooks"][hook_type]:
                            existing["hooks"][hook_type].append(hook)

                # Merge permissions
                if "permissions" not in existing:
                    existing["permissions"] = {}
                if "allow" not in existing["permissions"]:
                    existing["permissions"]["allow"] = []
                for perm in hooks_config["permissions"]["allow"]:
                    if perm not in existing["permissions"]["allow"]:
                        existing["permissions"]["allow"].append(perm)

                with open(settings_path, "w") as f:
                    json.dump(existing, f, indent=2)

                console.print(
                    f"  [green]Updated:[/green] .claude/settings.local.json (merged with existing)"
                )
            except json.JSONDecodeError:
                console.print(
                    f"  [yellow]Warning:[/yellow] .claude/settings.local.json exists but is invalid JSON"
                )
                console.print(
                    f"  [yellow]Skipping hooks config - please add manually from docs/HOOKS.md[/yellow]"
                )
        else:
            # Create new settings file
            with open(settings_path, "w") as f:
                json.dump(hooks_config, f, indent=2)
            console.print(f"  [green]Created:[/green] .claude/settings.local.json")

    def _update_claude_md(self):
        """Update or create CLAUDE.md with harness integration."""
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        claude_md_path = claude_dir / "CLAUDE.md"

        harness_section = f'''
# CLAUDE HARNESS INTEGRATION

## SESSION START RITUAL (MANDATORY)

At the START of every session, BEFORE any other work:

1. **Run init script:** `./scripts/init.sh`
2. **Read progress:** `.claude-harness/progress.md`
3. **Check features:** `.claude-harness/features.json`
4. **Pick ONE feature** with status "pending" or continue "in_progress"
5. **Update feature status** to "in_progress" before starting work

## SESSION END RITUAL (MANDATORY)

Before ending a session or when context is getting full:

1. **Update progress.md** with:
   - What was completed
   - Current work in progress
   - Blockers or issues
   - Next steps for the next session
   - Files modified

2. **Update features.json** - Mark completed features, update subtasks

3. **Commit work** if appropriate

## ONE FEATURE AT A TIME

- ALWAYS work on exactly ONE feature from features.json
- Mark it as "in_progress" before starting
- Complete ALL subtasks before marking "completed"
- Run tests before marking as complete
- E2E validation required if e2e_enabled is true

## GIT WORKFLOW

- **NEVER commit to:** {", ".join(self.config.protected_branches)}
- **Branch naming:** {", ".join(self.config.branch_prefixes)}
- **ALWAYS verify branch:** `git branch --show-current`
- **Require confirmation** before merging to protected branches

## BLOCKED ACTIONS

The following are blocked by harness hooks:
{chr(10).join(f"- {action}" for action in self.config.blocked_actions)}

## TESTING REQUIREMENTS

- Unit tests: `{self.config.unit_test_command}`
- E2E tests: `{self.config.e2e_test_command}`
- Coverage threshold: {self.config.coverage_threshold}%
- Features are NOT complete until tests pass

## PROJECT QUICK REFERENCE

- **Port:** {self.config.port}
- **Health endpoint:** {self.config.health_endpoint}
- **Start command:** `{self.config.start_command}`
- **Test framework:** {self.config.test_framework}

---
'''

        # Add delegation section if enabled
        if self.config.delegation_enabled:
            delegation_section = '''
## SUBAGENT DELEGATION

This project uses subagent delegation to preserve main agent context.

### When to Delegate (use Task tool)

**Delegate these tasks to specialized subagents:**
- **Exploration** (`explore` subagent): File discovery, codebase analysis, pattern finding
- **Testing** (`test` subagent): Unit tests, E2E tests, integration tests
- **Documentation** (`document` subagent): READMEs, API docs, code comments
- **Review** (`review` subagent): Security audits, performance analysis, code review

**Keep in main agent:**
- Core feature implementation requiring integration decisions
- User interaction and clarification
- Final validation and commits
- Complex multi-file changes

### Delegation Workflow

1. Check subtasks with: `claude-harness delegation suggest <FEATURE_ID>`
2. For delegatable tasks, use the Task tool with structured prompts
3. Summarize subagent results concisely (under 500 words)
4. Continue with main implementation

### Delegation Prompt Template

When using Task tool for delegation:

```
Feature: [feature_name] (ID: [feature_id])
Subtask: [subtask_name]

Context:
- Relevant files: [list key files]
- Current progress: [brief status]

Task: [detailed description]

Constraints:
- Keep summary under 500 words
- Report absolute file paths
- Include line numbers when relevant

Output: YAML summary with: accomplishments, files, decisions, issues, next_steps
```

### Estimated Context Savings

| Task Type | Without Delegation | With Delegation | Savings |
|-----------|-------------------|-----------------|---------|
| Exploration | ~30K tokens | ~3-5K | 83-90% |
| Test Writing | ~20K tokens | ~5-8K | 60-75% |
| Documentation | ~15K tokens | ~3-5K | 67-80% |
| Code Review | ~25K tokens | ~5-10K | 60-80% |

---
'''
            harness_section += delegation_section

        if claude_md_path.exists():
            # Append to existing
            existing_content = claude_md_path.read_text()

            # Check if harness section already exists
            if "CLAUDE HARNESS INTEGRATION" not in existing_content:
                with open(claude_md_path, "a") as f:
                    f.write("\n" + harness_section)
                console.print(f"  [green]Updated:[/green] .claude/CLAUDE.md (added harness section)")
            else:
                console.print(f"  [yellow]Skipped:[/yellow] .claude/CLAUDE.md (harness section exists)")
        else:
            # Create new
            full_content = f"""# {self.config.project_name}

{self.config.project_description}

{harness_section}

## Project-Specific Rules

(Add your project-specific rules here)

---
**Version:** 1.0
**Maintained by:** Claude Harness
"""
            with open(claude_md_path, "w") as f:
                f.write(full_content)
            console.print(f"  [green]Created:[/green] .claude/CLAUDE.md")

    def _write_e2e_setup(self):
        """Write E2E testing setup files."""
        e2e_dir = self.project_path / "e2e"

        # Create conftest.py for pytest + playwright
        conftest = f'''"""E2E test configuration for Playwright."""
import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context."""
    return {{
        **browser_context_args,
        "base_url": "{self.config.e2e_base_url}",
        "viewport": {{"width": 1280, "height": 720}},
    }}


@pytest.fixture
def authenticated_page(page: Page):
    """Fixture for authenticated page (customize login flow)."""
    # TODO: Implement your login flow
    # page.goto("/login")
    # page.fill("[name=email]", "test@example.com")
    # page.fill("[name=password]", "password")
    # page.click("button[type=submit]")
    # expect(page).to_have_url("/dashboard")
    return page
'''

        conftest_path = e2e_dir / "conftest.py"
        with open(conftest_path, "w") as f:
            f.write(conftest)

        # Create example test
        example_test = f'''"""Example E2E test."""
import pytest
from playwright.sync_api import Page, expect


def test_homepage_loads(page: Page):
    """Test that the homepage loads successfully."""
    page.goto("/")
    # Customize based on your app
    # expect(page).to_have_title("Your App Title")


def test_health_endpoint(page: Page):
    """Test that health endpoint responds."""
    response = page.request.get("{self.config.health_endpoint}")
    assert response.ok
'''

        test_path = e2e_dir / "tests" / "test_example.py"
        with open(test_path, "w") as f:
            f.write(example_test)

        # Create pytest.ini for e2e
        pytest_ini = '''[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
'''

        pytest_ini_path = e2e_dir / "pytest.ini"
        with open(pytest_ini_path, "w") as f:
            f.write(pytest_ini)

        console.print(f"  [green]Created:[/green] e2e/conftest.py")
        console.print(f"  [green]Created:[/green] e2e/tests/test_example.py")
        console.print(f"  [green]Created:[/green] e2e/pytest.ini")

    def _write_slash_commands(self):
        """Write Claude Code slash commands for harness integration."""
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        commands_dir = claude_dir / "commands"
        commands_dir.mkdir(exist_ok=True)

        # Write all harness commands
        created_files = write_commands_to_directory(commands_dir)

        # Generate README for commands
        generate_commands_readme(commands_dir)

        console.print(f"  [green]Created:[/green] .claude/commands/ ({len(created_files)} slash commands)")
        console.print(f"  [green]Created:[/green] .claude/commands/README.md")

    def _print_summary(self):
        """Print initialization summary."""
        console.print()
        console.print(
            Panel.fit(
                "[bold green]Claude Harness Initialized Successfully![/bold green]",
                border_style="green",
            )
        )

        console.print("\n[bold]Next Steps:[/bold]")
        console.print("  1. Review generated files in .claude-harness/")
        console.print("  2. Run [cyan]./scripts/init.sh[/cyan] to verify setup")
        console.print("  3. Add features to .claude-harness/features.json")
        console.print("  4. Start your Claude Code session!")

        if self.config.e2e_enabled:
            console.print("\n[bold]E2E Testing Setup:[/bold]")
            console.print("  1. Install Playwright: [cyan]pip install playwright[/cyan]")
            console.print("  2. Install browsers: [cyan]playwright install[/cyan]")
            console.print("  3. Run E2E tests: [cyan]pytest e2e/[/cyan]")

        console.print("\n[bold]Files Created:[/bold]")
        console.print("  .claude-harness/config.json")
        console.print("  .claude-harness/features.json")
        console.print("  .claude-harness/progress.md")
        console.print("  .claude-harness/hooks/check-git-safety.sh")
        console.print("  .claude-harness/hooks/log-activity.sh")
        console.print("  .claude/CLAUDE.md (created or updated)")
        console.print("  scripts/init.sh")
        console.print("  scripts/init.ps1")

        if self.config.create_claude_hooks:
            console.print("  .claude/settings.local.json (Claude Code hooks)")

        if self.config.e2e_enabled:
            console.print("  e2e/conftest.py")
            console.print("  e2e/tests/test_example.py")
            console.print("  e2e/pytest.ini")

        console.print("  .claude/commands/ (35 slash commands)")
        console.print("  .claude/commands/README.md")

        console.print("\n[bold]Slash Commands Available:[/bold]")
        console.print("  Inside Claude Code, use commands like:")
        console.print("    [cyan]/harness-status[/cyan] - Show current status")
        console.print("    [cyan]/harness-feature-add[/cyan] - Add a new feature")
        console.print("    [cyan]/harness-feature-start[/cyan] - Start working on a feature")
        console.print("    [cyan]/harness-delegation-suggest[/cyan] - Get delegation suggestions")
        console.print("  See .claude/commands/README.md for full list")

        console.print()


def initialize_project(project_path: str, non_interactive: bool = False) -> HarnessConfig:
    """Convenience function to initialize a project.

    Args:
        project_path: Path to the project directory
        non_interactive: If True, skip prompts and use detected/default values.
                        Useful for CI/CD pipelines and automated scripts.

    Returns:
        HarnessConfig with the applied configuration
    """
    initializer = Initializer(project_path, non_interactive=non_interactive)
    return initializer.run()
