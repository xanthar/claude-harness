"""Tests for orchestration_engine.py - Core orchestration state machine."""

import json
import time
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from claude_harness.orchestration_engine import (
    OrchestrationState,
    OrchestrationConfig,
    DelegationQueueItem,
    OrchestrationStatus,
    OrchestrationEngine,
    get_orchestration_engine,
)


class TestOrchestrationState:
    """Tests for OrchestrationState enum."""

    def test_all_states_exist(self):
        """Test all expected states are defined."""
        assert OrchestrationState.IDLE.value == "idle"
        assert OrchestrationState.EVALUATING.value == "evaluating"
        assert OrchestrationState.DELEGATING.value == "delegating"
        assert OrchestrationState.WAITING.value == "waiting"
        assert OrchestrationState.INTEGRATING.value == "integrating"

    def test_state_count(self):
        """Test expected number of states."""
        assert len(OrchestrationState) == 5


class TestOrchestrationConfig:
    """Tests for OrchestrationConfig dataclass."""

    def test_config_defaults(self):
        """Test config with default values."""
        config = OrchestrationConfig()
        assert config.max_delegations_per_feature == 5
        assert config.max_delegations_per_session == 20
        assert config.delegation_cooldown_seconds == 60
        assert config.max_parallel_delegations == 3
        assert config.context_threshold == 0.5
        assert config.min_subtasks_for_delegation == 1
        assert config.auto_delegate is False
        assert config.require_user_confirmation is True
        assert config.priority_threshold == 5

    def test_config_custom_values(self):
        """Test config with custom values."""
        config = OrchestrationConfig(
            max_delegations_per_feature=10,
            max_delegations_per_session=50,
            delegation_cooldown_seconds=30,
            context_threshold=0.7,
        )
        assert config.max_delegations_per_feature == 10
        assert config.max_delegations_per_session == 50
        assert config.delegation_cooldown_seconds == 30
        assert config.context_threshold == 0.7

    def test_config_to_dict(self):
        """Test converting config to dict."""
        config = OrchestrationConfig(
            max_delegations_per_feature=8,
            auto_delegate=True,
        )
        d = config.to_dict()
        assert d["max_delegations_per_feature"] == 8
        assert d["auto_delegate"] is True
        assert "context_threshold" in d

    def test_config_from_dict(self):
        """Test creating config from dict."""
        data = {
            "max_delegations_per_feature": 3,
            "max_parallel_delegations": 5,
            "context_threshold": 0.8,
        }
        config = OrchestrationConfig.from_dict(data)
        assert config.max_delegations_per_feature == 3
        assert config.max_parallel_delegations == 5
        assert config.context_threshold == 0.8

    def test_config_from_dict_missing_keys(self):
        """Test creating config from partial dict uses defaults."""
        data = {"max_delegations_per_feature": 7}
        config = OrchestrationConfig.from_dict(data)
        assert config.max_delegations_per_feature == 7
        assert config.max_delegations_per_session == 20  # Default
        assert config.delegation_cooldown_seconds == 60  # Default


