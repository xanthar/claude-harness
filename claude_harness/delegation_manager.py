"""Subagent delegation management for Claude Harness.

Provides configuration and prompt generation for delegating tasks to
specialized Claude Code subagents, reducing main agent context usage.

Key components:
- DelegationRule: Pattern-based rules for task delegation
- DelegationConfig: Configuration for delegation behavior
- DelegationManager: Manages rules, generates prompts, tracks delegation
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


# --- Data Classes ---


@dataclass
class DelegationRule:
    """A rule for when to delegate tasks to subagents."""

    name: str
    task_patterns: List[str]  # Regex patterns matching subtask names
    subagent_type: str  # "explore", "test", "document", "review", "general"
    priority: int = 5  # Higher = more likely to delegate (1-10)
    enabled: bool = True
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "task_patterns": self.task_patterns,
            "subagent_type": self.subagent_type,
            "priority": self.priority,
            "enabled": self.enabled,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DelegationRule":
        return cls(
            name=data["name"],
            task_patterns=data.get("task_patterns", []),
            subagent_type=data.get("subagent_type", "general"),
            priority=data.get("priority", 5),
            enabled=data.get("enabled", True),
            constraints=data.get("constraints", []),
        )

    def matches(self, task_name: str) -> bool:
        """Check if this rule matches a task name."""
        if not self.enabled:
            return False
        task_lower = task_name.lower()
        for pattern in self.task_patterns:
            try:
                if re.search(pattern.lower(), task_lower):
                    return True
            except re.error:
                # Invalid regex, try simple substring match
                if pattern.lower() in task_lower:
                    return True
        return False


@dataclass
class DelegationConfig:
    """Configuration for subagent delegation."""

    enabled: bool = False
    auto_delegate: bool = False  # Automatically suggest delegation in CLAUDE.md
    parallel_limit: int = 3  # Max concurrent subagents to suggest
    summary_max_words: int = 500  # Max words in subagent summaries
    context_threshold: float = 0.5  # Only delegate when context > this % used
    rules: List[DelegationRule] = field(default_factory=list)
    default_constraints: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Set default rules if none provided."""
        if not self.rules:
            self.rules = self._default_rules()
        if not self.default_constraints:
            self.default_constraints = [
                "Keep summaries concise to preserve main agent context",
                "Report file paths as absolute paths",
                "Include specific line numbers when relevant",
            ]

    @staticmethod
    def _default_rules() -> List[DelegationRule]:
        """Create default delegation rules."""
        return [
            DelegationRule(
                name="exploration",
                task_patterns=[
                    r"explore.*", r"investigate.*", r"find.*", r"discover.*",
                    r"search.*", r"analyze.*codebase", r"understand.*",
                ],
                subagent_type="explore",
                priority=10,
                constraints=["Read-only operations", "Focus on file structure and patterns"],
            ),
            DelegationRule(
                name="testing",
                task_patterns=[
                    r"test.*", r"write.*test.*", r"unit test.*", r"e2e.*",
                    r"integration test.*", r"add.*test.*",
                ],
                subagent_type="test",
                priority=8,
                constraints=["Use project test framework", "Include edge cases", "Mock external services"],
            ),
            DelegationRule(
                name="documentation",
                task_patterns=[
                    r"document.*", r"doc.*", r"readme.*", r"comment.*",
                    r"write.*doc.*", r"update.*doc.*",
                ],
                subagent_type="document",
                priority=6,
                constraints=["Follow project doc conventions", "Be concise", "Include examples"],
            ),
            DelegationRule(
                name="review",
                task_patterns=[
                    r"review.*", r"audit.*", r"check.*", r"validate.*",
                    r"security.*", r"performance.*",
                ],
                subagent_type="review",
                priority=7,
                constraints=["Focus on critical issues", "Provide actionable feedback"],
            ),
        ]

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "auto_delegate": self.auto_delegate,
            "parallel_limit": self.parallel_limit,
            "summary_max_words": self.summary_max_words,
            "context_threshold": self.context_threshold,
            "rules": [r.to_dict() for r in self.rules],
            "default_constraints": self.default_constraints,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DelegationConfig":
        rules = [DelegationRule.from_dict(r) for r in data.get("rules", [])]
        return cls(
            enabled=data.get("enabled", False),
            auto_delegate=data.get("auto_delegate", False),
            parallel_limit=data.get("parallel_limit", 3),
            summary_max_words=data.get("summary_max_words", 500),
            context_threshold=data.get("context_threshold", 0.5),
            rules=rules if rules else None,  # Will trigger default rules
            default_constraints=data.get("default_constraints", []),
        )


