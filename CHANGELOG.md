# Changelog

All notable changes to Claude Harness will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-12

### Added

#### Core Features
- **Project Initialization** (`claude-harness init`)
  - Interactive setup wizard with stack detection
  - Non-interactive mode (`--non-interactive` / `-y`) for CI/CD and automation
  - Auto-detection of language, framework, database, test framework
  - Generation of harness configuration files

- **Feature Management** (`claude-harness feature`)
  - Add features with subtasks and priorities
  - Start/complete/block/unblock features
  - Mark subtasks as done
  - Track tests passing and E2E validation status
  - One-feature-at-a-time workflow enforcement

- **Progress Tracking** (`claude-harness progress`)
  - Session continuity via `progress.md`
  - Track completed tasks, WIP, blockers
  - Track modified files
  - Session archival to `session-history/`
  - New session command with automatic archival

- **Context Tracking** (`claude-harness context`)
  - Token usage estimation (~4 chars per token)
  - Configurable budget with warning/critical thresholds
  - Per-task context tracking
  - Session summary generation
  - Handoff document generation for session continuation
  - Session compression (handoff + archive + reset)

- **E2E Testing** (`claude-harness e2e`)
  - Playwright integration
  - Browser installation command
  - Test generation from features
  - Headed and slow-motion test modes

- **Stack Detection** (`claude-harness detect`)
  - Python (Flask, Django, FastAPI)
  - JavaScript/TypeScript (Express, Next.js, React, Vue, NestJS)
  - Go, Rust (basic)
  - Database detection (PostgreSQL, MySQL, SQLite, MongoDB, Redis)
  - Git, Docker, Kubernetes detection
  - CI/CD provider detection

- **Startup Scripts**
  - `scripts/init.sh` (Bash) for Linux/macOS
  - `scripts/init.ps1` (PowerShell) for Windows
  - Environment checks, git status, app startup, test status

- **Claude Code Integration**
  - Auto-generation of `.claude/settings.json` with hooks
  - Git safety hooks (block protected branch commits)
  - Auto-progress tracking hooks (track file modifications)
  - Activity logging hooks
  - Stop hook for status summary

- **MCP Server**
  - Playwright browser automation server
  - 14 browser control tools (navigate, click, fill, screenshot, etc.)
  - Compatible with Claude Desktop and Claude Code

### Documentation
- Comprehensive README with usage examples
- HOOKS.md for Claude Code hook configuration
- Integration test report

### Testing
- 157 unit tests covering all modules
- Integration test suite with subagent testing
- 100% pass rate on all test scenarios

---

## [1.1.0] - 2025-12-12

### Added

#### Feature Management Enhancements
- **Feature Info Command** (`claude-harness feature info <ID>`)
  - Display detailed feature information
  - Show all subtasks with completion status
  - Show creation date, time in current status
  - Display notes and blocked reason history

- **Subtask Name-Based Completion** (`claude-harness feature done <ID> <name>`)
  - Complete subtasks by partial name match (fuzzy matching)
  - Case-insensitive matching
  - Shows matched subtask for confirmation

- **Feature Notes Command** (`claude-harness feature note <ID> "text"`)
  - Add timestamped notes to features
  - Notes visible in feature info display
  - Works on features in any status (pending, in_progress, blocked, completed)

- **Enhanced Feature Filtering**
  - `--priority` / `-p` flag to filter by priority level
  - `--search` / `-q` flag for case-insensitive name search
  - Combinable with existing `--status` filter

- **Bulk Operations**
  - `feature start` accepts multiple feature IDs
  - `feature block` accepts multiple feature IDs
  - Warning prompt for multiple features (bypass with `--yes` / `-y`)
  - Partial success handling with clear feedback

#### Progress Tracking Enhancements
- **Progress History Command** (`claude-harness progress history`)
  - List archived sessions with summaries
  - `--limit N` to show last N sessions (default: 10)
  - `--show <index>` to view specific session details

### Testing
- 178 unit tests (up from 157)
- New tests for all v1.1.0 features
- 100% pass rate

---

## [1.3.0] - 2025-12-12

### Added

#### Subagent Delegation System
- **DelegationManager** - Core delegation management with rule-based task matching
  - Pattern-based rule matching (regex support)
  - Priority-based rule selection
  - Token savings estimation per delegation
  - Delegation tracking and metrics

- **Delegation CLI Commands** (`claude-harness delegation`)
  - `delegation status` - Show delegation status and metrics
  - `delegation enable/disable` - Toggle delegation globally
  - `delegation rules` - List all delegation rules with details
  - `delegation add-rule` - Add custom delegation rules with patterns, type, priority, constraints
  - `delegation remove-rule` - Remove rules by name
  - `delegation enable-rule/disable-rule` - Toggle specific rules
  - `delegation suggest <ID>` - Get delegation suggestions for feature subtasks
  - `delegation auto --on/--off` - Configure auto-delegation hints in CLAUDE.md

- **CLAUDE.md Delegation Integration**
  - Generate delegation section when delegation is enabled
  - Include subagent type recommendations per subtask
  - Token savings estimates per task type
  - Constraint propagation to subagents

#### Default Delegation Rules
| Rule | Patterns | Subagent Type | Est. Savings |
|------|----------|---------------|--------------|
| exploration | explore.*, find.*, search.*, investigate.* | explore | 22K tokens |
| testing | test.*, write.*test, unit.*test | test | 15K tokens |
| documentation | document.*, write.*doc, update.*readme | document | 9K tokens |
| review | review.*, audit.*, check.*, validate.* | review | 17K tokens |

### Benefits
- **40-70% context savings** by delegating to specialized subagents
- **Parallel execution** of independent tasks
- **Summary-based returns** (3-5K tokens vs 25K+ full execution)
- **Pattern-based matching** for automatic delegation suggestions

### Documentation
- Comprehensive research report: `docs/SUBAGENT_DELEGATION_RESEARCH.md`
- Updated ROADMAP with delegation roadmap (v1.3.0-v1.5.0)

### Testing
- 35+ new tests for delegation module
- Tests for DelegationRule, DelegationConfig, DelegationResult, DelegationManager

---

## [Unreleased]

### Planned
- See [ROADMAP.md](ROADMAP.md) for upcoming features

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 1.3.0 | 2025-12-12 | Subagent delegation system with rule-based task matching |
| 1.1.0 | 2025-12-12 | Feature info, notes, bulk operations, enhanced filtering |
| 1.0.0 | 2025-12-12 | Initial release with full feature set |
