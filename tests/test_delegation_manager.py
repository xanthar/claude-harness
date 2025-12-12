"""Tests for delegation_manager.py - Subagent delegation management."""

import json
import pytest
from pathlib import Path

from claude_harness.delegation_manager import (
    DelegationRule,
    DelegationConfig,
    DelegationResult,
    DelegationManager,
    get_delegation_manager,
)


class TestDelegationRule:
    """Tests for DelegationRule dataclass."""

    def test_rule_creation_defaults(self):
        """Test creating a rule with defaults."""
        rule = DelegationRule(
            name="test",
            task_patterns=["test.*"],
            subagent_type="test",
        )
        assert rule.name == "test"
        assert rule.task_patterns == ["test.*"]
        assert rule.subagent_type == "test"
        assert rule.priority == 5
        assert rule.enabled is True
        assert rule.constraints == []

    def test_rule_to_dict(self):
        """Test converting rule to dict."""
        rule = DelegationRule(
            name="explore",
            task_patterns=["explore.*", "find.*"],
            subagent_type="explore",
            priority=10,
            constraints=["Read-only"],
        )
        d = rule.to_dict()
        assert d["name"] == "explore"
        assert d["task_patterns"] == ["explore.*", "find.*"]
        assert d["subagent_type"] == "explore"
        assert d["priority"] == 10
        assert d["constraints"] == ["Read-only"]

    def test_rule_from_dict(self):
        """Test creating rule from dict."""
        data = {
            "name": "testing",
            "task_patterns": ["test.*"],
            "subagent_type": "test",
            "priority": 8,
            "enabled": True,
            "constraints": ["Mock services"],
        }
        rule = DelegationRule.from_dict(data)
        assert rule.name == "testing"
        assert rule.priority == 8
        assert rule.constraints == ["Mock services"]

    def test_rule_matches_regex(self):
        """Test rule matching with regex patterns."""
        rule = DelegationRule(
            name="test",
            task_patterns=[r"test.*", r"write.*test"],
            subagent_type="test",
        )
        assert rule.matches("test login flow") is True
        assert rule.matches("write unit test") is True
        assert rule.matches("Test Authentication") is True  # Case insensitive
        assert rule.matches("implement feature") is False

    def test_rule_matches_disabled(self):
        """Test that disabled rules don't match."""
        rule = DelegationRule(
            name="test",
            task_patterns=["test.*"],
            subagent_type="test",
            enabled=False,
        )
        assert rule.matches("test login") is False

    def test_rule_matches_substring_fallback(self):
        """Test substring matching when regex is invalid."""
        rule = DelegationRule(
            name="test",
            task_patterns=["[invalid regex", "explore"],  # Invalid regex
            subagent_type="explore",
        )
        assert rule.matches("explore codebase") is True


class TestDelegationConfig:
    """Tests for DelegationConfig dataclass."""

    def test_config_defaults(self):
        """Test config with default values."""
        config = DelegationConfig()
        assert config.enabled is False
        assert config.auto_delegate is False
        assert config.parallel_limit == 3
        assert config.summary_max_words == 500
        assert config.context_threshold == 0.5
        assert len(config.rules) > 0  # Default rules

    def test_config_default_rules(self):
        """Test that default rules are created."""
        config = DelegationConfig()
        rule_names = [r.name for r in config.rules]
        assert "exploration" in rule_names
        assert "testing" in rule_names
        assert "documentation" in rule_names
        assert "review" in rule_names

    def test_config_to_dict(self):
        """Test converting config to dict."""
        config = DelegationConfig(enabled=True, parallel_limit=5)
        d = config.to_dict()
        assert d["enabled"] is True
        assert d["parallel_limit"] == 5
        assert "rules" in d
        assert len(d["rules"]) > 0

    def test_config_from_dict(self):
        """Test creating config from dict."""
        data = {
            "enabled": True,
            "auto_delegate": True,
            "parallel_limit": 2,
            "rules": [
                {
                    "name": "custom",
                    "task_patterns": ["custom.*"],
                    "subagent_type": "general",
                }
            ],
        }
        config = DelegationConfig.from_dict(data)
        assert config.enabled is True
        assert config.auto_delegate is True
        assert config.parallel_limit == 2
        assert len(config.rules) == 1
        assert config.rules[0].name == "custom"


class TestDelegationResult:
    """Tests for DelegationResult dataclass."""

    def test_result_creation(self):
        """Test creating a delegation result."""
        result = DelegationResult(
            feature_id="F-001",
            subtask_name="Write tests",
            subagent_type="test",
            status="pending",
        )
        assert result.feature_id == "F-001"
        assert result.subtask_name == "Write tests"
        assert result.status == "pending"
        assert result.delegated_at != ""

    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = DelegationResult(
            feature_id="F-001",
            subtask_name="Explore auth",
            subagent_type="explore",
            status="completed",
            summary="Found 3 auth files",
            files_created=["docs/auth.md"],
            estimated_tokens_saved=20000,
        )
        d = result.to_dict()
        assert d["feature_id"] == "F-001"
        assert d["status"] == "completed"
        assert d["summary"] == "Found 3 auth files"
        assert d["estimated_tokens_saved"] == 20000

    def test_result_from_dict(self):
        """Test creating result from dict."""
        data = {
            "feature_id": "F-002",
            "subtask_name": "Review security",
            "subagent_type": "review",
            "status": "completed",
            "summary": "2 issues found",
        }
        result = DelegationResult.from_dict(data)
        assert result.feature_id == "F-002"
        assert result.status == "completed"


