# Claude Harness Roadmap

This document outlines planned features and improvements for Claude Harness, prioritized based on user impact.

---

## Version 1.2.0 - History Import & Bootstrapping

**Target:** Next minor release
**Focus:** Import existing work into harness for established codebases

### High Priority

#### 1. Bootstrap Command
- [ ] `claude-harness bootstrap` - Import existing work into features.json
- Scan CHANGELOG.md for past releases/features
- Parse git tags/commits for feature history
- Interactive mode to confirm/edit detected features

#### 2. Import from Documentation
- [ ] `claude-harness import --from docs/` - Scan documentation for features
- Parse README, feature specs, architecture docs
- Extract completed work items as features

#### 3. Git History Analysis
- [ ] `claude-harness import --from git` - Analyze git history
- Parse conventional commit messages (feat:, fix:, etc.)
- Group by release tags
- Generate feature entries with completion dates

#### 4. Manual Backfill Helper
- [ ] `claude-harness feature add-completed "Feature Name" --date 2025-01-01`
- Bulk import from CSV/JSON
- Template for manual backfill

### Problem This Solves

When initializing harness on an existing codebase (e.g., a project with 20+ completed features), `features.json` starts empty. All past work is "invisible" to the harness. These commands allow importing historical work for complete tracking.

---

## Version 1.3.0 - Advanced Features

**Target:** Future release
**Focus:** Power user features and automation

### Medium Priority

#### 5. Configuration Validation
- [ ] `claude-harness validate` - Validate harness configuration
- Check config.json schema
- Verify features.json integrity
- Check hook script permissions
- Validate E2E setup

#### 6. Export Functionality
- [ ] `claude-harness export features --format csv` - Export features to CSV
- [ ] `claude-harness export progress --format json` - Export progress data
- [ ] `claude-harness export report` - Generate full project report

#### 7. Feature Dependencies
- [ ] Add `depends_on` field to features
- Block starting feature if dependencies incomplete
- Visual dependency tree: `claude-harness feature tree`

### Low Priority

#### 8. Time Tracking
- [ ] Track time spent on each feature
- Record start/stop timestamps
- Session duration tracking
- Time summary reports

#### 9. Interactive Tutorial
- [ ] `claude-harness tutorial` - Guided walkthrough
- Step-by-step introduction to all commands
- Example project setup
- Best practices guidance

#### 10. Template System
- [ ] `claude-harness init --template flask` - Use predefined templates
- Community template repository
- Custom template creation

---

## Version 2.0.0 - Enterprise Features

**Target:** Major release
**Focus:** Team collaboration and enterprise needs

### Planned Features

#### 11. Team Collaboration
- [ ] Shared progress tracking
- [ ] Feature assignment
- [ ] Conflict resolution for concurrent edits

#### 12. CI/CD Integration
- [ ] GitHub Actions integration
- [ ] GitLab CI templates
- [ ] Jenkins pipeline support

#### 13. Metrics Dashboard
- [ ] Web-based dashboard
- [ ] Feature velocity tracking
- [ ] Session analytics

#### 14. Plugin System
- [ ] Custom hook plugins
- [ ] Third-party integrations
- [ ] Extension API

---

## Completed Features

### v1.1.0 (2025-12-14)

#### Session Management & Context Tracking
- [x] Session-based context tracking with unique session IDs
- [x] Compaction detection (peak_tokens, compaction_events)
- [x] Auto-save handoff on session exit (SessionEnd hook)
- [x] `context session-info` and `context session-close` commands

#### Discoveries Tracking
- [x] `discovery add/list/show/search/delete` commands
- [x] Tag-based filtering and statistics
- [x] Discovery summary for handoffs

#### Subagent Delegation System
- [x] `DelegationManager` with rule-based task matching
- [x] `delegation status/enable/disable/rules` commands
- [x] `delegation add-rule/remove-rule/suggest` commands
- [x] Default rules for exploration, testing, documentation, review
- [x] Token savings estimation (40-70% context savings)
- [x] CLAUDE.md delegation section generation

#### Slash Commands Integration
- [x] 35 slash commands for Claude Code integration
- [x] `/harness-init` - Interactive initialization
- [x] `/harness-*` commands for all harness features
- [x] `claude-harness commands generate/list` CLI commands

#### Feature Management Enhancements
- [x] `feature info <ID>` - Detailed feature display
- [x] `feature done <ID> <name>` - Fuzzy subtask completion
- [x] `feature note <ID> "text"` - Timestamped notes
- [x] `--priority` and `--search` filtering
- [x] Bulk operations with `--yes` flag

#### Progress Tracking Enhancements
- [x] `progress history` command with `--limit` and `--show`

#### Output Control
- [x] OutputHelper for configurable output truncation
- [x] `output.compact_mode`, `output.max_lines`, `output.max_files_shown`

#### Refresh Command
- [x] `claude-harness refresh` - Regenerate scripts without losing data
- [x] Runtime config reading in init.sh (jq-based)
- [x] Auto gitignore/untrack session files
- [x] Data preservation on reinit

### v1.0.0 (2025-12-12)

#### Core Features
- [x] Project initialization with stack detection
- [x] Non-interactive mode (`--non-interactive`)
- [x] Feature management (add, start, complete, block, unblock)
- [x] Progress tracking with session archival
- [x] Context tracking with token estimation
- [x] Session compression and handoff documents

#### E2E Testing
- [x] Playwright integration
- [x] Test generation from features

#### Stack Detection
- [x] Python (Flask, Django, FastAPI)
- [x] JavaScript/TypeScript (Express, Next.js, React, Vue)
- [x] Database detection (PostgreSQL, MySQL, SQLite, MongoDB, Redis)

#### Startup Scripts
- [x] `scripts/init.sh` (Bash)
- [x] `scripts/init.ps1` (PowerShell)

#### Claude Code Integration
- [x] Git safety hooks (block protected branch commits)
- [x] Auto-progress tracking hooks
- [x] Activity logging hooks

#### MCP Server
- [x] Playwright browser automation server
- [x] 14 browser control tools

---

## Contributing

We welcome contributions! To propose a new feature:

1. Check if it's already on the roadmap
2. Open an issue with the `enhancement` label
3. Describe the use case and proposed implementation
4. Reference this roadmap in your PR

### Priority Guidelines

- **High**: Directly improves core workflow, blocks common use cases
- **Medium**: Quality of life improvements, power user features
- **Low**: Nice to have, edge cases, future considerations

---

## Feedback

Found an issue or have a suggestion?

- Open an issue on GitHub
- Reference the roadmap item number if applicable
- Include your use case and expected behavior

---

*Last updated: 2025-12-14*