class TestDelegationQueueItem:
    """Tests for DelegationQueueItem dataclass."""

    def test_queue_item_creation(self):
        """Test creating a queue item."""
        item = DelegationQueueItem(
            id="",
            feature_id="F-001",
            feature_name="Test Feature",
            subtask_name="Write unit tests",
            subtask_index=0,
            rule_name="testing",
            subagent_type="test",
            priority=8,
            prompt="Test prompt",
        )
        assert item.feature_id == "F-001"
        assert item.subtask_name == "Write unit tests"
        assert item.status == "queued"
        assert item.id != ""  # Auto-generated
        assert item.created_at != ""

    def test_queue_item_to_dict(self):
        """Test converting queue item to dict."""
        item = DelegationQueueItem(
            id="abc123",
            feature_id="F-001",
            feature_name="Test Feature",
            subtask_name="Explore codebase",
            subtask_index=1,
            rule_name="exploration",
            subagent_type="explore",
            priority=10,
            prompt="Explore...",
            estimated_tokens_saved=22000,
        )
        d = item.to_dict()
        assert d["id"] == "abc123"
        assert d["feature_id"] == "F-001"
        assert d["subtask_name"] == "Explore codebase"
        assert d["estimated_tokens_saved"] == 22000

    def test_queue_item_from_dict(self):
        """Test creating queue item from dict."""
        data = {
            "id": "test-id",
            "feature_id": "F-002",
            "subtask_name": "Document API",
            "subtask_index": 2,
            "rule_name": "documentation",
            "subagent_type": "document",
            "priority": 6,
            "prompt": "Document...",
            "status": "active",
        }
        item = DelegationQueueItem.from_dict(data)
        assert item.id == "test-id"
        assert item.feature_id == "F-002"
        assert item.status == "active"

    def test_queue_item_status_transitions(self):
        """Test that status can be changed."""
        item = DelegationQueueItem(
            id="",
            feature_id="F-001",
            feature_name="Test",
            subtask_name="Test task",
            subtask_index=0,
            rule_name="test",
            subagent_type="test",
            priority=5,
            prompt="Test",
        )
        assert item.status == "queued"
        item.status = "active"
        assert item.status == "active"
        item.status = "completed"
        assert item.status == "completed"


class TestOrchestrationStatus:
    """Tests for OrchestrationStatus dataclass."""

    def test_status_defaults(self):
        """Test status with default values."""
        status = OrchestrationStatus()
        assert status.state == OrchestrationState.IDLE
        assert status.total_delegations == 0
        assert status.completed_delegations == 0
        assert status.failed_delegations == 0
        assert status.session_start != ""

    def test_status_to_dict(self):
        """Test converting status to dict."""
        status = OrchestrationStatus(
            state=OrchestrationState.WAITING,
            total_delegations=5,
            completed_delegations=3,
            total_tokens_saved=50000,
        )
        d = status.to_dict()
        assert d["state"] == "waiting"
        assert d["total_delegations"] == 5
        assert d["completed_delegations"] == 3
        assert d["total_tokens_saved"] == 50000

    def test_status_from_dict(self):
        """Test creating status from dict."""
        data = {
            "state": "delegating",
            "total_delegations": 10,
            "completed_delegations": 8,
            "failed_delegations": 2,
            "total_tokens_saved": 100000,
        }
        status = OrchestrationStatus.from_dict(data)
        assert status.state == OrchestrationState.DELEGATING
        assert status.total_delegations == 10
        assert status.completed_delegations == 8

    def test_status_invalid_state_defaults_to_idle(self):
        """Test that invalid state string defaults to IDLE."""
        data = {"state": "invalid_state"}
        status = OrchestrationStatus.from_dict(data)
        assert status.state == OrchestrationState.IDLE

    def test_status_with_queue_items(self):
        """Test status with queued and active items."""
        item = DelegationQueueItem(
            id="q1",
            feature_id="F-001",
            feature_name="Test",
            subtask_name="Task 1",
            subtask_index=0,
            rule_name="test",
            subagent_type="test",
            priority=5,
            prompt="Test",
        )
        status = OrchestrationStatus(
            queued_delegations=[item],
        )
        d = status.to_dict()
        assert len(d["queued_delegations"]) == 1
        assert d["queued_delegations"][0]["id"] == "q1"


