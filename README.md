# Claude Harness

**AI Workflow Optimization Tool for Claude Code**

A comprehensive harness that optimizes Claude Code sessions by addressing the four most common failures:

1. **Early "done"** - Agent declares victory too soon → Feature list as source of truth
2. **Messy repo** - Half-finished, no history → Git + progress log ritual
3. **No real testing** - Marks features done without verification → E2E browser tests
4. **Chaotic setup** - Re-learns how to run app every time → Single `init.sh` startup script

## Features

- **Session Continuity**: `progress.md` maintains context between sessions
- **Feature Management**: Track features/tasks with status, subtasks, and E2E validation
- **Context Tracking**: Monitor estimated token usage with session-based lifecycle
- **Compaction Indicator**: Shows estimated compaction count when usage exceeds 100%
- **Auto-Save Handoff**: Automatically saves handoff document on session exit
- **Discoveries Tracking**: Capture findings, requirements, and institutional knowledge
- **Startup Ritual**: `init.sh` (Bash) and `init.ps1` (PowerShell) scripts
- **Git Safety Hooks**: Block dangerous operations (commits to main, force pushes)
- **Auto-Hooks Setup**: Creates `.claude/settings.local.json` with hooks during init
- **E2E Testing**: Playwright integration with test generation
- **MCP Server**: Playwright browser automation via Model Context Protocol
- **Stack Detection**: Automatically detects your project's language, framework, database

## Installation

```bash
# Clone the repository
git clone https://github.com/xanthar/claude-harness.git

# Install in development mode
cd claude-harness
pip install -e .

# Or install directly
pip install git+https://github.com/xanthar/claude-harness.git
```

## Quick Start

### Initialize a project

```bash
cd your-project
claude-harness init
```

The initializer will:
1. Detect your project stack (language, framework, database)
2. Ask configuration questions
3. Generate harness files in `.claude-harness/`
4. Create `scripts/init.sh` and `scripts/init.ps1` startup scripts
5. Set up E2E testing structure
6. Update/create `.claude/CLAUDE.md`
7. Create `.claude/settings.local.json` with hooks (project-specific)

### Start a session

```bash
./scripts/init.sh
```

This will:
- Check git status (warn if on protected branch)
- Activate virtual environment (Python)
- Check if app is running, optionally start it
- Verify database connection
- Run quick test check
- Show session progress and current feature

### Refresh after upgrading

After upgrading claude-harness, refresh your project's scripts:

```bash
claude-harness refresh
```

This regenerates init.sh, hooks, and init.ps1 with the latest improvements while preserving your data (features.json, progress.md, config.json).

### Manage features

```bash
# List features
claude-harness feature list

# Add a feature with subtasks
claude-harness feature add "User authentication" -s "Login form" -s "JWT handling" -s "Logout"

# Start working on a feature
claude-harness feature start F-001

# Mark subtask as done
claude-harness feature done F-001 0

# Mark tests as passing
claude-harness feature tests F-001

# Complete the feature
claude-harness feature complete F-001
```

### Track progress

```bash
# Show current progress
claude-harness progress show

# Add completed item
claude-harness progress completed "Implemented login form"

# Add work in progress
claude-harness progress wip "Working on JWT handling"

# Add blocker
claude-harness progress blocker "Need API keys for OAuth"

# Start new session (archives previous)
claude-harness progress new-session
```

### E2E Testing

```bash
# Install Playwright
claude-harness e2e install

# Generate test for a feature
claude-harness e2e generate F-001

# Run E2E tests
claude-harness e2e run
claude-harness e2e run --headed  # Visible browser
```

### MCP Server (Playwright)

Claude Harness includes an MCP server for browser automation, allowing Claude Code to interact with web applications directly.