class TestDelegationManager:
    """Tests for DelegationManager class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with harness initialized."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {
            "project_name": "test-project",
            "delegation": {
                "enabled": True,
                "auto_delegate": False,
                "parallel_limit": 3,
            },
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        return tmp_path

    def test_init(self, temp_project):
        """Test manager initialization."""
        dm = DelegationManager(str(temp_project))
        assert dm.project_path == temp_project

    def test_is_enabled(self, temp_project):
        """Test checking if delegation is enabled."""
        dm = DelegationManager(str(temp_project))
        assert dm.is_enabled() is True

    def test_enable_disable(self, temp_project):
        """Test enabling and disabling delegation."""
        dm = DelegationManager(str(temp_project))

        dm.disable()
        assert dm.is_enabled() is False

        dm.enable()
        assert dm.is_enabled() is True

    def test_get_rules(self, temp_project):
        """Test getting delegation rules."""
        dm = DelegationManager(str(temp_project))
        rules = dm.get_rules()
        assert len(rules) > 0
        assert any(r.name == "exploration" for r in rules)

    def test_add_rule(self, temp_project):
        """Test adding a custom rule."""
        dm = DelegationManager(str(temp_project))
        initial_count = len(dm.get_rules())

        rule = DelegationRule(
            name="custom-test",
            task_patterns=["custom.*"],
            subagent_type="general",
        )
        dm.add_rule(rule)

        assert len(dm.get_rules()) == initial_count + 1

    def test_add_rule_duplicate_name(self, temp_project):
        """Test that adding duplicate rule name raises error."""
        dm = DelegationManager(str(temp_project))

        rule = DelegationRule(
            name="exploration",  # Already exists in defaults
            task_patterns=["new.*"],
            subagent_type="explore",
        )

        with pytest.raises(ValueError):
            dm.add_rule(rule)

    def test_remove_rule(self, temp_project):
        """Test removing a rule."""
        dm = DelegationManager(str(temp_project))

        # Add a rule first
        rule = DelegationRule(
            name="to-remove",
            task_patterns=["remove.*"],
            subagent_type="general",
        )
        dm.add_rule(rule)

        # Remove it
        result = dm.remove_rule("to-remove")
        assert result is True

        # Try to remove again
        result = dm.remove_rule("to-remove")
        assert result is False

    def test_enable_disable_rule(self, temp_project):
        """Test enabling and disabling a specific rule."""
        dm = DelegationManager(str(temp_project))

        # Disable exploration rule
        result = dm.disable_rule("exploration")
        assert result is True

        # Verify it's disabled
        rules = dm.get_rules()
        exploration = next(r for r in rules if r.name == "exploration")
        assert exploration.enabled is False

        # Enable it
        result = dm.enable_rule("exploration")
        assert result is True

        rules = dm.get_rules()
        exploration = next(r for r in rules if r.name == "exploration")
        assert exploration.enabled is True

    def test_should_delegate(self, temp_project):
        """Test checking if a subtask should be delegated."""
        dm = DelegationManager(str(temp_project))

        # Should match exploration rule
        rule = dm.should_delegate("explore authentication patterns")
        assert rule is not None
        assert rule.subagent_type == "explore"

        # Should match testing rule
        rule = dm.should_delegate("write unit tests for login")
        assert rule is not None
        assert rule.subagent_type == "test"

        # Should not match any rule
        rule = dm.should_delegate("implement core feature")
        assert rule is None

    def test_get_delegation_suggestions(self, temp_project):
        """Test getting delegation suggestions for subtasks."""
        dm = DelegationManager(str(temp_project))

        subtasks = [
            "explore codebase structure",
            "implement login API",
            "write unit tests",
            "document API endpoints",
        ]

        suggestions = dm.get_delegation_suggestions(subtasks)

        # Should suggest delegation for 3 of 4 subtasks
        assert len(suggestions) == 3
        suggested_subtasks = [s[0] for s in suggestions]
        assert "explore codebase structure" in suggested_subtasks
        assert "write unit tests" in suggested_subtasks
        assert "document API endpoints" in suggested_subtasks
        assert "implement login API" not in suggested_subtasks

    def test_estimate_savings(self, temp_project):
        """Test estimating token savings."""
        dm = DelegationManager(str(temp_project))

        rule = DelegationRule(
            name="test",
            task_patterns=["test.*"],
            subagent_type="explore",
        )

        savings = dm.estimate_savings("test task", rule)
        assert savings > 0
        assert savings == 25000 - 3000  # explore type estimates

    def test_generate_delegation_prompt(self, temp_project):
        """Test generating a delegation prompt."""
        dm = DelegationManager(str(temp_project))

        rule = DelegationRule(
            name="test",
            task_patterns=["test.*"],
            subagent_type="test",
            constraints=["Use pytest"],
        )

        prompt = dm.generate_delegation_prompt(
            subtask_name="write unit tests for auth",
            feature_name="User Authentication",
            feature_id="F-001",
            rule=rule,
            relevant_files=["auth/login.py"],
        )

        assert "write unit tests for auth" in prompt
        assert "F-001" in prompt
        assert "User Authentication" in prompt
        assert "auth/login.py" in prompt
        assert "Use pytest" in prompt

    def test_generate_claude_md_section(self, temp_project):
        """Test generating CLAUDE.md delegation section."""
        dm = DelegationManager(str(temp_project))

        subtasks = [
            "explore existing patterns",
            "implement feature",
            "write tests",
        ]

        section = dm.generate_claude_md_section(
            feature_name="Test Feature",
            feature_id="F-001",
            subtasks=subtasks,
        )

        assert "Subagent Delegation" in section
        assert "explore existing patterns" in section
        assert "write tests" in section
        assert "Total estimated savings" in section

    def test_track_delegation(self, temp_project):
        """Test tracking a delegation."""
        dm = DelegationManager(str(temp_project))

        result = dm.track_delegation(
            feature_id="F-001",
            subtask_name="explore auth",
            subagent_type="explore",
        )

        assert result.feature_id == "F-001"
        assert result.status == "pending"

    def test_complete_delegation(self, temp_project):
        """Test completing a tracked delegation."""
        dm = DelegationManager(str(temp_project))

        # Track first
        dm.track_delegation(
            feature_id="F-001",
            subtask_name="explore auth",
            subagent_type="explore",
        )

        # Complete it
        dm.complete_delegation(
            feature_id="F-001",
            subtask_name="explore auth",
            summary="Found 3 auth files",
            files_created=["docs/auth.md"],
        )

        # Check metrics
        metrics = dm.get_delegation_metrics()
        assert metrics["completed"] >= 1

    def test_get_delegation_metrics(self, temp_project):
        """Test getting delegation metrics."""
        dm = DelegationManager(str(temp_project))

        # Initially no delegations
        metrics = dm.get_delegation_metrics()
        assert metrics["total_delegations"] == 0

        # Track some delegations
        dm.track_delegation("F-001", "task1", "explore")
        dm.track_delegation("F-001", "task2", "test")
        dm.complete_delegation("F-001", "task1", "Done")

        metrics = dm.get_delegation_metrics()
        assert metrics["total_delegations"] == 2
        assert metrics["completed"] == 1
        assert metrics["pending"] == 1

    def test_auto_delegate_setting(self, temp_project):
        """Test auto-delegate setting."""
        dm = DelegationManager(str(temp_project))

        dm.set_auto_delegate(True)
        assert dm.get_config().auto_delegate is True

        dm.set_auto_delegate(False)
        assert dm.get_config().auto_delegate is False


class TestGetDelegationManager:
    """Tests for get_delegation_manager function."""

    def test_get_delegation_manager(self, tmp_path):
        """Test getting a delegation manager instance."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"project_name": "test"}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        import os
        os.chdir(tmp_path)

        dm = get_delegation_manager()
        assert isinstance(dm, DelegationManager)


