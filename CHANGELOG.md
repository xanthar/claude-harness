# Changelog

All notable changes to Claude Harness will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-15

### Added

#### Compact CLAUDE.md Template (AI-Optimized)
- **Modular section generation** for CLAUDE.md harness integration
  - `_build_harness_section()` method builds compact, modular content
  - Helper methods for each section: `_build_core_behaviors()`, `_build_command_reference()`, etc.
  - ~70% token reduction from ~1800 to ~350-550 tokens
  - Optimized for AI comprehension over human readability

- **Conditional sections** based on enabled features
  - Delegation section only appears when `delegation_enabled: true`
  - Orchestration section only appears when `orchestration_enabled: true`
  - Discoveries section only appears when `discoveries_enabled: true`
  - Documentation section only appears when `documentation_enabled: true` (default: enabled)
  - E2E section only appears when `e2e_enabled: true`
  - Context tracking section always included (core feature)

#### Documentation Update Reminders (MANDATORY)
- `docs enable` - Enable documentation reminders (default)
- `docs disable` - Disable documentation reminders
- `docs status` - Show current settings
- `docs trigger <when>` - Set trigger: `feature_complete` (default) or `session_end`
- Documentation now **required BEFORE** `feature complete` (not after)
- One update per feature rule - prevents redundant updates after compaction

#### Context Critical Protocol (Pre-Compaction)
- New "Context Critical" section in CLAUDE.md for when Claude shows < 10% remaining
- Instructs agent to: STOP → mark subtasks → update docs → handoff → commit
- FIRST TIME only per feature (skip re-documenting after compaction)
- References Claude's actual context indicator (authoritative) vs harness estimation (supplementary)
- Thresholds: >30% continue, 10-30% wrap up, <10% STOP

#### Auto-Update CLAUDE.md on Enable/Disable
- All enable/disable commands now auto-update CLAUDE.md immediately
- No more manual `refresh --update-claude-md` required
- Applies to: delegation, orchestration, discovery, docs commands

#### Orchestration Enable/Disable Commands
- `orchestrate enable` - Enable automatic orchestration
- `orchestrate disable` - Disable automatic orchestration
- `orchestrate status` now shows enabled/disabled state at top

#### Discoveries Enable/Disable Commands
- `discovery enable` - Enable discoveries tracking
- `discovery disable` - Disable discoveries tracking
- `discovery status` - Show enabled/disabled state

#### Session End Subtask Audit Hook
- New `check-subtasks.sh` hook runs at session end
- Audits in-progress features for incomplete subtasks
- Reminds agent to mark subtasks complete before session ends
- Shows suggested `feature done` commands for unmarked subtasks
- Runs before `session-stop.sh` for proper sequencing

#### Enhanced Mandatory Behaviors Rules
- Added rule: "Mark subtasks done AS YOU COMPLETE THEM" - prevents batching at session end
- Added rule: "Use HARNESS commands, NOT Claude's internal TodoWrite" - ensures proper tracking

#### New Config Fields
- `orchestration_enabled` in HarnessConfig (default: false)
- `discoveries_enabled` in HarnessConfig (default: false)
- `documentation_enabled` in HarnessConfig (default: true)
- `documentation_trigger` in HarnessConfig (default: "feature_complete")
- Config sections in `config.json`:
  - `orchestration: { enabled: bool }`
  - `discoveries: { enabled: bool }`
  - `documentation: { enabled: bool, trigger: str }`

### Changed
- CLAUDE.md template format completely rewritten for AI optimization
  - Table format for commands instead of verbose code blocks
  - Concise flow arrows for session rituals instead of numbered lists
  - Single-line rules instead of multi-paragraph explanations
- `refresh` command now loads `orchestration_enabled` and `discoveries_enabled` from config

### Tests
- Added 51 new tests for:
  - Orchestrate enable/disable/status CLI commands (5 tests)
  - Discovery enable/disable/status CLI commands (5 tests)
  - Documentation enable/disable/status/trigger CLI commands (8 tests)
  - Documentation config and CLAUDE.md section (10 tests)
  - `_build_harness_section()` and helper methods (11 tests)
  - HarnessConfig new fields (8 tests)
  - Session end subtask audit hook (5 tests)
- Total tests: 631 passing

---

## [1.1.2] - 2025-12-15

### Fixed
- CLAUDE.md template now explicitly requires CLI commands for features.json updates
  - Session End Ritual references specific CLI commands instead of ambiguous "Update features.json"
  - Added bold warning: "NEVER manually edit features.json"
  - Prevents agents from manually editing JSON with incorrect data structure