**Setup for Claude Desktop:**

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "python",
      "args": ["-m", "claude_harness.mcp.playwright_server"]
    }
  }
}
```

**Available Tools:**

| Tool | Description |
|------|-------------|
| `browser_launch` | Launch browser (chromium/firefox/webkit) |
| `browser_navigate` | Navigate to URL |
| `browser_click` | Click elements |
| `browser_fill` | Fill form inputs |
| `browser_type` | Type with keystroke simulation |
| `browser_screenshot` | Take screenshots |
| `browser_get_text` | Get element text |
| `browser_wait` | Wait for elements |
| `browser_evaluate` | Run JavaScript |
| `browser_select` | Select dropdown options |
| `browser_check` | Check checkboxes |
| `browser_press` | Press keyboard keys |
| `browser_close` | Close browser |
| `browser_content` | Get page HTML |
| `browser_query_all` | Query multiple elements |

**Run standalone:**

```bash
python -m claude_harness.mcp.playwright_server
```

### Context Tracking

Monitor estimated token usage with session-based lifecycle:

```bash
# Show context usage
claude-harness context show
claude-harness context show --full  # Detailed view with compaction info

# Show session info
claude-harness context session-info

# Mark session as closed (triggers reset on next start)
claude-harness context session-close

# Reset for new session
claude-harness context reset

# Set context budget
claude-harness context budget 200000

# Track per-task usage
claude-harness context start-task F-001
# ... do work ...
claude-harness context end-task F-001

# Output metadata for embedding
claude-harness context metadata
```

**Session-Based Features:**
- Each session gets a unique `session_id`
- Metrics automatically reset when a closed session is detected
- Shows compaction indicator when usage exceeds 100% (e.g., `250% (~2 compactions)`)

The status command shows compact context usage:

```
[ * ] Context: 15.2% used | ~169,600 tokens remaining | 12 files read | 5 commands
[!!!] Context: 250% (~2 compactions) | 12 files read | 5 commands
```

### Session Compression & Handoff

When context is filling up, compress your session for seamless continuation:

```bash
# Generate a session summary
claude-harness context summary

# Create a handoff document for the next session
claude-harness context handoff
claude-harness context handoff --save  # Save to file

# Full compression: handoff + archive progress + reset metrics
claude-harness context compress
```

The handoff document includes:
- Project context and stack info
- Current feature progress and subtasks
- Completed work this session
- Files modified
- Pending features
- Recommended next steps

**Workflow for long sessions:**
1. Work until context hits warning level (~70%)
2. Run `claude-harness context compress`
3. Start a new Claude Code session
4. Read the saved handoff document for context
5. Continue seamlessly

### Hooks Setup

Claude Code hooks enable automatic tracking and safety enforcement. During `claude-harness init`, hooks are automatically configured in `.claude/settings.local.json` (project-specific, not committed).

**Auto-created hooks include:**
- **PreToolUse**: Git safety checks (block commits to protected branches)
- **PostToolUse**:
  - Context tracking (file reads)
  - Auto-progress tracking (file writes/edits added to progress.md)
  - Activity logging
- **SessionEnd**: Auto-save handoff, mark session closed, show summary

> **Note**: The `SessionEnd` hook fires on all session endings including `/exit`. The older `Stop` hook only fires when Claude naturally stops, so we use `SessionEnd` to ensure handoffs are always saved.

See [docs/HOOKS.md](docs/HOOKS.md) for detailed manual setup and customization.

**Manual setup** - add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": ".claude-harness/hooks/check-git-safety.sh"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": ".claude-harness/hooks/track-read.sh"}]
      },
      {
        "matcher": "Write",
        "hooks": [{"type": "command", "command": ".claude-harness/hooks/track-write.sh"}]
      },
      {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": ".claude-harness/hooks/track-edit.sh"}]
      },
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": ".claude-harness/hooks/log-activity.sh"}]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [{"type": "command", "command": ".claude-harness/hooks/session-stop.sh"}]
      }
    ]
  }
}
```

### Discoveries Tracking

Capture findings, requirements, and institutional knowledge during sessions:

```bash
# Add a discovery
claude-harness discovery add "Auth requires JWT secret in env" --context "Found during testing" --tags security,config

# List all discoveries
claude-harness discovery list
claude-harness discovery list --tag security  # Filter by tag
claude-harness discovery list --feature F-001  # Filter by feature

# Search discoveries
claude-harness discovery search "JWT"

# Show discovery details
claude-harness discovery show D-001

# View statistics
claude-harness discovery stats

# Generate summary for handoff
claude-harness discovery summary

# List all tags
claude-harness discovery tags
```

Discoveries are persisted in `.claude-harness/discoveries.json` and included in handoff documents.

## Project Structure After Init

