# Claude Harness - Development Guide

## Project Overview

**Claude Harness** (v1.2.0) is an AI workflow optimization tool for Claude Code that addresses four common failures:
1. Early "done" declarations → Feature tracking with subtasks
2. Messy repositories → Git safety hooks and progress logging
3. Lack of real testing → E2E test generation and validation
4. Chaotic setup between sessions → Startup scripts and session handoffs

## Quick Links

- [README.md](../README.md) - User documentation
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [ROADMAP.md](../ROADMAP.md) - Planned features
- [docs/HOOKS.md](../docs/HOOKS.md) - Hook configuration guide

---

## Project Structure

```
claude_harness/
├── __init__.py            # Version and package info (v1.2.0)
├── cli.py                 # Click CLI commands (main entry point)
├── initializer.py         # Project initialization wizard
├── detector.py            # Stack detection (language, framework, etc.)
├── feature_manager.py     # Feature/task lifecycle management
├── progress_tracker.py    # Session continuity (progress.md)
├── context_tracker.py     # Token usage tracking and compression
├── delegation_manager.py  # Subagent delegation with rule matching
├── discoveries.py         # Knowledge/findings tracker
├── command_generator.py   # Slash command generation for Claude Code
├── exploration_cache.py   # Caching for codebase exploration
├── file_filter.py         # Smart file filtering for context
├── file_read_optimizer.py # Optimized file reading strategies
├── lazy_loader.py         # Lazy context loading
├── orchestration_engine.py # Multi-step task orchestration
├── output_compressor.py   # Output compression utilities
├── output_helper.py       # Configurable output formatting
├── templates/             # Jinja2 templates for generated files
└── mcp/
    ├── __init__.py
    └── playwright_server.py  # MCP Playwright browser automation

tests/
├── test_cli.py
├── test_initializer.py
├── test_detector.py
├── test_feature_manager.py
├── test_progress_tracker.py
├── test_context_tracker.py
├── test_delegation_manager.py
├── test_discoveries.py
├── test_command_generator.py
├── test_exploration_cache.py
├── test_file_filter.py
├── test_file_read_optimizer.py
├── test_lazy_loader.py
├── test_orchestration_engine.py
├── test_output_compressor.py
└── test_output_helper.py

docs/
├── HOOKS.md                        # Hook configuration documentation
├── ORCHESTRATION_UX_DESIGN.md      # Orchestration design (implemented in v1.1.0)
└── SUBAGENT_DELEGATION_RESEARCH.md # Delegation research (implemented in v1.1.0)
```

---

## Key Modules

### Core

| Module | Purpose |
|--------|---------|
| `cli.py` | Click CLI with groups: main, feature, progress, context, discovery, delegation, orchestrate, e2e, optimize, commands |
| `initializer.py` | Interactive/non-interactive project setup, generates all harness files |
| `detector.py` | Auto-detects language, framework, database, test framework |
| `feature_manager.py` | Feature CRUD, status transitions, subtask management |
| `progress_tracker.py` | Session continuity via progress.md, archival |
| `context_tracker.py` | Token estimation, session lifecycle, compaction detection |

### Advanced Features

| Module | Purpose |
|--------|---------|
| `delegation_manager.py` | Rule-based task delegation to subagents |
| `discoveries.py` | Track findings, requirements, institutional knowledge |
| `command_generator.py` | Generate 35 slash commands for Claude Code |
| `orchestration_engine.py` | Multi-step task planning and execution |

### Optimization

| Module | Purpose |
|--------|---------|
| `exploration_cache.py` | Cache codebase exploration results |
| `file_filter.py` | Smart filtering for context optimization |
| `file_read_optimizer.py` | Intelligent file reading (structure extraction, chunking) |
| `lazy_loader.py` | Deferred context loading |
| `output_compressor.py` | Compress verbose outputs |
| `output_helper.py` | Configurable output truncation |

---

## Development Workflow

