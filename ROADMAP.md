# Claude Harness Roadmap

This document outlines planned features and improvements for Claude Harness, prioritized based on user impact and integration test feedback.

See [docs/INTEGRATION_TEST_REPORT.md](docs/INTEGRATION_TEST_REPORT.md) for the full test analysis.

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

## Version 1.3.0 - Subagent Delegation

**Target:** Next minor release
**Focus:** Context optimization through intelligent task delegation

### High Priority

#### 7. Subagent Delegation System
- [x] `DelegationManager` class for managing delegation rules and tracking
- [x] `DelegationRule` dataclass with regex pattern matching
- [x] `DelegationConfig` dataclass with default rules
- [x] `DelegationResult` tracking for delegation metrics

#### 8. Delegation CLI Commands
- [x] `claude-harness delegation status` - Show delegation status and metrics
- [x] `claude-harness delegation enable/disable` - Toggle delegation globally
- [x] `claude-harness delegation rules` - List all delegation rules
- [x] `claude-harness delegation add-rule` - Add custom delegation rules
- [x] `claude-harness delegation remove-rule` - Remove rules by name
- [x] `claude-harness delegation enable-rule/disable-rule` - Toggle specific rules
- [x] `claude-harness delegation suggest <ID>` - Get suggestions for a feature
- [x] `claude-harness delegation auto --on/--off` - Configure auto-delegation hints

#### 9. CLAUDE.md Delegation Integration
- [x] Generate delegation section in CLAUDE.md template
- [x] Include subagent type recommendations
- [x] Token savings estimates per task type
- [x] Constraint propagation to subagents

### Benefits
- **40-70% context savings** by delegating to specialized subagents
- **Parallel execution** of independent tasks
- **Summary-based returns** (3-5K tokens vs 25K+ full execution)
- **Pattern-based matching** for automatic delegation suggestions

### Default Delegation Rules
| Rule | Patterns | Subagent Type | Est. Savings |
|------|----------|---------------|--------------|
| exploration | explore.*, find.*, search.*, investigate.* | explore | 22K tokens |
| testing | test.*, write.*test, unit.*test, integration.*test | test | 15K tokens |
| documentation | document.*, write.*doc, update.*readme | document | 9K tokens |
| review | review.*, audit.*, check.*, validate.* | review | 17K tokens |

---

## Version 1.4.0 - Advanced Features

**Target:** Future release
**Focus:** Power user features and automation

### Medium Priority

#### 10. Configuration Validation
- [ ] `claude-harness validate` - Validate harness configuration
- Check config.json schema
- Verify features.json integrity
- Check hook script permissions
- Validate E2E setup

#### 11. Export Functionality
- [ ] `claude-harness export features --format csv` - Export features to CSV
- [ ] `claude-harness export progress --format json` - Export progress data
- [ ] `claude-harness export report` - Generate full project report

#### 12. Feature Dependencies
- [ ] Add `depends_on` field to features
- Block starting feature if dependencies incomplete
- Visual dependency tree: `claude-harness feature tree`

### Low Priority

#### 13. Time Tracking
- [ ] Track time spent on each feature
- Record start/stop timestamps
- Session duration tracking
- Time summary reports

#### 14. Interactive Tutorial
- [ ] `claude-harness tutorial` - Guided walkthrough
- Step-by-step introduction to all commands
- Example project setup
- Best practices guidance

#### 15. Template System
- [ ] `claude-harness init --template flask` - Use predefined templates
- Community template repository
- Custom template creation

---

## Version 2.0.0 - Enterprise Features

**Target:** Major release
**Focus:** Team collaboration and enterprise needs

### Planned Features

#### 16. Team Collaboration
- [ ] Shared progress tracking
- [ ] Feature assignment
- [ ] Conflict resolution for concurrent edits

#### 17. CI/CD Integration
- [ ] GitHub Actions integration
- [ ] GitLab CI templates
- [ ] Jenkins pipeline support

#### 18. Metrics Dashboard
- [ ] Web-based dashboard
- [ ] Feature velocity tracking
- [ ] Session analytics

#### 19. Plugin System
- [ ] Custom hook plugins
- [ ] Third-party integrations
- [ ] Extension API

---

## Completed Features

### v1.1.0 (2025-12-13)
- [x] Refresh command (`claude-harness refresh`) - Regenerate scripts without losing data
- [x] Compaction detection in context tracker (peak_tokens, compaction_events)
- [x] Runtime config reading in init.sh (jq-based, no more hardcoded values)
- [x] Auto gitignore/untrack session files (context_metrics.json, session-history/)
- [x] Data preservation on reinit (features.json, progress.md, config.json kept)

### v1.4.0 (2025-12-12)
- [x] 35 slash commands for Claude Code integration
- [x] `/harness-init` - Interactive initialization inside Claude Code
- [x] `/harness-*` commands for all harness features
- [x] `claude-harness commands generate/list` CLI commands
- [x] Commands auto-generated during init

### v1.3.0 (2025-12-12)
- [x] Subagent delegation system with rule-based matching
- [x] Delegation CLI commands (status, enable, disable, rules, suggest, auto)
- [x] CLAUDE.md delegation section generation
- [x] Token savings estimation and metrics tracking
- [x] Default rules for exploration, testing, documentation, review

### v1.1.0 (2025-12-12)
- [x] Feature info command (`feature info <ID>`)
- [x] Subtask name-based completion (`feature done <ID> <name>`)
- [x] Feature notes command (`feature note <ID> "text"`)
- [x] Progress history command (`progress history`)
- [x] Enhanced feature filtering (`--priority`, `--search`)
- [x] Bulk operations (`feature start/block` with multiple IDs)

### v1.0.0 (2025-12-12)
- [x] Non-interactive initialization (`--non-interactive`)
- [x] Feature unblock command (`feature unblock`)
- [x] Context compression and handoff
- [x] Auto-progress tracking hooks
- [x] MCP Playwright server
- [x] Comprehensive test coverage (170 tests)

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

*Last updated: 2025-12-13*