class TestOrchestrationEngine:
    """Tests for OrchestrationEngine class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with harness initialized."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        # Create config with delegation enabled
        config = {
            "project_name": "test-project",
            "delegation": {
                "enabled": True,
                "auto_delegate": False,
                "parallel_limit": 3,
            },
            "orchestration": {
                "max_delegations_per_feature": 5,
                "max_delegations_per_session": 20,
                "delegation_cooldown_seconds": 60,
                "context_threshold": 0.5,
            },
            "context_tracking": {
                "enabled": True,
                "budget": 200000,
            },
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        # Create features file with in-progress feature
        features = {
            "current_phase": "Phase 1",
            "features": [
                {
                    "id": "F-001",
                    "name": "Test Feature",
                    "status": "in_progress",
                    "priority": 1,
                    "subtasks": [
                        {"name": "Explore codebase structure", "done": False},
                        {"name": "Implement core logic", "done": False},
                        {"name": "Write unit tests", "done": False},
                        {"name": "Document API", "done": False},
                    ],
                    "tests_passing": False,
                    "e2e_validated": False,
                }
            ],
            "completed": [],
            "blocked": [],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        # Create context metrics showing high usage
        metrics = {
            "session_start": datetime.now(timezone.utc).isoformat(),
            "estimated_total_tokens": 120000,
            "context_budget": 200000,
            "files_read": ["file1.py", "file2.py"],
            "commands_executed": 10,
        }
        with open(harness_dir / "context_metrics.json", "w") as f:
            json.dump(metrics, f)

        return tmp_path

    def test_init(self, temp_project):
        """Test engine initialization."""
        engine = OrchestrationEngine(str(temp_project))
        assert engine.project_path == temp_project

    def test_get_config(self, temp_project):
        """Test getting configuration."""
        engine = OrchestrationEngine(str(temp_project))
        config = engine.get_config()
        assert config.max_delegations_per_feature == 5
        assert config.max_delegations_per_session == 20

    def test_update_config(self, temp_project):
        """Test updating configuration."""
        engine = OrchestrationEngine(str(temp_project))
        engine.update_config(max_delegations_per_feature=10)
        config = engine.get_config()
        assert config.max_delegations_per_feature == 10

    def test_can_delegate_basic(self, temp_project):
        """Test basic can_delegate check."""
        engine = OrchestrationEngine(str(temp_project))
        result = engine.can_delegate()
        assert "allowed" in result
        assert "reasons" in result
        assert "session_delegations" in result

    def test_can_delegate_session_limit(self, temp_project):
        """Test can_delegate respects session limit."""
        engine = OrchestrationEngine(str(temp_project))

        # Set high delegation count
        status = engine._load_status()
        status.total_delegations = 20
        engine._save_status()

        result = engine.can_delegate()
        assert result["allowed"] is False
        assert any("Session limit" in r for r in result["reasons"])

    def test_can_delegate_feature_limit(self, temp_project):
        """Test can_delegate respects feature limit."""
        engine = OrchestrationEngine(str(temp_project))

        # Set high feature delegation count
        status = engine._load_status()
        status.feature_delegation_counts["F-001"] = 5
        engine._save_status()

        result = engine.can_delegate(feature_id="F-001")
        assert result["allowed"] is False
        assert any("Feature limit" in r for r in result["reasons"])

    def test_can_delegate_parallel_limit(self, temp_project):
        """Test can_delegate respects parallel limit."""
        engine = OrchestrationEngine(str(temp_project))

        # Add active delegations
        status = engine._load_status()
        for i in range(3):
            item = DelegationQueueItem(
                id=f"active-{i}",
                feature_id="F-001",
                feature_name="Test",
                subtask_name=f"Task {i}",
                subtask_index=i,
                rule_name="test",
                subagent_type="test",
                priority=5,
                prompt="Test",
                status="active",
            )
            status.active_delegations.append(item)
        engine._save_status()

        result = engine.can_delegate()
        assert result["allowed"] is False
        assert any("Parallel limit" in r for r in result["reasons"])

    def test_can_delegate_cooldown(self, temp_project):
        """Test can_delegate respects cooldown."""
        engine = OrchestrationEngine(str(temp_project))

        # Set recent delegation time
        status = engine._load_status()
        status.last_delegation_at = datetime.now(timezone.utc).isoformat()
        engine._save_status()

        result = engine.can_delegate()
        assert result["allowed"] is False
        assert any("Cooldown" in r for r in result["reasons"])

    def test_evaluate_no_feature(self, temp_project):
        """Test evaluate when no feature is in progress."""
        engine = OrchestrationEngine(str(temp_project))

        # Remove in-progress feature
        features_file = temp_project / ".claude-harness" / "features.json"
        with open(features_file) as f:
            data = json.load(f)
        data["features"][0]["status"] = "pending"
        with open(features_file, "w") as f:
            json.dump(data, f)

        result = engine.evaluate()
        assert result["should_delegate"] is False
        assert any("No feature" in r for r in result["reasons"])

    def test_evaluate_low_context(self, temp_project):
        """Test evaluate when context is below threshold."""
        engine = OrchestrationEngine(str(temp_project))

        # Set low context usage
        metrics_file = temp_project / ".claude-harness" / "context_metrics.json"
        with open(metrics_file) as f:
            data = json.load(f)
        data["estimated_total_tokens"] = 50000  # 25%
        with open(metrics_file, "w") as f:
            json.dump(data, f)

        result = engine.evaluate()
        assert result["should_delegate"] is False
        assert any("below threshold" in r for r in result["reasons"])

    def test_evaluate_finds_delegatable_subtasks(self, temp_project):
        """Test evaluate finds subtasks matching delegation rules."""
        engine = OrchestrationEngine(str(temp_project))
        result = engine.evaluate()

        # Should find delegatable subtasks (explore, test, document)
        assert len(result["delegatable_subtasks"]) >= 2

    def test_generate_delegation_queue(self, temp_project):
        """Test generating delegation queue."""
        engine = OrchestrationEngine(str(temp_project))
        queue = engine.generate_delegation_queue()

        assert len(queue) > 0
        for item in queue:
            assert item.feature_id == "F-001"
            assert item.prompt != ""
            assert item.status == "queued"

    def test_generate_delegation_queue_respects_limits(self, temp_project):
        """Test queue generation respects parallel limit."""
        engine = OrchestrationEngine(str(temp_project))

        # Add 2 active delegations (limit is 3)
        status = engine._load_status()
        for i in range(2):
            item = DelegationQueueItem(
                id=f"active-{i}",
                feature_id="F-001",
                feature_name="Test",
                subtask_name=f"Task {i}",
                subtask_index=i,
                rule_name="test",
                subagent_type="test",
                priority=5,
                prompt="Test",
                status="active",
            )
            status.active_delegations.append(item)
        engine._save_status()

        queue = engine.generate_delegation_queue()
        assert len(queue) <= 1  # Only 1 slot remaining

    def test_start_delegation(self, temp_project):
        """Test starting a delegation."""
        engine = OrchestrationEngine(str(temp_project))

        # Generate queue first
        queue = engine.generate_delegation_queue()
        assert len(queue) > 0

        delegation_id = queue[0].id
        result = engine.start_delegation(delegation_id)

        assert result is not None
        assert result.status == "active"
        assert result.started_at is not None

        # Check moved to active list
        status = engine._load_status()
        assert len(status.active_delegations) == 1
        assert status.total_delegations == 1

    def test_start_delegation_not_found(self, temp_project):
        """Test starting non-existent delegation."""
        engine = OrchestrationEngine(str(temp_project))
        result = engine.start_delegation("nonexistent-id")
        assert result is None

    def test_complete_delegation(self, temp_project):
        """Test completing a delegation."""
        engine = OrchestrationEngine(str(temp_project))

        # Generate and start a delegation
        queue = engine.generate_delegation_queue()
        delegation_id = queue[0].id
        engine.start_delegation(delegation_id)

        # Complete it
        result = engine.complete_delegation(
            delegation_id=delegation_id,
            result_summary="Successfully completed task",
            files_created=["test_file.py"],
            files_modified=["existing.py"],
        )

        assert result is not None
        assert result.status == "completed"
        assert result.result_summary == "Successfully completed task"
        assert result.completed_at is not None

        # Check counters updated
        status = engine._load_status()
        assert status.completed_delegations == 1
        assert status.total_tokens_saved > 0

    def test_fail_delegation(self, temp_project):
        """Test marking a delegation as failed."""
        engine = OrchestrationEngine(str(temp_project))

        # Generate and start a delegation
        queue = engine.generate_delegation_queue()
        delegation_id = queue[0].id
        engine.start_delegation(delegation_id)

        # Fail it
        result = engine.fail_delegation(
            delegation_id=delegation_id,
            error="Subagent encountered error",
        )

        assert result is not None
        assert result.status == "failed"
        assert result.error == "Subagent encountered error"

        # Check counters updated
        status = engine._load_status()
        assert status.failed_delegations == 1

    def test_get_status(self, temp_project):
        """Test getting orchestration status."""
        engine = OrchestrationEngine(str(temp_project))
        status = engine.get_status()

        assert "state" in status
        assert "metrics" in status
        assert "limits" in status
        assert "queued" in status
        assert "active" in status

    def test_get_active_delegations(self, temp_project):
        """Test getting active delegations."""
        engine = OrchestrationEngine(str(temp_project))

        # Initially empty
        active = engine.get_active_delegations()
        assert len(active) == 0

        # Start a delegation
        queue = engine.generate_delegation_queue()
        engine.start_delegation(queue[0].id)

        active = engine.get_active_delegations()
        assert len(active) == 1

    def test_clear_queue(self, temp_project):
        """Test clearing the delegation queue."""
        engine = OrchestrationEngine(str(temp_project))

        # Generate queue
        queue = engine.generate_delegation_queue()
        assert len(queue) > 0

        # Clear it
        engine.clear_queue()
        assert len(engine.get_queue()) == 0

    def test_reset_session(self, temp_project):
        """Test resetting session state."""
        engine = OrchestrationEngine(str(temp_project))

        # Generate and start some delegations
        queue = engine.generate_delegation_queue()
        engine.start_delegation(queue[0].id)

        # Reset
        engine.reset_session()

        status = engine._load_status()
        assert status.total_delegations == 0
        assert len(status.active_delegations) == 0
        assert len(status.queued_delegations) == 0

    def test_state_transitions(self, temp_project):
        """Test state machine transitions."""
        engine = OrchestrationEngine(str(temp_project))

        # Initial state
        status = engine._load_status()
        assert status.state == OrchestrationState.IDLE

        # Evaluate triggers EVALUATING then back to IDLE
        engine.evaluate()
        status = engine._load_status()
        assert status.state == OrchestrationState.IDLE

        # Generate queue triggers DELEGATING then back to IDLE
        engine.generate_delegation_queue()
        status = engine._load_status()
        assert status.state == OrchestrationState.IDLE

        # Start delegation triggers WAITING
        queue = engine.generate_delegation_queue()
        if queue:
            engine.start_delegation(queue[0].id)
            status = engine._load_status()
            assert status.state == OrchestrationState.WAITING


class TestGetOrchestrationEngine:
    """Tests for get_orchestration_engine function."""

    def test_get_orchestration_engine(self, tmp_path):
        """Test getting an orchestration engine instance."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"project_name": "test"}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            engine = get_orchestration_engine()
            assert isinstance(engine, OrchestrationEngine)
        finally:
            os.chdir(original_cwd)