- Added `feature add` command documentation to CLAUDE.md template
  - Documents syntax for adding features with priority and subtasks
- Backwards compatibility for legacy `tests_pass` field in features.json
  - `Feature.from_dict()` now reads `tests_pass` if `tests_passing` is not present
  - Supports features.json files created by older versions or manual editing

### Changed
- Removed "Estimated Context Savings" table from delegation section in CLAUDE.md template
  - Table was documentation for humans, not actionable guidance for agents
  - Saves ~200 tokens per generated CLAUDE.md

---

## [1.1.1] - 2025-12-15

### Fixed
- Refresh command now correctly loads all 12 config values from config.json:
  - port, health_endpoint, start_command, protected_branches, branch_prefixes
  - blocked_actions, delegation_enabled, test_framework
  - unit_test_command, e2e_test_command, coverage_threshold, e2e_enabled
- CLAUDE.md conditional sections now work correctly:
  - E2E validation/test lines appear only when `e2e.enabled: true`
  - SUBAGENT DELEGATION section appears only when `delegation.enabled: true`
- Conflicting messages in `refresh --update-claude-md` (now replaces existing section)
- Regex pattern for CLAUDE.md replacement improved (fixes accumulated `---` separators)

---

## [1.1.0] - 2025-12-14

### Added

#### Session Management & Context Tracking
- **Session-Based Context Tracking**
  - Unique `session_id` per session with lifecycle management
  - `session_closed` flag for clean session transitions
  - Automatic session reset when previous session was closed
  - Session archival to `session-history/` with metrics preserved

- **Compaction Detection**
  - Tracks when estimated tokens exceed context budget
  - Records compaction events with timestamp and metrics
  - `peak_tokens`, `compaction_events` fields in context_metrics.json
  - Compact view: `[!!!] Context: 250% (~2 compactions)`

- **Auto-Save Handoff on Exit**
  - SessionEnd hook saves handoff document when Claude exits
  - Marks session as closed for clean restart
  - Configurable via `auto_save_handoff` config option

- **New Context Commands**
  - `context session-info` - Show current session details
  - `context session-close` - Manually mark session as closed

#### Discoveries Tracking System
- **Discovery Commands** (`claude-harness discovery`)
  - `discovery add` - Add findings with summary, context, tags, impact
  - `discovery list` - List all discoveries (filterable by tag/feature)
  - `discovery show <ID>` - Show detailed discovery information
  - `discovery search <query>` - Search discoveries (case-insensitive)
  - `discovery delete <ID>` - Delete a discovery
  - `discovery tags` - List all unique tags
  - `discovery stats` - Show discovery statistics
  - `discovery summary` - Generate summary for context handoff
- Discoveries persisted in `.claude-harness/discoveries.json`

#### Subagent Delegation System
- **DelegationManager** with rule-based task matching
  - Pattern-based matching (regex support)
  - Priority-based rule selection
  - Token savings estimation per delegation
  - Delegation tracking and metrics

- **Delegation CLI Commands** (`claude-harness delegation`)
  - `delegation status` - Show delegation status and metrics
  - `delegation enable/disable` - Toggle delegation globally
  - `delegation rules` - List all delegation rules
  - `delegation add-rule` - Add custom delegation rules
  - `delegation remove-rule` - Remove rules by name
  - `delegation enable-rule/disable-rule` - Toggle specific rules
  - `delegation suggest <ID>` - Get delegation suggestions for feature subtasks
  - `delegation auto --on/--off` - Configure auto-delegation hints

- **Default Delegation Rules**
  - exploration (explore.*, find.*, search.*) - ~22K tokens saved
  - testing (test.*, write.*test) - ~15K tokens saved
  - documentation (document.*, write.*doc) - ~9K tokens saved
  - review (review.*, audit.*, check.*) - ~17K tokens saved

#### Orchestration Engine
- **OrchestrationEngine** for coordinating automatic subagent delegation
  - State machine: IDLE → EVALUATING → DELEGATING → WAITING → INTEGRATING
  - Configurable thresholds, limits, and behavior settings
  - Delegation queue management with priority ordering

- **Orchestration CLI Commands** (`claude-harness orchestrate`)
  - `orchestrate status` - Show orchestration status and metrics
  - `orchestrate evaluate` - Evaluate current feature for delegation opportunities
  - `orchestrate queue [ID]` - Generate delegation queue for feature
  - `orchestrate start <ID>` - Start a queued delegation
  - `orchestrate complete <ID>` - Mark delegation complete with summary
  - `orchestrate reset` - Reset orchestration session

