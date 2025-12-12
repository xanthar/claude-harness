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

    # Claude Code Integration
    create_claude_hooks: bool = False  # Auto-create .claude/settings.json with hooks

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

    def __init__(self, project_path: str):
        """Initialize with project path."""
        self.project_path = Path(project_path).resolve()
        self.detected: Optional[DetectedStack] = None
        self.config = HarnessConfig()
        self.is_existing_project = False

        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=PackageLoader("claude_harness", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def run(self) -> HarnessConfig:
        """Run the interactive initialization process."""
        self._print_header()
        self._detect_existing_stack()
        self._ask_questions()
        self._generate_files()
        self._print_summary()

        return self.config

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
            "Auto-create .claude/settings.json with harness hooks?",
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

        from datetime import datetime

        content = f"""# Session Progress Log

## Last Session: {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC

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
        """Write Claude Code hooks."""
        hooks_dir = self.project_path / ".claude-harness" / "hooks"

        # Git safety hook
        git_safety = f'''#!/bin/bash
# Claude Harness - Git Safety Hook
# Blocks dangerous git operations

INPUT="$1"
PROTECTED_BRANCHES="{" ".join(self.config.protected_branches)}"

# Block direct commits to protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$INPUT" | grep -qE "git commit.*$branch"; then
        echo "BLOCKED: Cannot commit directly to protected branch '$branch'. Create a feature branch first."
        exit 1
    fi
done

# Block force pushes to protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$INPUT" | grep -qE "git push.*(-f|--force).*$branch"; then
        echo "BLOCKED: Cannot force push to protected branch '$branch'."
        exit 1
    fi
done

# Block backup branch deletion
if echo "$INPUT" | grep -qiE "git branch -[dD].*[Bb]ackup"; then
    echo "BLOCKED: Cannot delete backup branches."
    exit 1
fi

exit 0
'''

        git_safety_path = hooks_dir / "check-git-safety.sh"
        with open(git_safety_path, "w") as f:
            f.write(git_safety)
        os.chmod(git_safety_path, 0o755)

        # Activity logger hook
        activity_logger = '''#!/bin/bash
# Claude Harness - Activity Logger
# Logs tool usage for session tracking

TOOL_NAME="$1"
TOOL_INPUT="$2"
LOG_DIR=".claude-harness/session-history"
LOG_FILE="$LOG_DIR/activity-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
echo "[$(date -Iseconds)] $TOOL_NAME: ${TOOL_INPUT:0:200}" >> "$LOG_FILE"
'''

        logger_path = hooks_dir / "log-activity.sh"
        with open(logger_path, "w") as f:
            f.write(activity_logger)
        os.chmod(logger_path, 0o755)

        # Progress tracking hook
        track_progress = '''#!/bin/bash
# Claude Harness - Auto Progress Tracker
# Automatically tracks modified files in progress.md

FILEPATH="$1"
ACTION="${2:-write}"  # write or edit

# Skip if not a harness project
[ -f ".claude-harness/config.json" ] || exit 0

# Skip harness internal files and common non-code files
case "$FILEPATH" in
    .claude-harness/*|.git/*|*.log|*.pyc|__pycache__/*|node_modules/*|.env*)
        exit 0
        ;;
esac

# Track the file modification
claude-harness progress file "$FILEPATH" 2>/dev/null || true
'''

        track_progress_path = hooks_dir / "track-progress.sh"
        with open(track_progress_path, "w") as f:
            f.write(track_progress)
        os.chmod(track_progress_path, 0o755)

        console.print(f"  [green]Created:[/green] .claude-harness/hooks/check-git-safety.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/log-activity.sh")
        console.print(f"  [green]Created:[/green] .claude-harness/hooks/track-progress.sh")

    def _write_claude_settings(self):
        """Write Claude Code settings.json with harness hooks."""
        claude_dir = self.project_path / ".claude"
        claude_dir.mkdir(exist_ok=True)

        settings_path = claude_dir / "settings.json"

        hooks_config = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "command": "[ -f .claude-harness/hooks/check-git-safety.sh ] && .claude-harness/hooks/check-git-safety.sh \"$TOOL_INPUT\"",
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "Read",
                        "command": "[ -f .claude-harness/config.json ] && claude-harness context track-file \"$TOOL_INPUT\" $(wc -c < \"$TOOL_INPUT\" 2>/dev/null || echo 1000)",
                    },
                    {
                        "matcher": "Write",
                        "command": "[ -f .claude-harness/hooks/track-progress.sh ] && .claude-harness/hooks/track-progress.sh \"$TOOL_INPUT\" write",
                    },
                    {
                        "matcher": "Edit",
                        "command": "[ -f .claude-harness/hooks/track-progress.sh ] && .claude-harness/hooks/track-progress.sh \"$TOOL_INPUT\" edit",
                    },
                    {
                        "matcher": "Bash",
                        "command": "[ -f .claude-harness/hooks/log-activity.sh ] && .claude-harness/hooks/log-activity.sh \"Bash\" \"$TOOL_INPUT\"",
                    },
                ],
                "Stop": [
                    {
                        "command": "[ -f .claude-harness/config.json ] && (claude-harness context show; echo '---'; claude-harness progress show)",
                    }
                ],
            },
            "permissions": {
                "allow": [
                    "Bash(claude-harness:*)",
                ]
            },
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
                    f"  [green]Updated:[/green] .claude/settings.json (merged with existing)"
                )
            except json.JSONDecodeError:
                console.print(
                    f"  [yellow]Warning:[/yellow] .claude/settings.json exists but is invalid JSON"
                )
                console.print(
                    f"  [yellow]Skipping hooks config - please add manually from docs/HOOKS.md[/yellow]"
                )
        else:
            # Create new settings file
            with open(settings_path, "w") as f:
                json.dump(hooks_config, f, indent=2)
            console.print(f"  [green]Created:[/green] .claude/settings.json")

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
            console.print("  .claude/settings.json (Claude Code hooks)")

        if self.config.e2e_enabled:
            console.print("  e2e/conftest.py")
            console.print("  e2e/tests/test_example.py")
            console.print("  e2e/pytest.ini")

        console.print()


def initialize_project(project_path: str) -> HarnessConfig:
    """Convenience function to initialize a project."""
    initializer = Initializer(project_path)
    return initializer.run()