class TestOrchestrationEngineEdgeCases:
    """Edge case tests for OrchestrationEngine."""

    def test_no_config_file(self, tmp_path):
        """Test engine works without config file."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        engine = OrchestrationEngine(str(tmp_path))
        config = engine.get_config()
        assert config.max_delegations_per_feature == 5  # Default

    def test_no_features_file(self, tmp_path):
        """Test evaluate handles missing features file."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"delegation": {"enabled": True}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.evaluate()
        assert result["should_delegate"] is False

    def test_empty_subtasks(self, tmp_path):
        """Test evaluate with feature having no subtasks."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"delegation": {"enabled": True}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        features = {
            "current_phase": "Phase 1",
            "features": [{
                "id": "F-001",
                "name": "Empty Feature",
                "status": "in_progress",
                "subtasks": [],
            }],
            "completed": [],
            "blocked": [],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.evaluate()
        assert result["should_delegate"] is False
        assert any("No pending subtasks" in r for r in result["reasons"])

    def test_all_subtasks_done(self, tmp_path):
        """Test evaluate when all subtasks are completed."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"delegation": {"enabled": True}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        features = {
            "current_phase": "Phase 1",
            "features": [{
                "id": "F-001",
                "name": "Completed Feature",
                "status": "in_progress",
                "subtasks": [
                    {"name": "Task 1", "done": True},
                    {"name": "Task 2", "done": True},
                ],
            }],
            "completed": [],
            "blocked": [],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.evaluate()
        assert result["should_delegate"] is False
        assert any("No pending subtasks" in r for r in result["reasons"])

    def test_delegation_disabled(self, tmp_path):
        """Test can_delegate when delegation is disabled."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"delegation": {"enabled": False}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.can_delegate()
        assert result["allowed"] is False
        assert any("disabled" in r for r in result["reasons"])

    def test_no_matching_rules(self, tmp_path):
        """Test evaluate when no subtasks match delegation rules."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {
            "delegation": {"enabled": True},
            "context_tracking": {"enabled": True, "budget": 200000},
        }
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        features = {
            "current_phase": "Phase 1",
            "features": [{
                "id": "F-001",
                "name": "Feature",
                "status": "in_progress",
                "subtasks": [
                    {"name": "Implement core logic", "done": False},
                    {"name": "Refactor database layer", "done": False},
                ],
            }],
            "completed": [],
            "blocked": [],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        metrics = {
            "estimated_total_tokens": 120000,
            "context_budget": 200000,
        }
        with open(harness_dir / "context_metrics.json", "w") as f:
            json.dump(metrics, f)

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.evaluate()
        # Should not find delegatable subtasks
        assert len(result.get("delegatable_subtasks", [])) == 0

    def test_queue_sorted_by_priority(self, tmp_path):
        """Test that delegation queue is sorted by priority."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        config = {"delegation": {"enabled": True}}
        with open(harness_dir / "config.json", "w") as f:
            json.dump(config, f)

        # Subtasks that match different priority rules
        features = {
            "current_phase": "Phase 1",
            "features": [{
                "id": "F-001",
                "name": "Feature",
                "status": "in_progress",
                "subtasks": [
                    {"name": "Document API endpoints", "done": False},  # priority 6
                    {"name": "Explore codebase", "done": False},  # priority 10
                    {"name": "Write unit tests", "done": False},  # priority 8
                ],
            }],
            "completed": [],
            "blocked": [],
        }
        with open(harness_dir / "features.json", "w") as f:
            json.dump(features, f)

        engine = OrchestrationEngine(str(tmp_path))
        queue = engine.generate_delegation_queue()

        if len(queue) >= 2:
            # Queue should be sorted highest priority first
            for i in range(len(queue) - 1):
                assert queue[i].priority >= queue[i + 1].priority

    def test_complete_delegation_not_found(self, tmp_path):
        """Test completing non-existent delegation."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.complete_delegation(
            delegation_id="nonexistent",
            result_summary="Summary",
        )
        assert result is None

    def test_fail_delegation_not_found(self, tmp_path):
        """Test failing non-existent delegation."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        engine = OrchestrationEngine(str(tmp_path))
        result = engine.fail_delegation(
            delegation_id="nonexistent",
            error="Error",
        )
        assert result is None

    def test_history_limit(self, tmp_path):
        """Test that completed delegation history is limited."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        engine = OrchestrationEngine(str(tmp_path))
        status = engine._load_status()

        # Add more than 20 items to history
        for i in range(25):
            item = DelegationQueueItem(
                id=f"hist-{i}",
                feature_id="F-001",
                feature_name="Test",
                subtask_name=f"Task {i}",
                subtask_index=i,
                rule_name="test",
                subagent_type="test",
                priority=5,
                prompt="Test",
                status="completed",
            )
            status.completed_delegations_history.append(item)

        engine._save_status()

        # Reload and check - to_dict limits to 20
        status = engine._load_status()
        d = status.to_dict()
        assert len(d["completed_delegations_history"]) <= 20