#### Slash Commands Integration
- **35 Slash Commands** for Claude Code integration
  - Commands auto-generated during `claude-harness init`
  - `/harness-init` - Interactive initialization
  - `/harness-status` - Show current harness status
  - `/harness-feature-*` - Feature management
  - `/harness-progress-*` - Progress tracking
  - `/harness-context-*` - Context management
  - `/harness-delegation-*` - Delegation management
  - `/harness-e2e-generate` - Generate E2E tests

- **CLI Commands for Slash Command Management**
  - `claude-harness commands generate` - Generate slash commands
  - `claude-harness commands list` - List all available commands

#### Feature Management Enhancements
- **Feature Info Command** (`claude-harness feature info <ID>`)
  - Display detailed feature information
  - Show all subtasks with completion status
  - Show creation date, time in current status
  - Display notes and blocked reason history

- **Feature Sync Command** (`claude-harness feature sync`)
  - Infer subtask status from modified files in progress.md
  - Auto-start next pending feature if none in progress
  - Auto-complete features when all subtasks are done
  - `--dry-run` option to preview without changes
  - `--no-auto-start` to disable auto-starting features

- **Subtask Name-Based Completion**
  - Complete subtasks by partial name match (fuzzy matching)
  - Case-insensitive matching

- **Feature Notes Command** (`claude-harness feature note <ID> "text"`)
  - Add timestamped notes to features

- **Enhanced Feature Filtering**
  - `--priority` / `-p` flag to filter by priority
  - `--search` / `-q` flag for name search

- **Bulk Operations**
  - `feature start` accepts multiple feature IDs
  - `feature block` accepts multiple feature IDs
  - `--yes` / `-y` to bypass confirmation

#### Progress Tracking Enhancements
- **Progress History Command** (`claude-harness progress history`)
  - List archived sessions with summaries
  - `--limit N` to show last N sessions
  - `--show <index>` to view specific session details

#### Output Control System
- **OutputHelper** for project-specific output control
  - Configurable truncation to reduce terminal scrolling
  - `output.compact_mode`, `output.max_lines`, `output.max_files_shown`

#### Refresh Command
- **`claude-harness refresh`**
  - Regenerates init.sh, hooks, init.ps1 without losing data
  - Use after upgrading claude-harness to get latest improvements
  - Automatically updates .gitignore for session files
  - Untracks already-tracked session files from git
  - `--update-claude-md` flag to update CLAUDE.md with latest harness section

### Changed

- **init.sh reads config at runtime**
  - Port, health endpoint, start command now read from config.json using `jq`
  - Falls back to defaults if `jq` not available

- **Session files automatically gitignored**
  - `.claude-harness/context_metrics.json`
  - `.claude-harness/session-history/`
  - `.claude-harness/discoveries.json`
  - `.claude-harness/cache/`

- **Hook Configuration**
  - Changed from `Stop` to `SessionEnd` hook for exit handling
  - Hooks now written to `.claude/settings.local.json` (project-specific)

- **CLAUDE.md Template Enhanced**
  - Added "FEATURE TRACKING COMMANDS" section with explicit command examples
  - Session start ritual now requires `feature start <ID>`
  - Clear workflow: `feature start` before work, `feature done` after subtasks

### Fixed
- Session reset now persists to disk immediately
- Hook commands use simple relative paths for reliable execution
- init/refresh now untracks already-tracked session files
- Data preservation on reinit (features.json, progress.md, config.json kept)
- Placeholder text filtering in progress.md (fixes "No tasks in progress" persisting)
- String subtasks in features.json now supported (backwards compatibility for manual/external creation)

---

## [1.0.0] - 2025-12-12

### Added

#### Core Features
- **Project Initialization** (`claude-harness init`)
  - Interactive setup wizard with stack detection
  - Non-interactive mode (`--non-interactive` / `-y`) for CI/CD
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
  - Auto-generation of `.claude/settings.local.json` with hooks
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

### Testing
- Full test suite covering all modules
- 100% pass rate on all test scenarios

---

## [Unreleased]

### Planned
- See [ROADMAP.md](ROADMAP.md) for upcoming features

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 1.1.2 | 2025-12-15 | CLAUDE.md template clarity, tests_pass backwards compat |
| 1.1.1 | 2025-12-15 | Fix refresh config loading, CLAUDE.md conditional sections |
| 1.1.0 | 2025-12-14 | Session tracking, discoveries, delegation, slash commands, refresh |
| 1.0.0 | 2025-12-12 | Initial release with full feature set |