```
your-project/
├── .claude/
│   ├── CLAUDE.md              # Enhanced with harness integration
│   └── settings.local.json    # Claude Code hooks (project-specific)
├── .claude-harness/
│   ├── config.json            # Project configuration
│   ├── features.json          # Feature/task tracking
│   ├── progress.md            # Session continuity log
│   ├── context_metrics.json   # Context usage tracking
│   ├── discoveries.json       # Captured findings and knowledge
│   ├── hooks/
│   │   ├── check-git-safety.sh
│   │   ├── track-read.sh
│   │   ├── track-write.sh
│   │   ├── track-edit.sh
│   │   ├── log-activity.sh
│   │   └── session-stop.sh
│   └── session-history/       # Archived sessions
├── scripts/
│   ├── init.sh                # Startup ritual (Bash)
│   └── init.ps1               # Startup ritual (PowerShell)
└── e2e/
    ├── conftest.py            # Playwright fixtures
    ├── pytest.ini
    └── tests/                 # E2E test files
```

## Configuration

The `.claude-harness/config.json` file contains all project settings:

```json
{
  "project_name": "my-project",
  "stack": {
    "language": "python",
    "framework": "flask",
    "database": "postgresql"
  },
  "startup": {
    "port": 8000,
    "health_endpoint": "/api/v1/health",
    "start_command": "python run.py"
  },
  "git": {
    "protected_branches": ["main", "master"],
    "require_merge_confirmation": true
  },
  "testing": {
    "framework": "pytest",
    "coverage_threshold": 80
  }
}
```

## Feature Tracking Format

The `.claude-harness/features.json` file tracks all features:

```json
{
  "current_phase": "Phase 1 - Core Features",
  "features": [
    {
      "id": "F-001",
      "name": "User authentication",
      "status": "in_progress",
      "priority": 1,
      "tests_passing": false,
      "e2e_validated": false,
      "subtasks": [
        {"name": "Login form", "done": true},
        {"name": "JWT handling", "done": false}
      ]
    }
  ],
  "completed": [],
  "blocked": []
}
```

## Progress Tracking

The `.claude-harness/progress.md` file maintains session continuity:

```markdown
# Session Progress Log

## Last Session: 2025-12-12 17:30 UTC

### Completed This Session
- [x] Implemented login form
- [x] Added form validation

### Current Work In Progress
- [ ] F-001: User authentication - JWT handling

### Blockers
- None

### Next Session Should
1. Run `./scripts/init.sh` to verify environment
2. Continue with JWT handling subtask
3. Write unit tests for auth module

### Files Modified This Session
- app/auth/login.py
- app/templates/login.html
```

## CLAUDE.md Integration

The harness adds mandatory rituals to your CLAUDE.md:

### Session Start Ritual
1. Run `./scripts/init.sh`
2. Read `.claude-harness/progress.md`
3. Check `.claude-harness/features.json`
4. Pick ONE feature to work on
5. Update status to "in_progress"

### Session End Ritual
1. Update progress.md with session summary
2. Update feature status/subtasks
3. Commit work if appropriate

## CLI Reference

| Command | Description |
|---------|-------------|
| `claude-harness init` | Initialize harness in project |
| `claude-harness refresh` | Refresh scripts without losing data |
| `claude-harness status` | Show current status |
| `claude-harness detect` | Preview stack detection |
| `claude-harness run` | Execute init.sh |
| `claude-harness feature list` | List features |
| `claude-harness feature add NAME` | Add new feature |
| `claude-harness feature start ID` | Start working on feature |
| `claude-harness feature complete ID` | Complete feature |
| `claude-harness feature subtask ID NAME` | Add subtask |
| `claude-harness feature done ID INDEX` | Complete subtask |
| `claude-harness progress show` | Show progress |
| `claude-harness progress completed ITEM` | Add completed item |
| `claude-harness progress wip ITEM` | Add WIP item |
| `claude-harness progress file PATH` | Track modified file |
| `claude-harness progress new-session` | Start new session |
| `claude-harness context show` | Show context usage |
| `claude-harness context reset` | Reset context metrics |
| `claude-harness context budget N` | Set token budget |
| `claude-harness context start-task ID` | Start tracking task |
| `claude-harness context end-task ID` | End tracking task |
| `claude-harness context summary` | Generate session summary |
| `claude-harness context handoff` | Generate handoff document |
| `claude-harness context compress` | Compress session (handoff + archive + reset) |
| `claude-harness context session-info` | Show current session details |
| `claude-harness context session-close` | Mark session as closed |
| `claude-harness discovery add SUMMARY` | Add a discovery |
| `claude-harness discovery list` | List all discoveries |
| `claude-harness discovery show ID` | Show discovery details |
| `claude-harness discovery search QUERY` | Search discoveries |
| `claude-harness discovery delete ID` | Delete a discovery |
| `claude-harness discovery tags` | List all unique tags |
| `claude-harness discovery stats` | Show discovery statistics |
| `claude-harness discovery summary` | Generate discovery summary |
| `claude-harness e2e install` | Install Playwright |
| `claude-harness e2e run` | Run E2E tests |
| `claude-harness e2e generate ID` | Generate E2E test |