### Session Start
```bash
git status                              # Ensure clean working directory
git branch --show-current               # Check current branch
git checkout -b feat/<feature-name>     # Create feature branch if on main
source .venv/bin/activate               # Activate virtual environment
pytest tests/ -q --tb=line              # Quick test check
```

### Session End
```bash
pytest tests/ -v --tb=short             # Full test suite (609 tests)
# Update CHANGELOG.md if significant changes
git add -A && git commit -m "feat: ..." # Conventional commit
git push -u origin <branch>             # Push feature branch
```

---

## Testing

### Commands
```bash
# Quick test run
pytest tests/ -q --tb=line

# Full test suite with coverage
pytest tests/ -v --cov=claude_harness --cov-report=term-missing

# Specific module
pytest tests/test_cli.py -v

# Debug mode
pytest tests/ -v -s --tb=long
```

### Current Status
- **614 tests** all passing
- Full coverage of all modules

### Test Patterns
- Use `pytest` fixtures for setup
- Use `tmp_path` for file operations
- Mock external dependencies (questionary, subprocess)
- Follow existing patterns in `tests/`

---

## CLI Command Groups

| Group | Commands |
|-------|----------|
| `main` | init, refresh, status, detect, run |
| `feature` | list, add, start, complete, block, unblock, info, note, done, tests, e2e-pass |
| `progress` | show, completed, wip, blocker, file, new-session, history |
| `context` | show, reset, budget, start-task, end-task, summary, handoff, compress, metadata, session-info, session-close |
| `discovery` | add, list, show, search, delete, tags, stats, summary, enable, disable, status |
| `delegation` | status, enable, disable, rules, add-rule, remove-rule, suggest, auto |
| `orchestrate` | status, enable, disable, evaluate, queue, start, complete, reset, plan, run |
| `e2e` | install, run, generate |
| `optimize` | status, cache-status, cache-clear, cache-prune |
| `commands` | generate, list |

---

## Git Workflow

### Branch Naming
- `feat/<feature>` - New features
- `fix/<bug>` - Bug fixes
- `docs/<topic>` - Documentation
- `refactor/<scope>` - Code improvements
- `chore/<scope>` - Maintenance
- `test/<scope>` - Test additions

### Commit Convention
```
feat: add new feature
fix: resolve bug
docs: update documentation
test: add tests
refactor: improve code structure
chore: maintenance tasks
```

---

## Dependencies

### Runtime
- click - CLI framework
- jinja2 - Template rendering
- rich - Terminal formatting
- questionary - Interactive prompts
- toml - TOML parsing
- playwright - Browser automation (optional)

### Development
- pytest - Testing framework
- pytest-cov - Coverage reporting
- black - Code formatting
- ruff - Linting
- mypy - Type checking

---

## Code Style

- **Python 3.10+** required
- **Type hints** for function signatures
- **Docstrings** for public functions
- **Rich** for terminal output
- **Click** for CLI

---

## Release Process

1. Update version in `claude_harness/__init__.py`
2. Update version in `pyproject.toml` and `setup.py`
3. Update CHANGELOG.md with release notes
4. Run full test suite: `pytest tests/ -v`
5. Commit: `chore: release v1.x.x`
6. Tag: `git tag v1.x.x`
7. Push: `git push origin main --tags`

---

## Current Priorities

From [ROADMAP.md](../ROADMAP.md):

### v1.3.0 - History Import & Bootstrapping
- Bootstrap command - Import existing work
- Import from documentation
- Git history analysis
- Manual backfill helper

### v1.4.0 - Advanced Features
- Configuration validation
- Export functionality
- Feature dependencies

---

## Troubleshooting

### Tests Failing
```bash
pytest tests/test_cli.py -v          # Run specific file
pytest tests/ -v -s --tb=long        # Debug output
```

### Import Errors
```bash
pip install -e .                     # Reinstall in dev mode
```

### Virtual Environment
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

*This project follows its own philosophy: one feature at a time, tests required, clean repo always.*
