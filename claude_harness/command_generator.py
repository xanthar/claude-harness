"""Generate Claude Code slash commands for claude-harness integration."""

from pathlib import Path
from typing import Dict, Optional


# All slash command definitions
HARNESS_COMMANDS: Dict[str, Dict[str, str]] = {
    # ========== INITIALIZATION ==========
    "harness-init": {
        "description": "Initialize claude-harness in the current project",
        "content": """Initialize claude-harness for this project.

First, check if claude-harness is already initialized by looking for `.claude-harness/config.json`.

If NOT initialized, help me set up claude-harness by:

1. **Detect the project stack** by running:
   ```bash
   claude-harness detect
   ```

2. **Ask me these questions** (use the detected values as defaults):
   - Project name? (default: current folder name)
   - What language? (default: detected)
   - What framework? (default: detected)
   - What port does the app run on? (default: 5000 for Python, 3000 for JS)
   - What test framework? (default: detected)
   - Enable E2E testing with Playwright? (default: no)
   - Enable subagent delegation? (default: no)

3. **Run the init command** with my answers:
   ```bash
   claude-harness init --non-interactive \\
     --name "<project_name>" \\
     --language "<language>" \\
     --framework "<framework>" \\
     --port <port> \\
     --test-framework "<test_framework>" \\
     [--e2e if enabled] \\
     [--delegation if enabled]
   ```

4. **Show me the results** - what files were created and next steps.

If ALREADY initialized, tell me and show the current status with `claude-harness status`."""
    },

    # ========== STATUS ==========
    "harness-status": {
        "description": "Show current harness status (context, features, progress)",
        "content": """Show the current claude-harness status.

Run this command and display the output:
```bash
claude-harness status
```

Summarize the key information: context usage, current feature, and any blockers."""
    },

    # ========== FEATURE MANAGEMENT ==========
    "harness-feature-list": {
        "description": "List all features",
        "content": """List all features in the harness.

Run:
```bash
claude-harness feature list --all
```

Display the results in a clear format."""
    },

    "harness-feature-add": {
        "description": "Add a new feature with subtasks",
        "content": """Add a new feature to the harness.

If arguments are provided, use them. Otherwise, ask me:
1. What is the feature name?
2. What priority (1=highest, 5=lowest)? Default: 3
3. What are the subtasks? (comma-separated or one per line)
4. Any initial notes?

Then run:
```bash
claude-harness feature add "<feature_name>" -p <priority> \\
  -s "<subtask1>" \\
  -s "<subtask2>" \\
  [-n "<notes>"]
```

Show the created feature ID and confirm success.

Arguments provided: $ARGUMENTS"""
    },

    "harness-feature-start": {
        "description": "Start working on a feature",
        "content": """Start a feature.

If a feature ID is provided in arguments, use it. Otherwise:
1. Run `claude-harness feature list` to show available features
2. Ask me which feature to start

Then run:
```bash
claude-harness feature start <feature_id>
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-complete": {
        "description": "Mark a feature as complete",
        "content": """Complete a feature.

If a feature ID is provided, use it. Otherwise, show current in-progress feature.

Before completing, verify:
1. All subtasks are done
2. Tests are passing

Run:
```bash
claude-harness feature complete <feature_id>
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-block": {
        "description": "Block a feature with a reason",
        "content": """Block a feature.

Ask me:
1. Which feature ID to block? (or use argument)
2. What is the blocking reason?

Run:
```bash
claude-harness feature block <feature_id> -r "<reason>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-unblock": {
        "description": "Unblock a blocked feature",
        "content": """Unblock a feature.

If a feature ID is provided, use it. Otherwise, list blocked features.

Run:
```bash
claude-harness feature unblock <feature_id>
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-done": {
        "description": "Mark a subtask as done",
        "content": """Mark a subtask as done.

If arguments provided, use them. Otherwise:
1. Show current feature with `claude-harness feature info <current_feature>`
2. Ask which subtask to mark done (by number or name)

Run:
```bash
claude-harness feature done <feature_id> "<subtask_name_or_index>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-info": {
        "description": "Show detailed feature information",
        "content": """Show detailed information about a feature.

If a feature ID is provided, use it. Otherwise, show the current in-progress feature.

Run:
```bash
claude-harness feature info <feature_id>
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-note": {
        "description": "Add a note to a feature",
        "content": """Add a note to a feature.

If arguments provided, parse feature ID and note. Otherwise, ask:
1. Which feature ID?
2. What note to add?

Run:
```bash
claude-harness feature note <feature_id> "<note_text>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-feature-tests": {
        "description": "Mark feature tests as passing/failing",
        "content": """Update test status for a feature.

Ask me:
1. Which feature ID? (or use argument)
2. Are tests passing? (yes/no)

Run:
```bash
claude-harness feature tests <feature_id> --passing
# or
claude-harness feature tests <feature_id> --failing
```

Arguments: $ARGUMENTS"""
    },

    # ========== PROGRESS TRACKING ==========
    "harness-progress": {
        "description": "Show current session progress",
        "content": """Show current session progress.

Run:
```bash
claude-harness progress show
```

Display the output clearly."""
    },

    "harness-progress-completed": {
        "description": "Add a completed item to progress",
        "content": """Add a completed item to progress tracking.

If text provided in arguments, use it. Otherwise ask what was completed.

Run:
```bash
claude-harness progress completed "<item_description>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-progress-wip": {
        "description": "Add a work-in-progress item",
        "content": """Add a work-in-progress item to progress tracking.

If text provided in arguments, use it. Otherwise ask what's in progress.

Run:
```bash
claude-harness progress wip "<item_description>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-progress-blocker": {
        "description": "Add a blocker to progress",
        "content": """Add a blocker to progress tracking.

If text provided in arguments, use it. Otherwise ask what the blocker is.

Run:
```bash
claude-harness progress blocker "<blocker_description>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-progress-file": {
        "description": "Track a modified file",
        "content": """Track a modified file in progress.

If filename provided in arguments, use it. Otherwise ask which file.

Run:
```bash
claude-harness progress file "<filename>"
```

Arguments: $ARGUMENTS"""
    },

    "harness-progress-new-session": {
        "description": "Start a new session (archives current)",
        "content": """Start a new session, archiving the current one.

Confirm with me before proceeding, then run:
```bash
claude-harness progress new-session
```

Show the archive location."""
    },

    "harness-progress-history": {
        "description": "View session history",
        "content": """View session history.

Run:
```bash
claude-harness progress history --limit 10
```

Arguments (optional limit): $ARGUMENTS"""
    },

    # ========== CONTEXT TRACKING ==========
    "harness-context": {
        "description": "Show context/token usage",
        "content": """Show current context/token usage.

Run:
```bash
claude-harness context show --full
```

Explain the status (OK, WARNING, CRITICAL) and remaining budget."""
    },

    "harness-context-summary": {
        "description": "Generate a context summary",
        "content": """Generate a summary of the current session context.

Run:
```bash
claude-harness context summary
```

Display the generated summary."""
    },

    "harness-context-handoff": {
        "description": "Generate a handoff document for session continuity",
        "content": """Generate a handoff document for continuing this session later.

Run:
```bash
claude-harness context handoff
```

Show where the handoff document was saved and its key contents."""
    },

    "harness-context-compress": {
        "description": "Compress session (handoff + archive + reset)",
        "content": """Compress the current session to save context.

This will:
1. Generate a handoff document
2. Archive the current session
3. Reset context tracking

Confirm with me, then run:
```bash
claude-harness context compress
```"""
    },

    # ========== DELEGATION ==========
    "harness-delegation-status": {
        "description": "Show delegation status and metrics",
        "content": """Show subagent delegation status.

Run:
```bash
claude-harness delegation status
```

Explain what delegation is and current settings."""
    },

    "harness-delegation-enable": {
        "description": "Enable subagent delegation",
        "content": """Enable subagent delegation.

Run:
```bash
claude-harness delegation enable
```

Explain what this means for the workflow."""
    },

    "harness-delegation-disable": {
        "description": "Disable subagent delegation",
        "content": """Disable subagent delegation.

Run:
```bash
claude-harness delegation disable
```"""
    },

    "harness-delegation-rules": {
        "description": "Show delegation rules",
        "content": """Show all delegation rules.

Run:
```bash
claude-harness delegation rules
```

Explain what each rule does and when it triggers."""
    },

    "harness-delegation-suggest": {
        "description": "Get delegation suggestions for a feature",
        "content": """Get delegation suggestions for a feature's subtasks.

If feature ID provided, use it. Otherwise, use current in-progress feature.

Run:
```bash
claude-harness delegation suggest <feature_id>
```

Explain which subtasks could be delegated and estimated token savings.

Arguments: $ARGUMENTS"""
    },

    "harness-delegation-auto": {
        "description": "Toggle auto-delegation hints",
        "content": """Toggle auto-delegation hints in CLAUDE.md.

Ask: Enable or disable auto-delegation hints?

Run:
```bash
claude-harness delegation auto --on
# or
claude-harness delegation auto --off
```"""
    },

    "harness-delegation-add-rule": {
        "description": "Add a custom delegation rule",
        "content": """Add a custom delegation rule.

Ask me:
1. Rule name?
2. Task patterns (comma-separated regex patterns)?
3. Subagent type (explore, test, document, review, general)?
4. Priority (1-10, higher = more important)?

Run:
```bash
claude-harness delegation add-rule \\
  -n "<name>" \\
  -p "<pattern1>,<pattern2>" \\
  -t <type> \\
  --priority <priority>
```"""
    },

    # ========== E2E TESTING ==========
    "harness-e2e-generate": {
        "description": "Generate E2E test for a feature",
        "content": """Generate an E2E test scaffold for a feature.

If feature ID provided, use it. Otherwise, ask which feature.

Run:
```bash
claude-harness e2e generate <feature_id>
```

Show the generated test file location.

Arguments: $ARGUMENTS"""
    },

    # ========== UTILITIES ==========
    "harness-detect": {
        "description": "Detect project stack without initializing",
        "content": """Detect the current project's technology stack.

Run:
```bash
claude-harness detect
```

Show what was detected: language, framework, test framework, databases, etc."""
    },

    "harness-run": {
        "description": "Run the project's init script",
        "content": """Run the project initialization/startup script.

Run:
```bash
claude-harness run
```

This executes `scripts/init.sh` (or `init.ps1` on Windows) which typically:
- Checks environment
- Shows git status
- Starts the application
- Runs tests"""
    },

    "harness-help": {
        "description": "Show all available harness commands",
        "content": """Show all available claude-harness commands.

Run:
```bash
claude-harness --help
```

Also list all `/harness-*` slash commands available in this project."""
    },

    # ========== ORCHESTRATION ==========
    "harness-orchestrate": {
        "description": "Evaluate and suggest automatic task delegation",
        "content": """Evaluate if tasks should be delegated to subagents for context optimization.

Run:
```bash
claude-harness orchestrate evaluate
```

If delegation is recommended, generate the queue:
```bash
claude-harness orchestrate queue
```

Show me which subtasks can be delegated and the estimated token savings."""
    },

    "harness-orchestrate-status": {
        "description": "Show orchestration status and metrics",
        "content": """Show the current orchestration status.

Run:
```bash
claude-harness orchestrate status
```

Display: state, active delegations, completed count, tokens saved."""
    },

    "harness-orchestrate-queue": {
        "description": "Generate delegation queue for current feature",
        "content": """Generate a delegation queue for the current feature.

Run:
```bash
claude-harness orchestrate queue
```

Arguments (optional feature ID): $ARGUMENTS"""
    },

    # ========== OPTIMIZATION ==========
    "harness-optimize": {
        "description": "Show context optimization status",
        "content": """Show context optimization status and potential savings.

Run:
```bash
claude-harness optimize status
```

Display: filter stats, cache stats, compression potential, total savings estimate."""
    },

    "harness-optimize-filter": {
        "description": "Show which files would be tracked/skipped",
        "content": """Filter files to see which would be tracked vs skipped.

Run on current directory:
```bash
claude-harness optimize filter -d .
```

Or on specific files: $ARGUMENTS"""
    },

    "harness-optimize-prune": {
        "description": "Prune stale context references",
        "content": """Remove stale file references from context tracking.

Run:
```bash
claude-harness optimize prune
```

This frees up token budget by removing old file references."""
    },

    "harness-optimize-cache": {
        "description": "Show exploration cache status",
        "content": """List cached exploration results.

Run:
```bash
claude-harness optimize cache
```

Show what's cached and potential token savings from reuse."""
    },

    "harness-optimize-cache-clear": {
        "description": "Clear exploration cache",
        "content": """Clear the exploration cache.

To clear only expired entries:
```bash
claude-harness optimize cache-clear --expired-only
```

To clear everything:
```bash
claude-harness optimize cache-clear -y
```"""
    },

    "harness-optimize-summary": {
        "description": "Show compact context summary",
        "content": """Show a compact one-line context summary.

Run:
```bash
claude-harness optimize summary
```

Great for quick status checks."""
    },
}


def generate_command_file(name: str, description: str, content: str) -> str:
    """Generate the content of a slash command markdown file."""
    return f"""{content}
"""


def write_commands_to_directory(commands_dir: Path, commands: Optional[Dict] = None) -> list:
    """
    Write all harness commands to the .claude/commands directory.

    Args:
        commands_dir: Path to .claude/commands directory
        commands: Optional dict of commands (defaults to HARNESS_COMMANDS)

    Returns:
        List of created command file paths
    """
    if commands is None:
        commands = HARNESS_COMMANDS

    commands_dir.mkdir(parents=True, exist_ok=True)
    created_files = []

    for name, cmd_data in commands.items():
        file_path = commands_dir / f"{name}.md"
        content = generate_command_file(
            name=name,
            description=cmd_data["description"],
            content=cmd_data["content"]
        )
        file_path.write_text(content)
        created_files.append(str(file_path))

    return created_files


def get_command_list() -> list:
    """Get list of all command names and descriptions."""
    return [
        {"name": f"/{name}", "description": data["description"]}
        for name, data in HARNESS_COMMANDS.items()
    ]


def generate_commands_readme(commands_dir: Path) -> str:
    """Generate a README for the commands directory."""
    readme_content = """# Claude Harness Commands

These slash commands integrate claude-harness with Claude Code.

## Available Commands

| Command | Description |
|---------|-------------|
"""
    for name, data in sorted(HARNESS_COMMANDS.items()):
        readme_content += f"| `/{name}` | {data['description']} |\n"

    readme_content += """
## Usage

Type any command in Claude Code, e.g.:
- `/harness-status` - Show current status
- `/harness-feature-add` - Add a new feature
- `/harness-delegation-suggest` - Get delegation suggestions

Commands that accept arguments can be used like:
- `/harness-feature-start F-001`
- `/harness-feature-note F-001 "This is a note"`

## First Time Setup

If claude-harness is not initialized yet, run:
- `/harness-init` - Interactive initialization within Claude Code

Or run directly in terminal:
```bash
claude-harness init
```
"""

    readme_path = commands_dir / "README.md"
    readme_path.write_text(readme_content)
    return str(readme_path)
