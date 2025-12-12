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

## [Unreleased]

### Planned
- See [ROADMAP.md](ROADMAP.md) for upcoming features

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 1.0.0 | 2025-12-12 | Initial release with full feature set |