class TestDelegationManagerEdgeCases:
    """Edge case tests for DelegationManager."""

    def test_no_config_file(self, tmp_path):
        """Test manager works without config file."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        dm = DelegationManager(str(tmp_path))
        assert dm.is_enabled() is False  # Default is disabled
        assert len(dm.get_rules()) > 0  # Default rules exist

    def test_empty_subtasks(self, tmp_path):
        """Test suggestions with empty subtask list."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        dm = DelegationManager(str(tmp_path))
        suggestions = dm.get_delegation_suggestions([])
        assert suggestions == []

    def test_no_matching_rules(self, tmp_path):
        """Test when no rules match."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        dm = DelegationManager(str(tmp_path))
        dm.enable()

        subtasks = [
            "implement core logic",
            "refactor database layer",
            "fix bug in auth",
        ]

        suggestions = dm.get_delegation_suggestions(subtasks)
        assert len(suggestions) == 0

    def test_priority_ordering(self, tmp_path):
        """Test that higher priority rules are selected."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {
            "delegation": {
                "enabled": True,
                "rules": [
                    {
                        "name": "low-priority",
                        "task_patterns": ["test.*"],
                        "subagent_type": "general",
                        "priority": 1,
                    },
                    {
                        "name": "high-priority",
                        "task_patterns": ["test.*"],
                        "subagent_type": "test",
                        "priority": 10,
                    },
                ],
            }
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        dm = DelegationManager(str(tmp_path))
        rule = dm.should_delegate("test something")

        assert rule is not None
        assert rule.name == "high-priority"
        assert rule.priority == 10
