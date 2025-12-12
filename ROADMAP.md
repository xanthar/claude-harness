# Claude Harness Roadmap

This document outlines planned features and improvements for Claude Harness, prioritized based on user impact and integration test feedback.

See [docs/INTEGRATION_TEST_REPORT.md](docs/INTEGRATION_TEST_REPORT.md) for the full test analysis.

---

## Version 1.1.0 - Usability Improvements

**Target:** Next minor release
**Focus:** Enhanced feature management and CLI usability

### High Priority

#### 1. Feature Info Command
- [ ] `claude-harness feature info <ID>` - Show detailed feature information
- Display all subtasks with status
- Show creation date, time in status
- Display notes and blocked reason history

#### 2. Subtask Name-Based Completion
- [ ] `claude-harness feature done <ID> <subtask-name>` - Complete subtask by name
- Fuzzy matching for partial names
- Confirmation prompt if multiple matches

#### 3. Feature Notes Command
- [ ] `claude-harness feature note <ID> "note text"` - Add notes to features
- Timestamped notes
- View notes in feature info

### Medium Priority

#### 4. Progress History Command
- [ ] `claude-harness progress history` - View previous sessions
- List archived sessions with summaries
- `--last N` to show last N sessions
- `--date YYYY-MM-DD` to show specific date

#### 5. Enhanced Feature Filtering
- [ ] `claude-harness feature list --status blocked` - Already exists, document better
- [ ] `claude-harness feature list --priority 1` - Filter by priority
- [ ] `claude-harness feature list --search "auth"` - Search in names

#### 6. Bulk Operations
- [ ] `claude-harness feature start F-001 F-002` - Start multiple (with warning)
- [ ] `claude-harness feature block F-001 F-002 -r "reason"` - Block multiple

---

## Version 1.2.0 - Advanced Features

**Target:** Future release
**Focus:** Power user features and automation

### Medium Priority

#### 7. Configuration Validation
- [ ] `claude-harness validate` - Validate harness configuration
- Check config.json schema
- Verify features.json integrity
- Check hook script permissions
- Validate E2E setup

#### 8. Export Functionality
- [ ] `claude-harness export features --format csv` - Export features to CSV
- [ ] `claude-harness export progress --format json` - Export progress data
- [ ] `claude-harness export report` - Generate full project report

#### 9. Feature Dependencies
- [ ] Add `depends_on` field to features
- Block starting feature if dependencies incomplete
- Visual dependency tree: `claude-harness feature tree`

### Low Priority

#### 10. Time Tracking
- [ ] Track time spent on each feature
- Record start/stop timestamps
- Session duration tracking
- Time summary reports

#### 11. Interactive Tutorial
- [ ] `claude-harness tutorial` - Guided walkthrough
- Step-by-step introduction to all commands
- Example project setup
- Best practices guidance

#### 12. Template System
- [ ] `claude-harness init --template flask` - Use predefined templates
- Community template repository
- Custom template creation

---

## Version 2.0.0 - Enterprise Features

**Target:** Major release
**Focus:** Team collaboration and enterprise needs

### Planned Features

#### 13. Team Collaboration
- [ ] Shared progress tracking
- [ ] Feature assignment
- [ ] Conflict resolution for concurrent edits

#### 14. CI/CD Integration
- [ ] GitHub Actions integration
- [ ] GitLab CI templates
- [ ] Jenkins pipeline support

#### 15. Metrics Dashboard
- [ ] Web-based dashboard
- [ ] Feature velocity tracking
- [ ] Session analytics

#### 16. Plugin System
- [ ] Custom hook plugins
- [ ] Third-party integrations
- [ ] Extension API

---

## Completed Features

### v1.0.0 (2025-12-12)
- [x] Non-interactive initialization (`--non-interactive`)
- [x] Feature unblock command (`feature unblock`)
- [x] Context compression and handoff
- [x] Auto-progress tracking hooks
- [x] MCP Playwright server
- [x] Comprehensive test coverage (157 tests)

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

*Last updated: 2025-12-12*
