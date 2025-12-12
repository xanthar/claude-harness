# Claude Harness - Development Guide

## Project Overview

**Claude Harness** is an AI workflow optimization tool for Claude Code that addresses four common failures:
1. Early "done" declarations
2. Messy repositories
3. Lack of real testing
4. Chaotic setup between sessions

## Quick Links

- [README.md](../README.md) - User documentation
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [ROADMAP.md](../ROADMAP.md) - Planned features
- [docs/INTEGRATION_TEST_REPORT.md](../docs/INTEGRATION_TEST_REPORT.md) - Latest test results
- [docs/HOOKS.md](../docs/HOOKS.md) - Hook configuration guide

---

## Development Workflow

### Session Start Ritual

1. **Check git status**: `git status` - ensure clean working directory
2. **Check current branch**: `git branch --show-current`
3. **If on main**: Create feature branch `git checkout -b feat/<feature-name>`
4. **Run tests**: `source venv/bin/activate && pytest tests/ -v --tb=short`
5. **Review ROADMAP.md**: Pick ONE feature to work on

### Session End Ritual

1. **Run full test suite**: `pytest tests/ -v`
2. **Check for regressions**: All 157+ tests should pass
3. **Update CHANGELOG.md** if significant changes
4. **Commit with conventional commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
5. **Push feature branch**: `git push -u origin <branch>`

---

## Project Structure

```
claude_harness/
├── __init__.py           # Version and package info
├── cli.py                # Click CLI commands (main entry point)
├── initializer.py        # Project initialization wizard
├── detector.py           # Stack detection (language, framework, etc.)
├── feature_manager.py    # Feature/task lifecycle management
├── progress_tracker.py   # Session continuity (progress.md)
├── context_tracker.py    # Token usage tracking and compression
├── templates/            # Jinja2 templates for generated files
└── mcp/
    └── playwright_server.py  # MCP Playwright browser automation

tests/
├── test_cli.py           # CLI command tests
├── test_initializer.py   # Initialization tests
├── test_detector.py      # Stack detection tests
├── test_feature_manager.py
├── test_progress_tracker.py
└── test_context_tracker.py

docs/
├── HOOKS.md              # Hook configuration documentation
└── INTEGRATION_TEST_REPORT.md  # Latest integration test results
```

---

## Key Modules

### cli.py
- Entry point for all `claude-harness` commands
- Uses Click framework
- Groups: `main`, `feature`, `progress`, `context`, `e2e`

### initializer.py
- Interactive project setup wizard
- `--non-interactive` mode for automation
- Generates all harness files

### feature_manager.py
- CRUD operations for features
- Status transitions: pending -> in_progress -> completed/blocked
- Subtask management

### progress_tracker.py
- Session continuity via progress.md
- Archival to session-history/
- Parse and update markdown sections

### context_tracker.py
- Token usage estimation
- Session summary/handoff generation
- Compression workflow

---

## Testing

### Run Tests
```bash
source venv/bin/activate
pytest tests/ -v --tb=short
```

### Test Coverage
```bash
pytest tests/ -v --cov=claude_harness --cov-report=term-missing
```

### Current Status
- **157 tests** all passing
- Covers: CLI, initializer, detector, feature_manager, progress_tracker, context_tracker

### Adding Tests
- Follow existing patterns in `tests/`
- Use `pytest` fixtures for setup
- Use `tmp_path` for file operations
- Mock external dependencies (questionary, subprocess)

---

## Git Workflow

### Branch Naming
- `feat/<feature>` - New features
- `fix/<bug>` - Bug fixes
- `docs/<topic>` - Documentation
- `refactor/<scope>` - Code improvements
- `test/<scope>` - Test additions

### Protected Branches
- `main` - Production-ready code only
- Never commit directly to main
- Always use feature branches and PRs

### Commit Convention
```
feat: add feature info command
fix: handle empty subtask list
docs: update ROADMAP with new priorities
test: add tests for unblock command
refactor: simplify feature status transitions
```

---

## Current Priorities

From [ROADMAP.md](../ROADMAP.md):

### High Priority (v1.1.0)
1. Feature info command - `feature info <ID>`
2. Subtask name-based completion
3. Feature notes command

### Medium Priority
4. Progress history command
5. Enhanced feature filtering
6. Bulk operations

See ROADMAP.md for full list with descriptions.

---

## Code Style

- **Python 3.11+** required
- **Type hints** for function signatures
- **Docstrings** for public functions
- **Black** for formatting (if configured)
- **Rich** for terminal output
- **Click** for CLI

### Example Function
```python
def add_feature(
    self,
    name: str,
    priority: int = 0,
    subtasks: Optional[List[str]] = None,
    notes: str = "",
) -> Feature:
    """Add a new feature.

    Args:
        name: Feature name/description
        priority: Lower number = higher priority
        subtasks: List of subtask names
        notes: Additional notes

    Returns:
        The created Feature object
    """
    ...
```

---

## Dependencies

### Runtime
- click - CLI framework
- rich - Terminal formatting
- questionary - Interactive prompts
- jinja2 - Template rendering
- playwright - Browser automation (optional)

### Development
- pytest - Testing
- pytest-cov - Coverage

---

## Release Process

1. Update version in `__init__.py`
2. Update CHANGELOG.md with release notes
3. Run full test suite
4. Create release commit: `chore: release v1.x.x`
5. Tag release: `git tag v1.x.x`
6. Push with tags: `git push --tags`

---

## Troubleshooting

### Tests Failing
```bash
# Run specific test file
pytest tests/test_cli.py -v

# Run with debug output
pytest tests/ -v -s --tb=long
```

### Import Errors
```bash
# Reinstall in dev mode
pip install -e .
```

### Virtual Environment
```bash
# Recreate venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

---

*This project follows its own philosophy: one feature at a time, tests required, clean repo always.*
