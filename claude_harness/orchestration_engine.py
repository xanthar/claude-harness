"""Orchestration Engine for Claude Harness.

Core state machine that orchestrates automatic subagent delegation for context
optimization. Coordinates between DelegationManager, ContextTracker, and
FeatureManager to intelligently delegate subtasks when context thresholds
are met.

Key components:
- OrchestrationState: Enum defining state machine states
- OrchestrationConfig: Configuration limits, thresholds, settings
- DelegationQueueItem: Queued delegation with prompt, rule, subtask info
- OrchestrationStatus: Current state, metrics, active delegations
- OrchestrationEngine: Main state machine and coordination logic
"""

import json
import uuid
import time
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


# --- Enums ---


class OrchestrationState(Enum):
    """State machine states for orchestration."""

    IDLE = "idle"                   # No active orchestration
    EVALUATING = "evaluating"       # Checking if delegation should trigger
    DELEGATING = "delegating"       # Creating delegation queue and prompts
    WAITING = "waiting"             # Waiting for subagent completions
    INTEGRATING = "integrating"     # Processing and integrating results


# --- Data Classes ---


@dataclass
class OrchestrationConfig:
    """Configuration for orchestration behavior."""

    # Safety limits
    max_delegations_per_feature: int = 5        # Max delegations for single feature
    max_delegations_per_session: int = 20       # Max total delegations in session
    delegation_cooldown_seconds: int = 60       # Min seconds between delegation cycles
    max_parallel_delegations: int = 3           # Max concurrent active delegations

    # Trigger thresholds
    context_threshold: float = 0.5              # Context usage % to trigger evaluation
    min_subtasks_for_delegation: int = 1        # Min pending subtasks to delegate

    # Behavior settings
    auto_delegate: bool = False                 # Automatically trigger delegation
    require_user_confirmation: bool = True      # Require user to confirm delegation
    priority_threshold: int = 5                 # Min rule priority to consider

    def to_dict(self) -> dict:
        return {
            "max_delegations_per_feature": self.max_delegations_per_feature,
            "max_delegations_per_session": self.max_delegations_per_session,
            "delegation_cooldown_seconds": self.delegation_cooldown_seconds,
            "max_parallel_delegations": self.max_parallel_delegations,
            "context_threshold": self.context_threshold,
            "min_subtasks_for_delegation": self.min_subtasks_for_delegation,
            "auto_delegate": self.auto_delegate,
            "require_user_confirmation": self.require_user_confirmation,
            "priority_threshold": self.priority_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestrationConfig":
        return cls(
            max_delegations_per_feature=data.get("max_delegations_per_feature", 5),
            max_delegations_per_session=data.get("max_delegations_per_session", 20),
            delegation_cooldown_seconds=data.get("delegation_cooldown_seconds", 60),
            max_parallel_delegations=data.get("max_parallel_delegations", 3),
            context_threshold=data.get("context_threshold", 0.5),
            min_subtasks_for_delegation=data.get("min_subtasks_for_delegation", 1),
            auto_delegate=data.get("auto_delegate", False),
            require_user_confirmation=data.get("require_user_confirmation", True),
            priority_threshold=data.get("priority_threshold", 5),
        )


@dataclass
class DelegationQueueItem:
    """A queued delegation with all necessary information."""

    id: str                                     # Unique delegation ID
    feature_id: str                             # Feature being worked on
    feature_name: str                           # Feature name for context
    subtask_name: str                           # Subtask to delegate
    subtask_index: int                          # Index in feature's subtask list
    rule_name: str                              # Matching delegation rule name
    subagent_type: str                          # Type of subagent (explore, test, etc.)
    priority: int                               # Rule priority
    prompt: str                                 # Generated delegation prompt
    estimated_tokens_saved: int = 0             # Estimated context savings
    status: str = "queued"                      # queued, active, completed, failed
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_summary: Optional[str] = None
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "subtask_name": self.subtask_name,
            "subtask_index": self.subtask_index,
            "rule_name": self.rule_name,
            "subagent_type": self.subagent_type,
            "priority": self.priority,
            "prompt": self.prompt,
            "estimated_tokens_saved": self.estimated_tokens_saved,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result_summary": self.result_summary,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DelegationQueueItem":
        return cls(
            id=data.get("id", ""),
            feature_id=data["feature_id"],
            feature_name=data.get("feature_name", ""),
            subtask_name=data["subtask_name"],
            subtask_index=data.get("subtask_index", 0),
            rule_name=data.get("rule_name", ""),
            subagent_type=data.get("subagent_type", "general"),
            priority=data.get("priority", 5),
            prompt=data.get("prompt", ""),
            estimated_tokens_saved=data.get("estimated_tokens_saved", 0),
            status=data.get("status", "queued"),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            result_summary=data.get("result_summary"),
            files_created=data.get("files_created", []),
            files_modified=data.get("files_modified", []),
            error=data.get("error"),
        )


@dataclass
class OrchestrationStatus:
    """Current orchestration state and metrics."""

    state: OrchestrationState = OrchestrationState.IDLE
    last_evaluation_at: Optional[str] = None
    last_delegation_at: Optional[str] = None
    session_start: str = ""

    # Session counters
    total_delegations: int = 0
    completed_delegations: int = 0
    failed_delegations: int = 0
    total_tokens_saved: int = 0

    # Per-feature tracking
    feature_delegation_counts: Dict[str, int] = field(default_factory=dict)

    # Queue state
    queued_delegations: List[DelegationQueueItem] = field(default_factory=list)
    active_delegations: List[DelegationQueueItem] = field(default_factory=list)
    completed_delegations_history: List[DelegationQueueItem] = field(default_factory=list)

    # Evaluation results
    last_evaluation_result: Optional[Dict[str, Any]] = None
    delegation_available: bool = False

    def __post_init__(self):
        if not self.session_start:
            self.session_start = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_evaluation_at": self.last_evaluation_at,
            "last_delegation_at": self.last_delegation_at,
            "session_start": self.session_start,
            "total_delegations": self.total_delegations,
            "completed_delegations": self.completed_delegations,
            "failed_delegations": self.failed_delegations,
            "total_tokens_saved": self.total_tokens_saved,
            "feature_delegation_counts": self.feature_delegation_counts,
            "queued_delegations": [d.to_dict() for d in self.queued_delegations],
            "active_delegations": [d.to_dict() for d in self.active_delegations],
            "completed_delegations_history": [
                d.to_dict() for d in self.completed_delegations_history[-20:]
            ],  # Keep last 20
            "last_evaluation_result": self.last_evaluation_result,
            "delegation_available": self.delegation_available,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrchestrationStatus":
        state_str = data.get("state", "idle")
        try:
            state = OrchestrationState(state_str)
        except ValueError:
            state = OrchestrationState.IDLE

        return cls(
            state=state,
            last_evaluation_at=data.get("last_evaluation_at"),
            last_delegation_at=data.get("last_delegation_at"),
            session_start=data.get("session_start", ""),
            total_delegations=data.get("total_delegations", 0),
            completed_delegations=data.get("completed_delegations", 0),
            failed_delegations=data.get("failed_delegations", 0),
            total_tokens_saved=data.get("total_tokens_saved", 0),
            feature_delegation_counts=data.get("feature_delegation_counts", {}),
            queued_delegations=[
                DelegationQueueItem.from_dict(d)
                for d in data.get("queued_delegations", [])
            ],
            active_delegations=[
                DelegationQueueItem.from_dict(d)
                for d in data.get("active_delegations", [])
            ],
            completed_delegations_history=[
                DelegationQueueItem.from_dict(d)
                for d in data.get("completed_delegations_history", [])
            ],
            last_evaluation_result=data.get("last_evaluation_result"),
            delegation_available=data.get("delegation_available", False),
        )


# --- Orchestration Engine ---


class OrchestrationEngine:
    """Core state machine orchestrating automatic subagent delegation.

    Coordinates between:
    - DelegationManager: Rule matching and prompt generation
    - ContextTracker: Context threshold checking
    - FeatureManager: Subtask access and completion tracking

    State Machine Flow:
    IDLE -> EVALUATING -> DELEGATING -> WAITING -> INTEGRATING -> IDLE
         ^                                                      |
         +------------------------------------------------------+
    """

    def __init__(self, project_path: str):
        """Initialize orchestration engine.

        Args:
            project_path: Path to project root
        """
        self.project_path = Path(project_path).resolve()
        self.harness_dir = self.project_path / ".claude-harness"
        self.state_file = self.harness_dir / "orchestration_state.json"
        self.config_file = self.harness_dir / "config.json"

        self._config: Optional[OrchestrationConfig] = None
        self._status: Optional[OrchestrationStatus] = None

        # Lazy-loaded managers
        self._delegation_manager = None
        self._context_tracker = None
        self._feature_manager = None

    # --- Manager Access (Lazy Loading) ---

    @property
    def delegation_manager(self):
        """Get DelegationManager instance."""
        if self._delegation_manager is None:
            from .delegation_manager import DelegationManager
            self._delegation_manager = DelegationManager(str(self.project_path))
        return self._delegation_manager

    @property
    def context_tracker(self):
        """Get ContextTracker instance."""
        if self._context_tracker is None:
            from .context_tracker import ContextTracker
            self._context_tracker = ContextTracker(str(self.project_path))
        return self._context_tracker

    @property
    def feature_manager(self):
        """Get FeatureManager instance."""
        if self._feature_manager is None:
            from .feature_manager import FeatureManager
            self._feature_manager = FeatureManager(str(self.project_path))
        return self._feature_manager

    # --- State Persistence ---

    def _load_config(self) -> OrchestrationConfig:
        """Load orchestration config from config.json."""
        if self._config is not None:
            return self._config

        if not self.config_file.exists():
            self._config = OrchestrationConfig()
            return self._config

        try:
            with open(self.config_file) as f:
                data = json.load(f)
            orchestration_data = data.get("orchestration", {})
            self._config = OrchestrationConfig.from_dict(orchestration_data)
        except (json.JSONDecodeError, IOError):
            self._config = OrchestrationConfig()

        return self._config

    def _save_config(self):
        """Save orchestration config to config.json."""
        if self._config is None:
            return

        self.harness_dir.mkdir(parents=True, exist_ok=True)

        if self.config_file.exists():
            with open(self.config_file) as f:
                data = json.load(f)
        else:
            data = {}

        data["orchestration"] = self._config.to_dict()

        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_status(self) -> OrchestrationStatus:
        """Load orchestration status from state file."""
        if self._status is not None:
            return self._status

        if not self.state_file.exists():
            self._status = OrchestrationStatus()
            return self._status

        try:
            with open(self.state_file) as f:
                data = json.load(f)
            self._status = OrchestrationStatus.from_dict(data)
        except (json.JSONDecodeError, IOError):
            self._status = OrchestrationStatus()

        return self._status

    def _save_status(self):
        """Save orchestration status to state file."""
        if self._status is None:
            return

        self.harness_dir.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, "w") as f:
            json.dump(self._status.to_dict(), f, indent=2)

    def _set_state(self, new_state: OrchestrationState):
        """Transition to a new state."""
        status = self._load_status()
        status.state = new_state
        self._save_status()

    # --- Configuration Access ---

    def get_config(self) -> OrchestrationConfig:
        """Get current orchestration configuration."""
        return self._load_config()

    def update_config(self, **kwargs):
        """Update configuration settings.

        Args:
            **kwargs: Config fields to update
        """
        config = self._load_config()

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self._save_config()

    # --- Safety Guards ---

    def can_delegate(self, feature_id: Optional[str] = None) -> Dict[str, Any]:
        """Check all safety guards before delegation.

        Args:
            feature_id: Optional feature to check limits for

        Returns:
            Dict with 'allowed' bool and 'reasons' list of blocking reasons
        """
        config = self._load_config()
        status = self._load_status()
        reasons = []

        # Check if delegation is enabled
        if not self.delegation_manager.is_enabled():
            reasons.append("Delegation is disabled")

        # Check session limit
        if status.total_delegations >= config.max_delegations_per_session:
            reasons.append(
                f"Session limit reached ({status.total_delegations}/"
                f"{config.max_delegations_per_session})"
            )

        # Check feature limit
        if feature_id:
            feature_count = status.feature_delegation_counts.get(feature_id, 0)
            if feature_count >= config.max_delegations_per_feature:
                reasons.append(
                    f"Feature limit reached ({feature_count}/"
                    f"{config.max_delegations_per_feature})"
                )

        # Check parallel limit
        active_count = len(status.active_delegations)
        if active_count >= config.max_parallel_delegations:
            reasons.append(
                f"Parallel limit reached ({active_count}/"
                f"{config.max_parallel_delegations})"
            )

        # Check cooldown
        if status.last_delegation_at:
            last_time = datetime.fromisoformat(status.last_delegation_at)
            now = datetime.now(timezone.utc)
            elapsed = (now - last_time).total_seconds()
            if elapsed < config.delegation_cooldown_seconds:
                remaining = config.delegation_cooldown_seconds - elapsed
                reasons.append(f"Cooldown active ({remaining:.0f}s remaining)")

        return {
            "allowed": len(reasons) == 0,
            "reasons": reasons,
            "session_delegations": status.total_delegations,
            "session_limit": config.max_delegations_per_session,
            "active_delegations": active_count,
            "parallel_limit": config.max_parallel_delegations,
        }

    # --- Evaluation ---

    def evaluate(self) -> Dict[str, Any]:
        """Check if orchestration should trigger delegation.

        Evaluates:
        1. Context threshold reached
        2. Delegatable subtasks exist
        3. Safety guards pass

        Returns:
            Dict with evaluation result and details
        """
        self._set_state(OrchestrationState.EVALUATING)

        config = self._load_config()
        status = self._load_status()
        result = {
            "should_delegate": False,
            "reasons": [],
            "context_usage": 0.0,
            "threshold": config.context_threshold,
            "delegatable_subtasks": [],
            "feature_id": None,
            "feature_name": None,
        }

        try:
            # Check context usage
            metrics = self.context_tracker.get_metrics()
            context_usage = metrics.context_usage_percent / 100.0
            result["context_usage"] = context_usage

            context_met = context_usage >= config.context_threshold
            if not context_met:
                result["reasons"].append(
                    f"Context usage ({context_usage:.1%}) below threshold "
                    f"({config.context_threshold:.0%})"
                )

            # Get current feature
            feature = self.feature_manager.get_in_progress()
            if not feature:
                result["reasons"].append("No feature currently in progress")
                self._update_evaluation_result(result)
                return result

            result["feature_id"] = feature.id
            result["feature_name"] = feature.name

            # Find delegatable subtasks
            pending_subtasks = [
                (i, st.name) for i, st in enumerate(feature.subtasks)
                if not st.done
            ]

            if not pending_subtasks:
                result["reasons"].append("No pending subtasks")
                self._update_evaluation_result(result)
                return result

            # Check which subtasks match delegation rules
            for idx, subtask_name in pending_subtasks:
                rule = self.delegation_manager.should_delegate(subtask_name)
                if rule and rule.priority >= config.priority_threshold:
                    result["delegatable_subtasks"].append({
                        "index": idx,
                        "name": subtask_name,
                        "rule": rule.name,
                        "subagent_type": rule.subagent_type,
                        "priority": rule.priority,
                    })

            if not result["delegatable_subtasks"]:
                result["reasons"].append(
                    "No subtasks match delegation rules with sufficient priority"
                )
                self._update_evaluation_result(result)
                return result

            # Check minimum subtask count
            if len(result["delegatable_subtasks"]) < config.min_subtasks_for_delegation:
                result["reasons"].append(
                    f"Need at least {config.min_subtasks_for_delegation} delegatable "
                    f"subtasks (found {len(result['delegatable_subtasks'])})"
                )
                self._update_evaluation_result(result)
                return result

            # Check safety guards
            safety = self.can_delegate(feature.id)
            if not safety["allowed"]:
                result["reasons"].extend(safety["reasons"])
                self._update_evaluation_result(result)
                return result

            # All checks passed
            if context_met:
                result["should_delegate"] = True

        except Exception as e:
            result["reasons"].append(f"Evaluation error: {str(e)}")

        finally:
            self._update_evaluation_result(result)
            self._set_state(OrchestrationState.IDLE)

        return result

    def _update_evaluation_result(self, result: Dict[str, Any]):
        """Update status with evaluation result."""
        status = self._load_status()
        status.last_evaluation_at = datetime.now(timezone.utc).isoformat()
        status.last_evaluation_result = result
        status.delegation_available = result.get("should_delegate", False)
        self._save_status()

    # --- Queue Management ---

    def generate_delegation_queue(
        self, feature_id: Optional[str] = None
    ) -> List[DelegationQueueItem]:
        """Generate queue of delegatable subtasks for a feature.

        Args:
            feature_id: Feature to generate queue for (or current in-progress)

        Returns:
            List of DelegationQueueItem ready for delegation
        """
        self._set_state(OrchestrationState.DELEGATING)

        config = self._load_config()
        status = self._load_status()
        queue = []

        try:
            # Get feature
            if feature_id:
                feature = self.feature_manager.get_feature(feature_id)
            else:
                feature = self.feature_manager.get_in_progress()

            if not feature:
                return queue

            # Get pending subtasks
            pending_subtasks = [
                (i, st.name) for i, st in enumerate(feature.subtasks)
                if not st.done
            ]

            # Match against rules and create queue items
            for idx, subtask_name in pending_subtasks:
                rule = self.delegation_manager.should_delegate(subtask_name)
                if not rule or rule.priority < config.priority_threshold:
                    continue

                # Generate prompt
                prompt = self.delegation_manager.generate_delegation_prompt(
                    subtask_name=subtask_name,
                    feature_name=feature.name,
                    feature_id=feature.id,
                    rule=rule,
                )

                # Estimate savings
                savings = self.delegation_manager.estimate_savings(subtask_name, rule)

                item = DelegationQueueItem(
                    id="",  # Will be auto-generated
                    feature_id=feature.id,
                    feature_name=feature.name,
                    subtask_name=subtask_name,
                    subtask_index=idx,
                    rule_name=rule.name,
                    subagent_type=rule.subagent_type,
                    priority=rule.priority,
                    prompt=prompt,
                    estimated_tokens_saved=savings,
                )
                queue.append(item)

            # Sort by priority (highest first)
            queue.sort(key=lambda x: x.priority, reverse=True)

            # Respect limits
            remaining_slots = min(
                config.max_parallel_delegations - len(status.active_delegations),
                config.max_delegations_per_session - status.total_delegations,
                config.max_delegations_per_feature - status.feature_delegation_counts.get(
                    feature.id, 0
                ),
            )
            queue = queue[:max(0, remaining_slots)]

            # Update status with queue
            status.queued_delegations = queue
            self._save_status()

        finally:
            self._set_state(OrchestrationState.IDLE)

        return queue

    def get_queue(self) -> List[DelegationQueueItem]:
        """Get current delegation queue."""
        status = self._load_status()
        return status.queued_delegations

    def clear_queue(self):
        """Clear the delegation queue."""
        status = self._load_status()
        status.queued_delegations = []
        self._save_status()

    # --- Delegation Lifecycle ---

    def start_delegation(self, delegation_id: str) -> Optional[DelegationQueueItem]:
        """Mark a delegation as active.

        Args:
            delegation_id: ID of delegation to start

        Returns:
            The started DelegationQueueItem or None if not found
        """
        status = self._load_status()

        # Find in queue
        item = None
        for i, queued in enumerate(status.queued_delegations):
            if queued.id == delegation_id:
                item = status.queued_delegations.pop(i)
                break

        if not item:
            return None

        # Update item state
        item.status = "active"
        item.started_at = datetime.now(timezone.utc).isoformat()

        # Move to active list
        status.active_delegations.append(item)
        status.total_delegations += 1
        status.feature_delegation_counts[item.feature_id] = (
            status.feature_delegation_counts.get(item.feature_id, 0) + 1
        )
        status.last_delegation_at = datetime.now(timezone.utc).isoformat()

        # Track in DelegationManager
        self.delegation_manager.track_delegation(
            feature_id=item.feature_id,
            subtask_name=item.subtask_name,
            subagent_type=item.subagent_type,
        )

        self._set_state(OrchestrationState.WAITING)
        self._save_status()

        return item

    def complete_delegation(
        self,
        delegation_id: str,
        result_summary: str,
        files_created: Optional[List[str]] = None,
        files_modified: Optional[List[str]] = None,
        mark_subtask_done: bool = True,
    ) -> Optional[DelegationQueueItem]:
        """Process delegation result and update feature.

        Args:
            delegation_id: ID of delegation to complete
            result_summary: Summary of what was accomplished
            files_created: List of files created
            files_modified: List of files modified
            mark_subtask_done: Whether to mark the subtask as done

        Returns:
            The completed DelegationQueueItem or None if not found
        """
        self._set_state(OrchestrationState.INTEGRATING)
        status = self._load_status()

        # Find in active list
        item = None
        for i, active in enumerate(status.active_delegations):
            if active.id == delegation_id:
                item = status.active_delegations.pop(i)
                break

        if not item:
            self._set_state(OrchestrationState.IDLE)
            return None

        try:
            # Update item state
            item.status = "completed"
            item.completed_at = datetime.now(timezone.utc).isoformat()
            item.result_summary = result_summary
            item.files_created = files_created or []
            item.files_modified = files_modified or []

            # Update counters
            status.completed_delegations += 1
            status.total_tokens_saved += item.estimated_tokens_saved

            # Add to history
            status.completed_delegations_history.append(item)

            # Complete in DelegationManager
            self.delegation_manager.complete_delegation(
                feature_id=item.feature_id,
                subtask_name=item.subtask_name,
                summary=result_summary,
                files_created=files_created,
                files_modified=files_modified,
            )

            # Mark subtask as done in feature
            if mark_subtask_done:
                self.feature_manager.complete_subtask(
                    feature_id=item.feature_id,
                    subtask_index=item.subtask_index,
                )

        finally:
            self._save_status()
            # Return to WAITING if more active, else IDLE
            if status.active_delegations:
                self._set_state(OrchestrationState.WAITING)
            else:
                self._set_state(OrchestrationState.IDLE)

        return item

    def fail_delegation(
        self,
        delegation_id: str,
        error: str,
    ) -> Optional[DelegationQueueItem]:
        """Mark a delegation as failed.

        Args:
            delegation_id: ID of delegation that failed
            error: Error message or reason

        Returns:
            The failed DelegationQueueItem or None if not found
        """
        status = self._load_status()

        # Find in active list
        item = None
        for i, active in enumerate(status.active_delegations):
            if active.id == delegation_id:
                item = status.active_delegations.pop(i)
                break

        if not item:
            return None

        # Update item state
        item.status = "failed"
        item.completed_at = datetime.now(timezone.utc).isoformat()
        item.error = error

        # Update counters
        status.failed_delegations += 1

        # Add to history
        status.completed_delegations_history.append(item)

        self._save_status()

        # Return to WAITING if more active, else IDLE
        if status.active_delegations:
            self._set_state(OrchestrationState.WAITING)
        else:
            self._set_state(OrchestrationState.IDLE)

        return item

    # --- Status and Metrics ---

    def get_status(self) -> Dict[str, Any]:
        """Get current orchestration state and metrics.

        Returns:
            Dict with state, metrics, and active delegations
        """
        status = self._load_status()
        config = self._load_config()

        return {
            "state": status.state.value,
            "session_start": status.session_start,
            "delegation_available": status.delegation_available,
            "metrics": {
                "total_delegations": status.total_delegations,
                "completed_delegations": status.completed_delegations,
                "failed_delegations": status.failed_delegations,
                "total_tokens_saved": status.total_tokens_saved,
                "success_rate": (
                    status.completed_delegations / status.total_delegations
                    if status.total_delegations > 0 else 0.0
                ),
            },
            "limits": {
                "session_used": status.total_delegations,
                "session_max": config.max_delegations_per_session,
                "parallel_used": len(status.active_delegations),
                "parallel_max": config.max_parallel_delegations,
            },
            "queued": [d.to_dict() for d in status.queued_delegations],
            "active": [d.to_dict() for d in status.active_delegations],
            "last_evaluation": status.last_evaluation_result,
        }

    def get_active_delegations(self) -> List[DelegationQueueItem]:
        """Get list of currently active delegations."""
        status = self._load_status()
        return status.active_delegations

    def reset_session(self):
        """Reset orchestration state for a new session."""
        self._status = OrchestrationStatus()
        self._save_status()

    # --- Display Methods ---

    def show_status(self):
        """Display orchestration status."""
        status = self._load_status()
        config = self._load_config()

        state_colors = {
            OrchestrationState.IDLE: "green",
            OrchestrationState.EVALUATING: "yellow",
            OrchestrationState.DELEGATING: "blue",
            OrchestrationState.WAITING: "cyan",
            OrchestrationState.INTEGRATING: "magenta",
        }

        state_color = state_colors.get(status.state, "white")

        console.print()
        console.print(
            Panel.fit(
                f"[bold blue]Orchestration Engine[/bold blue]\n"
                f"State: [{state_color}]{status.state.value.upper()}[/{state_color}]\n"
                f"Delegation available: "
                f"{'[green]Yes[/green]' if status.delegation_available else '[dim]No[/dim]'}",
                border_style="blue",
            )
        )

        # Metrics
        console.print("\n[bold]Session Metrics:[/bold]")
        console.print(f"  Total delegations: {status.total_delegations}/{config.max_delegations_per_session}")
        console.print(f"  Completed: {status.completed_delegations}")
        console.print(f"  Failed: {status.failed_delegations}")
        console.print(f"  Tokens saved: {status.total_tokens_saved:,}")

        # Active delegations
        if status.active_delegations:
            console.print(f"\n[bold yellow]Active ({len(status.active_delegations)}):[/bold yellow]")
            for d in status.active_delegations:
                console.print(f"  [{d.id}] {d.subtask_name} ({d.subagent_type})")

        # Queued delegations
        if status.queued_delegations:
            console.print(f"\n[bold blue]Queued ({len(status.queued_delegations)}):[/bold blue]")
            for d in status.queued_delegations[:5]:
                console.print(f"  [{d.id}] {d.subtask_name} (priority: {d.priority})")
            if len(status.queued_delegations) > 5:
                console.print(f"  [dim]... and {len(status.queued_delegations) - 5} more[/dim]")

        # Last evaluation
        if status.last_evaluation_result:
            result = status.last_evaluation_result
            console.print("\n[bold]Last Evaluation:[/bold]")
            console.print(f"  Context usage: {result.get('context_usage', 0):.1%}")
            console.print(f"  Should delegate: {result.get('should_delegate', False)}")
            if result.get("reasons"):
                console.print("  Reasons:")
                for reason in result["reasons"][:3]:
                    console.print(f"    - {reason}")

    def show_queue_table(self):
        """Display delegation queue as a table."""
        status = self._load_status()

        if not status.queued_delegations and not status.active_delegations:
            console.print("[dim]No delegations in queue or active[/dim]")
            return

        table = Table(title="Delegation Queue")
        table.add_column("ID", style="cyan", width=10)
        table.add_column("Subtask", style="white")
        table.add_column("Type", style="yellow", width=10)
        table.add_column("Priority", justify="center", width=8)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Est. Savings", justify="right", width=12)

        # Active first
        for d in status.active_delegations:
            table.add_row(
                d.id,
                d.subtask_name[:40] + ("..." if len(d.subtask_name) > 40 else ""),
                d.subagent_type,
                str(d.priority),
                "[yellow]ACTIVE[/yellow]",
                f"{d.estimated_tokens_saved:,}",
            )

        # Then queued
        for d in status.queued_delegations:
            table.add_row(
                d.id,
                d.subtask_name[:40] + ("..." if len(d.subtask_name) > 40 else ""),
                d.subagent_type,
                str(d.priority),
                "[blue]queued[/blue]",
                f"{d.estimated_tokens_saved:,}",
            )

        console.print(table)


def get_orchestration_engine(project_path: str = ".") -> OrchestrationEngine:
    """Get an orchestration engine instance.

    Args:
        project_path: Path to project (default: current directory)

    Returns:
        OrchestrationEngine instance
    """
    return OrchestrationEngine(project_path)