## Short Alias

The `ch` alias is also available:

```bash
ch init
ch status
ch feature list
```

## Supported Stacks

### Languages
- Python (pip, poetry, pipenv)
- JavaScript/TypeScript (npm, yarn, pnpm)
- Go, Rust (basic detection)

### Frameworks
- Python: Flask, Django, FastAPI
- JS/TS: Express, Next.js, React, Vue, NestJS

### Databases
- PostgreSQL, MySQL, SQLite, MongoDB, Redis

### Testing
- pytest, unittest, Jest, Vitest, Mocha, Playwright

## Philosophy

The harness enforces these principles:

1. **ONE feature at a time** - Focus prevents half-finished work
2. **Progress over perfection** - Track what's done, what's blocked
3. **Tests or it didn't happen** - Features need tests and E2E validation
4. **Clean repo always** - Every session ends with a commit
5. **Context is king** - Progress.md ensures no context is lost

## Comparison with Sequential Thinking MCP

Claude Harness and the [Sequential Thinking MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking) serve different purposes and can be used together:

| Aspect | **Claude Harness** | **Sequential Thinking MCP** |
|--------|-------------------|----------------------------|
| **Purpose** | Project workflow management | Structured reasoning process |
| **Focus** | Session continuity & task tracking | Step-by-step thinking during tasks |
| **Persistence** | Saves to disk (features.json, progress.md) | In-memory only (session-scoped) |
| **Scope** | Across multiple sessions | Within a single reasoning task |
| **What it tracks** | Features, progress, context usage, git | Individual thought steps & revisions |

### Using Them Together

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Session                        │
│                                                          │
│  ┌──────────────────┐     ┌──────────────────────────┐  │
│  │ Sequential       │     │ Claude Harness            │  │
│  │ Thinking MCP     │     │                          │  │
│  │                  │     │ • What feature am I on?  │  │
│  │ • How do I solve │     │ • What's done/remaining? │  │
│  │   this problem?  │     │ • How much context used? │  │
│  │ • Step 1...      │     │ • Session handoff        │  │
│  │ • Revise step 2  │     │                          │  │
│  │ • Branch idea... │     │                          │  │
│  └──────────────────┘     └──────────────────────────┘  │
│       ↑                            ↑                     │
│  MICRO: reasoning             MACRO: workflow            │
│  within a task                across sessions            │
└─────────────────────────────────────────────────────────┘
```

- **Harness** tells Claude "Work on F003: Add authentication"
- **Sequential Thinking** helps Claude reason through HOW to implement it
- **Harness** tracks that F003 is complete and what files changed

## Documentation

- [CHANGELOG.md](CHANGELOG.md) - Version history and release notes
- [ROADMAP.md](ROADMAP.md) - Planned features and improvements
- [docs/HOOKS.md](docs/HOOKS.md) - Detailed hook configuration guide

## Contributing

1. Fork the repository
2. Create a feature branch (`feat/your-feature`)
3. Make your changes
4. Write tests (aim for 100% coverage on new code)
5. Update CHANGELOG.md
6. Submit a pull request

See [ROADMAP.md](ROADMAP.md) for planned features accepting contributions.

## License

MIT License - see LICENSE file

## Author

Created by Morten Elmstroem Hansen

---

*Optimizing Claude Code workflows, one harness at a time.*