@dataclass
class DelegationResult:
    """Result of a delegated task."""

    feature_id: str
    subtask_name: str
    subagent_type: str
    status: str  # "pending", "completed", "failed"
    summary: str = ""
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    estimated_tokens_saved: int = 0
    delegated_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.delegated_at:
            self.delegated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "subtask_name": self.subtask_name,
            "subagent_type": self.subagent_type,
            "status": self.status,
            "summary": self.summary,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "estimated_tokens_saved": self.estimated_tokens_saved,
            "delegated_at": self.delegated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DelegationResult":
        return cls(
            feature_id=data["feature_id"],
            subtask_name=data["subtask_name"],
            subagent_type=data.get("subagent_type", "general"),
            status=data.get("status", "pending"),
            summary=data.get("summary", ""),
            files_created=data.get("files_created", []),
            files_modified=data.get("files_modified", []),
            estimated_tokens_saved=data.get("estimated_tokens_saved", 0),
            delegated_at=data.get("delegated_at", ""),
            completed_at=data.get("completed_at"),
        )


# --- Manager Class ---


class DelegationManager:
    """Manages subagent delegation rules, prompts, and tracking."""

    # Token estimates for different task types
    TOKEN_ESTIMATES = {
        "explore": 25000,
        "test": 18000,
        "document": 12000,
        "review": 20000,
        "general": 15000,
    }

    # Summary return estimates (what comes back to main agent)
    SUMMARY_ESTIMATES = {
        "explore": 3000,
        "test": 5000,
        "document": 3000,
        "review": 5000,
        "general": 4000,
    }

    def __init__(self, project_path: str):
        """Initialize with project path."""
        self.project_path = Path(project_path).resolve()
        self.config_file = self.project_path / ".claude-harness" / "config.json"
        self.delegation_file = self.project_path / ".claude-harness" / "delegation.json"
        self._config: Optional[DelegationConfig] = None

    def _load_config(self) -> DelegationConfig:
        """Load delegation config from config.json."""
        if self._config is not None:
            return self._config

        if not self.config_file.exists():
            self._config = DelegationConfig()
            return self._config

        with open(self.config_file) as f:
            data = json.load(f)

        delegation_data = data.get("delegation", {})
        self._config = DelegationConfig.from_dict(delegation_data)
        return self._config

    def _save_config(self):
        """Save delegation config to config.json."""
        if self._config is None:
            return

        # Load existing config
        if self.config_file.exists():
            with open(self.config_file) as f:
                data = json.load(f)
        else:
            data = {}

        # Update delegation section
        data["delegation"] = self._config.to_dict()

        # Save
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_delegation_tracking(self) -> Dict[str, List[dict]]:
        """Load delegation tracking data."""
        if not self.delegation_file.exists():
            return {"delegations": [], "metrics": {}}

        with open(self.delegation_file) as f:
            return json.load(f)

    def _save_delegation_tracking(self, data: dict):
        """Save delegation tracking data."""
        self.delegation_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.delegation_file, "w") as f:
            json.dump(data, f, indent=2)

    # --- Configuration Methods ---

    def get_config(self) -> DelegationConfig:
        """Get current delegation configuration."""
        return self._load_config()

    def is_enabled(self) -> bool:
        """Check if delegation is enabled."""
        return self._load_config().enabled

    def enable(self):
        """Enable delegation."""
        config = self._load_config()
        config.enabled = True
        self._save_config()

    def disable(self):
        """Disable delegation."""
        config = self._load_config()
        config.enabled = False
        self._save_config()

    def set_auto_delegate(self, enabled: bool):
        """Enable or disable auto-delegation hints."""
        config = self._load_config()
        config.auto_delegate = enabled
        self._save_config()

    # --- Rule Management ---

    def get_rules(self) -> List[DelegationRule]:
        """Get all delegation rules."""
        return self._load_config().rules

    def add_rule(self, rule: DelegationRule):
        """Add a new delegation rule."""
        config = self._load_config()

        # Check for duplicate name
        for existing in config.rules:
            if existing.name == rule.name:
                raise ValueError(f"Rule with name '{rule.name}' already exists")

        config.rules.append(rule)
        self._save_config()

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a delegation rule by name."""
        config = self._load_config()

        for i, rule in enumerate(config.rules):
            if rule.name == rule_name:
                config.rules.pop(i)
                self._save_config()
                return True

        return False

    def enable_rule(self, rule_name: str) -> bool:
        """Enable a specific rule."""
        config = self._load_config()

        for rule in config.rules:
            if rule.name == rule_name:
                rule.enabled = True
                self._save_config()
                return True

        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Disable a specific rule."""
        config = self._load_config()

        for rule in config.rules:
            if rule.name == rule_name:
                rule.enabled = False
                self._save_config()
                return True

        return False

    # --- Matching and Suggestion ---

    def should_delegate(self, subtask_name: str) -> Optional[DelegationRule]:
        """Determine if a subtask should be delegated.

        Returns the matching rule with highest priority, or None if no match.
        """
        config = self._load_config()

        if not config.enabled:
            return None

        matching_rules = []
        for rule in config.rules:
            if rule.matches(subtask_name):
                matching_rules.append(rule)

        if not matching_rules:
            return None

        # Return highest priority rule
        return max(matching_rules, key=lambda r: r.priority)

    def get_delegation_suggestions(
        self, subtasks: List[str]
    ) -> List[tuple[str, DelegationRule]]:
        """Get delegation suggestions for a list of subtasks.

        Returns list of (subtask_name, matching_rule) tuples.
        """
        suggestions = []
        for subtask in subtasks:
            rule = self.should_delegate(subtask)
            if rule:
                suggestions.append((subtask, rule))
        return suggestions

    def estimate_savings(self, subtask_name: str, rule: DelegationRule) -> int:
        """Estimate token savings from delegating a task."""
        full_tokens = self.TOKEN_ESTIMATES.get(rule.subagent_type, 15000)
        summary_tokens = self.SUMMARY_ESTIMATES.get(rule.subagent_type, 4000)
        return full_tokens - summary_tokens

    # --- Prompt Generation ---

    def generate_delegation_prompt(
        self,
        subtask_name: str,
        feature_name: str,
        feature_id: str,
        rule: DelegationRule,
        relevant_files: Optional[List[str]] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """Generate a Task tool prompt for delegating a subtask."""
        config = self._load_config()

        # Combine constraints
        all_constraints = config.default_constraints + rule.constraints

        prompt = f"""## Delegated Task: {subtask_name}

**Feature:** {feature_name} (ID: {feature_id})
**Subagent Type:** {rule.subagent_type}

### Task Description
{subtask_name}

### Context
"""
        if additional_context:
            prompt += f"{additional_context}\n\n"

        if relevant_files:
            prompt += "### Relevant Files\n"
            for f in relevant_files:
                prompt += f"- {f}\n"
            prompt += "\n"

        prompt += "### Constraints\n"
        for constraint in all_constraints:
            prompt += f"- {constraint}\n"

        prompt += f"""
### Output Requirements
Provide a concise summary (under {config.summary_max_words} words) containing:

1. **What was accomplished** - Brief description of work done
2. **Files created/modified** - List with absolute paths
3. **Key decisions made** - Important choices and rationale
4. **Issues encountered** - Any problems or blockers
5. **Recommended next steps** - What should happen next

Format your response as structured YAML for easy parsing.
"""
        return prompt

    def generate_claude_md_section(
        self,
        feature_name: str,
        feature_id: str,
        subtasks: List[str],
    ) -> str:
        """Generate CLAUDE.md section with delegation instructions."""
        config = self._load_config()

        if not config.enabled:
            return ""

        suggestions = self.get_delegation_suggestions(subtasks)

        if not suggestions and not config.auto_delegate:
            return ""

        section = """
## Subagent Delegation

This project uses claude-harness for optimized AI workflow with subagent delegation
to preserve main context.

### Delegation Guidelines

**When to Delegate (use Task tool):**
- Exploration tasks: File discovery, codebase analysis
- Test writing: Unit tests, E2E tests, integration tests
- Documentation: READMEs, API docs, code comments
- Code review: Security audits, performance analysis

**Keep in Main Agent:**
- Core feature implementation
- Complex integration decisions
- User interaction and clarification
- Final validation and commits

"""

        if suggestions:
            section += f"### Current Feature: {feature_name} ({feature_id})\n\n"
            section += "**Suggested Delegations:**\n\n"

            for subtask, rule in suggestions:
                savings = self.estimate_savings(subtask, rule)
                section += f"- **{subtask}**\n"
                section += f"  - Type: `{rule.subagent_type}` subagent\n"
                section += f"  - Est. savings: ~{savings:,} tokens\n"
                section += f"  - Constraints: {', '.join(rule.constraints[:2])}\n\n"

            total_savings = sum(
                self.estimate_savings(s, r) for s, r in suggestions
            )
            section += f"**Total estimated savings:** ~{total_savings:,} tokens\n\n"

        section += """### Delegation Prompt Template

When delegating via Task tool, use this structure:

```
Feature: [feature_name] (ID: [feature_id])
Subtask: [subtask_name]

Context:
- [relevant context]

Task: [detailed description]

Constraints:
- Keep summary under 500 words
- Report absolute file paths
- Include line numbers when relevant

Output: YAML summary with accomplishments, files, decisions, issues, next steps
```
"""
        return section

    # --- Tracking ---

    def track_delegation(
        self,
        feature_id: str,
        subtask_name: str,
        subagent_type: str,
    ) -> DelegationResult:
        """Track that a task was delegated."""
        result = DelegationResult(
            feature_id=feature_id,
            subtask_name=subtask_name,
            subagent_type=subagent_type,
            status="pending",
            estimated_tokens_saved=self.TOKEN_ESTIMATES.get(subagent_type, 15000)
            - self.SUMMARY_ESTIMATES.get(subagent_type, 4000),
        )

        data = self._load_delegation_tracking()
        data["delegations"].append(result.to_dict())
        self._save_delegation_tracking(data)

        return result

    def complete_delegation(
        self,
        feature_id: str,
        subtask_name: str,
        summary: str,
        files_created: Optional[List[str]] = None,
        files_modified: Optional[List[str]] = None,
    ):
        """Mark a delegation as completed with results."""
        data = self._load_delegation_tracking()

        for delegation in data["delegations"]:
            if (
                delegation["feature_id"] == feature_id
                and delegation["subtask_name"] == subtask_name
                and delegation["status"] == "pending"
            ):
                delegation["status"] = "completed"
                delegation["summary"] = summary
                delegation["files_created"] = files_created or []
                delegation["files_modified"] = files_modified or []
                delegation["completed_at"] = datetime.now(timezone.utc).isoformat()
                break

        self._save_delegation_tracking(data)

    def get_delegation_metrics(self) -> dict:
        """Get delegation metrics for reporting."""
        data = self._load_delegation_tracking()
        delegations = data.get("delegations", [])

        total = len(delegations)
        completed = sum(1 for d in delegations if d.get("status") == "completed")
        pending = sum(1 for d in delegations if d.get("status") == "pending")
        failed = sum(1 for d in delegations if d.get("status") == "failed")

        total_savings = sum(
            d.get("estimated_tokens_saved", 0)
            for d in delegations
            if d.get("status") == "completed"
        )

        return {
            "total_delegations": total,
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "estimated_tokens_saved": total_savings,
            "by_type": self._count_by_type(delegations),
        }

    def _count_by_type(self, delegations: List[dict]) -> dict:
        """Count delegations by subagent type."""
        counts = {}
        for d in delegations:
            subagent_type = d.get("subagent_type", "general")
            counts[subagent_type] = counts.get(subagent_type, 0) + 1
        return counts

    # --- Display Methods ---

    def show_status(self):
        """Display delegation status."""
        config = self._load_config()

        console.print()
        status = "[green]Enabled[/green]" if config.enabled else "[red]Disabled[/red]"
        auto = "[green]Yes[/green]" if config.auto_delegate else "[dim]No[/dim]"

        console.print(
            Panel.fit(
                f"[bold blue]Subagent Delegation[/bold blue]\n"
                f"Status: {status}\n"
                f"Auto-delegate: {auto}\n"
                f"Parallel limit: {config.parallel_limit}\n"
                f"Summary max words: {config.summary_max_words}",
                border_style="blue",
            )
        )

        # Show metrics if any delegations exist
        metrics = self.get_delegation_metrics()
        if metrics["total_delegations"] > 0:
            console.print()
            console.print("[bold]Delegation Metrics:[/bold]")
            console.print(f"  Total delegations: {metrics['total_delegations']}")
            console.print(f"  Completed: {metrics['completed']}")
            console.print(f"  Success rate: {metrics['success_rate']:.0%}")
            console.print(
                f"  Est. tokens saved: {metrics['estimated_tokens_saved']:,}"
            )

    def show_rules(self):
        """Display delegation rules as a table."""
        config = self._load_config()

        table = Table(title="Delegation Rules")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Priority", justify="center")
        table.add_column("Enabled", justify="center")
        table.add_column("Patterns")

        for rule in config.rules:
            enabled = "[green]Yes[/green]" if rule.enabled else "[red]No[/red]"
            patterns = ", ".join(rule.task_patterns[:3])
            if len(rule.task_patterns) > 3:
                patterns += f" (+{len(rule.task_patterns) - 3})"

            table.add_row(
                rule.name,
                rule.subagent_type,
                str(rule.priority),
                enabled,
                patterns,
            )

        console.print(table)


def get_delegation_manager(project_path: str = ".") -> DelegationManager:
    """Get a delegation manager instance."""
    return DelegationManager(project_path)
