# Subagent Delegation Research Report

**Author:** Systems Architect Agent
**Date:** 2025-12-12
**Version:** 1.0
**Status:** ✅ Implemented in v1.1.0

> **Note:** This research led to the delegation feature implemented in v1.1.0. See `claude-harness delegation --help` for usage. The document is preserved as historical context for the design decisions.

---

## Executive Summary

This research report analyzes the feasibility and design of a "subagent delegation" feature for claude-harness. The feature would allow users to configure the harness to instruct Claude Code's main agent to delegate specific features or tasks to specialized subagents, with those subagents reporting summaries back to the main agent.

**Key Findings:**
- Context accumulation is a real problem: Claude Code sessions can consume 200K+ tokens
- Subagent delegation can reduce main context usage by 40-70% for complex tasks
- Claude Code's Task tool provides the mechanism for delegation
- Integration with claude-harness is feasible and aligns with existing architecture

**Recommendation:** Proceed with implementation as a v1.3.0 feature, prioritized as Medium-High.

---

## 1. Problem Analysis

### 1.1 Context Accumulation in Claude Code Sessions

When working on complex features in Claude Code, the context window fills up from:

| Context Source | Typical Size | Accumulation Pattern |
|----------------|--------------|----------------------|
| System prompts | 2-5K tokens | Fixed overhead |
| CLAUDE.md files | 1-10K tokens | Loaded per session |
| File reads | 1-50K tokens each | Cumulative |
| Command outputs | 0.5-10K per command | Cumulative |
| Conversation history | 5-20K per exchange | Cumulative |
| Tool call overhead | 0.1-0.5K per call | Cumulative |

**Problem:** A typical 2-hour feature implementation session can easily consume 100K-180K tokens of the 200K context window, leaving limited room for complex reasoning or additional context.

### 1.2 Current Context Limits and Costs

Based on research:

| Model | Context Window | Input Cost | Output Cost |
|-------|----------------|------------|-------------|
| Claude Opus 4.5 | 200K tokens | $5.00/M | $25.00/M |
| Claude Sonnet 4.5 | 200K (API), 1M (Enterprise) | $3.00/M | $15.00/M |
| Claude Sonnet 4.5 (>200K) | 1M tokens | $6.00/M | $22.50/M |

**Impact:**
- Long sessions hit context limits before feature completion
- Degraded reasoning quality as context fills
- Increased costs from repeated context in multi-session work
- Lost context when session handoffs are required

### 1.3 Context Savings from Delegation

Subagent delegation provides savings because:

1. **Isolated Context Windows:** Each subagent operates in its own context window
2. **Summary-Only Returns:** Only essential information flows back to main agent
3. **Parallel Execution:** Multiple subagents can work simultaneously

**Estimated Savings by Task Type:**

| Task Type | Main Agent Tokens | With Delegation | Savings |
|-----------|-------------------|-----------------|---------|
| Code exploration | 30K | 3-5K (summary) | 83-90% |
| Test writing | 20K | 5-8K (summary) | 60-75% |
| Documentation | 15K | 3-5K (summary) | 67-80% |
| Bug investigation | 40K | 8-15K (summary) | 62-80% |
| Code review | 25K | 5-10K (summary) | 60-80% |

**Overall Session Impact:** For a feature with 4-5 delegatable tasks, main context usage can be reduced by 40-70%.

---

## 2. Solution Space Exploration

### 2.1 How Subagent Delegation Works

Claude Code provides the **Task tool** for spawning subagents. The workflow:

```
Main Agent (Orchestrator)
    |
    +-- Task Tool --> Subagent A (Code Exploration)
    |                     |
    |                     +-- Returns summary
    |
    +-- Task Tool --> Subagent B (Test Writing)
    |                     |
    |                     +-- Returns summary
    |
    +-- Synthesizes results
```

**Key Characteristics:**
- Subagents have independent context windows
- Subagents cannot spawn other subagents (no nesting)
- Subagents can use most Claude Code tools (Read, Write, Bash, Grep, etc.)
- Subagents return a text summary to the main agent

### 2.2 Built-in Subagent Types

Claude Code includes specialized built-in subagents:

| Subagent | Purpose | Mode |
|----------|---------|------|
| **Plan** | Research codebase before creating plans | Read-only |
| **Explore** | Fast file discovery and code analysis | Read-only |

These are automatically invoked in certain modes but can also be instructed via prompts.

### 2.3 Task Candidates for Delegation

Based on research and claude-harness feature structure, ideal delegation candidates:

**High Delegation Value:**
- Codebase exploration and file discovery
- Test suite creation and expansion
- Documentation generation
- Code review and analysis
- Dependency analysis
- Migration planning

**Medium Delegation Value:**
- Specific refactoring tasks
- Bug investigation
- Performance analysis
- Security auditing

**Low Delegation Value (Keep in Main Agent):**
- Core feature implementation
- Complex integration work
- User interaction/clarification
- Final validation and commit

### 2.4 Information Flow Design

**From Main Agent to Subagent:**
```yaml
delegation_context:
  feature_id: "F-001"
  feature_name: "User Authentication"
  task: "Write unit tests for login flow"
  constraints:
    - "Use pytest framework"
    - "Mock external services"
    - "Target 90% coverage for auth module"
  relevant_files:
    - "auth/login.py"
    - "tests/test_auth.py (reference)"
  expected_output: "Summary of tests created with file paths"
```

**From Subagent to Main Agent:**
```yaml
delegation_result:
  status: "completed"
  summary: |
    Created 8 unit tests in tests/unit/test_login.py:
    - test_login_success: Valid credentials flow
    - test_login_invalid_password: Error handling
    - test_login_user_not_found: 404 case
    - test_login_rate_limiting: Throttle behavior
    - test_session_creation: Token generation
    - test_session_expiry: Timeout handling
    - test_logout_clears_session: Cleanup
    - test_concurrent_sessions: Multi-device
  files_created:
    - "tests/unit/test_login.py"
  files_modified: []
  coverage_impact: "+15% on auth module"
  issues_found: []
  next_steps:
    - "Run tests to verify: pytest tests/unit/test_login.py -v"
```

---

## 3. Technical Feasibility

### 3.1 Claude Code Task Tool Mechanics

The Task tool is invoked through Claude's tool system:

```
Tool: Task
Input: {
  "description": "Task description for the subagent",
  "prompt": "Detailed instructions including context and constraints"
}
Output: Subagent's summary response
```

**Capabilities:**
- Read files (Read, Glob, Grep tools)
- Write/Edit files (Write, Edit tools)
- Execute commands (Bash tool)
- Web searches (WebSearch tool)
- Full reasoning capabilities

**Limitations:**
- Cannot spawn nested subagents
- Cannot access main agent's conversation history
- Must be given explicit context in the prompt
- No direct communication between subagents

### 3.2 Prompt Engineering for Delegation

Effective delegation requires structured prompts. Example template:

```markdown
## Context
You are a specialized subagent for the claude-harness workflow.

## Your Task
{task_description}

## Feature Context
- Feature ID: {feature_id}
- Feature Name: {feature_name}
- Current Subtask: {subtask_name}

## Constraints
{constraints_list}

## Relevant Files
{file_list}

## Expected Output Format
Provide a summary containing:
1. What was accomplished
2. Files created/modified (with paths)
3. Key decisions made
4. Issues encountered
5. Recommended next steps

Keep the summary concise (under 500 words) to preserve main agent context.
```

### 3.3 Integration Points with Claude-Harness

The delegation feature can integrate with:

| Harness Component | Integration |
|-------------------|-------------|
| **feature_manager.py** | Subtask-level delegation triggers |
| **config.json** | Delegation settings and preferences |
| **CLAUDE.md templates** | Delegation prompts and instructions |
| **progress_tracker.py** | Track delegated vs direct work |
| **context_tracker.py** | Monitor context savings |

---

## 4. Architecture Design

### 4.1 System Overview

```
+---------------------------+
|     claude-harness        |
|  +---------------------+  |
|  | DelegationManager   |  |
|  | - rules             |  |
|  | - templates         |  |
|  | - tracking          |  |
|  +---------------------+  |
|           |               |
|           v               |
|  +---------------------+  |
|  | PromptGenerator     |  |
|  | - delegation prompts|  |
|  | - context injection |  |
|  +---------------------+  |
+---------------------------+
           |
           | (generates CLAUDE.md content)
           v
+---------------------------+
|     Claude Code           |
|  +---------------------+  |
|  | Main Agent          |  |
|  | - feature work      |  |
|  | - orchestration     |  |
|  +---------------------+  |
|           |               |
|           | Task tool     |
|           v               |
|  +---------------------+  |
|  | Subagents           |  |
|  | - exploration       |  |
|  | - testing           |  |
|  | - documentation     |  |
|  +---------------------+  |
+---------------------------+
```

### 4.2 Component Design

#### DelegationManager

```python
@dataclass
class DelegationRule:
    """A rule for when to delegate to subagents."""

    name: str
    task_patterns: List[str]  # Regex patterns matching subtask names
    subagent_type: str  # "explore", "test", "document", "review"
    priority: int  # Higher = delegate more aggressively
    enabled: bool
    constraints: List[str]  # Additional constraints for the subagent

@dataclass
class DelegationConfig:
    """Configuration for subagent delegation."""

    enabled: bool = False
    auto_delegate: bool = False  # Automatically delegate matching tasks
    rules: List[DelegationRule] = field(default_factory=list)
    default_summary_length: int = 500  # Max words in summary
    parallel_limit: int = 3  # Max concurrent subagents

class DelegationManager:
    """Manages delegation rules and prompt generation."""

    def should_delegate(self, subtask: Subtask, feature: Feature) -> Optional[DelegationRule]:
        """Determine if a subtask should be delegated."""
        pass

    def generate_delegation_prompt(self, subtask: Subtask, feature: Feature, rule: DelegationRule) -> str:
        """Generate the delegation prompt for CLAUDE.md."""
        pass

    def track_delegation(self, feature_id: str, subtask_index: int, delegated: bool):
        """Track which tasks were delegated."""
        pass
```

### 4.3 Data Flow

```
1. User runs: claude-harness feature start F-001
2. DelegationManager checks subtasks against rules
3. For matching subtasks, generates delegation instructions
4. Instructions added to generated CLAUDE.md section
5. Main agent reads instructions on session start
6. Main agent decides to delegate based on instructions
7. Subagent executes and returns summary
8. Main agent synthesizes and continues work
9. Harness tracks delegation metrics
```

---

## 5. Configuration Schema

### 5.1 config.json Extension

```json
{
  "delegation": {
    "enabled": true,
    "auto_delegate": false,
    "parallel_limit": 3,
    "summary_max_words": 500,
    "rules": [
      {
        "name": "exploration",
        "task_patterns": ["explore.*", "investigate.*", "find.*", "discover.*"],
        "subagent_type": "explore",
        "priority": 10,
        "enabled": true,
        "constraints": ["Read-only operations", "Focus on file structure and patterns"]
      },
      {
        "name": "testing",
        "task_patterns": ["test.*", "write.*test.*", "unit test.*", "e2e.*"],
        "subagent_type": "test",
        "priority": 8,
        "enabled": true,
        "constraints": ["Use project test framework", "Include edge cases"]
      },
      {
        "name": "documentation",
        "task_patterns": ["document.*", "doc.*", "readme.*", "comment.*"],
        "subagent_type": "document",
        "priority": 6,
        "enabled": true,
        "constraints": ["Follow project doc conventions", "Be concise"]
      },
      {
        "name": "review",
        "task_patterns": ["review.*", "audit.*", "check.*", "validate.*"],
        "subagent_type": "review",
        "priority": 7,
        "enabled": true,
        "constraints": ["Focus on critical issues", "Provide actionable feedback"]
      }
    ],
    "default_constraints": [
      "Preserve main agent context by keeping summaries concise",
      "Report file paths absolutely",
      "Include specific line numbers when relevant"
    ]
  }
}
```

### 5.2 CLI Extensions

```bash
# Enable/disable delegation
claude-harness delegation enable
claude-harness delegation disable

# Show delegation rules
claude-harness delegation rules

# Add custom rule
claude-harness delegation add-rule --name "migration" \
  --patterns "migrate.*,upgrade.*" \
  --type "explore" \
  --constraints "Read-only,Focus on breaking changes"

# Show delegation status for a feature
claude-harness feature info F-001 --delegation

# Override delegation for a specific subtask
claude-harness feature delegate F-001 "subtask name" --force
claude-harness feature no-delegate F-001 "subtask name"
```

---

## 6. Prompt Template Examples

### 6.1 CLAUDE.md Delegation Section

```markdown
## SUBAGENT DELEGATION

This project uses claude-harness for optimized AI workflow. The following delegation
guidelines help preserve context while maintaining productivity.

### Delegation Rules

When starting work on the current feature, evaluate each subtask:

**Delegate These Tasks (use Task tool):**
- Exploration tasks: Use an Explore subagent for file discovery and codebase analysis
- Test writing: Delegate to a Test subagent with specific coverage requirements
- Documentation: Delegate doc generation to a Document subagent
- Code review: Use a Review subagent for audit tasks

**Keep These Tasks (main agent):**
- Core implementation requiring integration decisions
- Tasks needing user clarification
- Final integration and validation
- Commit and PR operations

### Delegation Prompt Template

When delegating, structure the Task prompt as:

```
Feature: {feature_name} (ID: {feature_id})
Subtask: {subtask_name}

Context:
- Project stack: {stack_info}
- Relevant files: {file_list}

Task: {detailed_task_description}

Constraints:
{constraints}

Output Requirements:
- Summary under 500 words
- List files created/modified
- Note any issues or blockers
- Suggest next steps
```

### Current Feature Delegation Hints

Feature: {current_feature.name}
Subtasks:
{for subtask in current_feature.subtasks}
- [{subtask.delegation_status}] {subtask.name}
  {if subtask.should_delegate}
  -> DELEGATE: {subtask.delegation_prompt_hint}
  {endif}
{endfor}
```

### 6.2 Specific Subagent Prompts

#### Exploration Subagent

```markdown
## Exploration Task

You are an Explore subagent analyzing the codebase for feature implementation.

**Feature:** User Authentication (F-001)
**Task:** Discover existing authentication patterns and relevant files

**Instructions:**
1. Search for auth-related files (auth*, login*, session*)
2. Identify key classes and functions
3. Map dependencies between auth components
4. Note any existing tests

**Constraints:**
- Read-only operations only
- Focus on structure, not detailed implementation
- Time budget: 2 minutes exploration

**Output Format:**
```yaml
discovered_files:
  - path: "auth/login.py"
    purpose: "Login controller"
    dependencies: ["models.User", "services.SessionManager"]
patterns:
  - "Decorator-based auth checks (@require_auth)"
  - "JWT tokens for session management"
key_functions:
  - "authenticate_user(email, password) -> User"
  - "create_session(user) -> Token"
existing_tests: "tests/test_auth.py (12 tests)"
recommendations:
  - "Follow existing decorator pattern"
  - "Use SessionManager for token operations"
```
```

#### Test Writing Subagent

```markdown
## Test Writing Task

You are a Test subagent creating unit tests for a feature.

**Feature:** User Authentication (F-001)
**Task:** Write unit tests for login flow

**Context:**
- Test framework: pytest
- Target file: auth/login.py
- Coverage goal: 90% for auth module

**Relevant Code:**
```python
# auth/login.py - key function signatures
def authenticate_user(email: str, password: str) -> Optional[User]:
def create_session(user: User) -> Session:
def validate_session(token: str) -> Optional[User]:
```

**Constraints:**
- Mock external services (database, email)
- Include edge cases (invalid input, rate limiting)
- Follow existing test patterns in tests/

**Output Format:**
```yaml
tests_created:
  file: "tests/unit/test_login.py"
  count: 8
  tests:
    - name: "test_authenticate_valid_credentials"
      covers: "authenticate_user happy path"
    - name: "test_authenticate_invalid_password"
      covers: "authenticate_user error handling"
    # ... more tests
coverage_impact: "+15% estimated on auth module"
run_command: "pytest tests/unit/test_login.py -v"
issues: []
```
```

---

## 7. Integration with Existing Features

### 7.1 Feature Management Integration

```python
# feature_manager.py additions

@dataclass
class Subtask:
    name: str
    done: bool = False
    delegated: bool = False  # NEW: Track if delegated
    delegation_result: Optional[str] = None  # NEW: Subagent summary

class FeatureManager:
    def mark_subtask_delegated(self, feature_id: str, subtask_index: int,
                                result: str) -> Optional[Feature]:
        """Mark a subtask as delegated with its result summary."""
        pass

    def get_delegation_status(self, feature_id: str) -> dict:
        """Get delegation status for all subtasks in a feature."""
        pass
```

### 7.2 Context Tracking Integration

```python
# context_tracker.py additions

class ContextTracker:
    def track_delegation(self, feature_id: str, subtask: str,
                         estimated_savings: int):
        """Track context savings from delegation."""
        pass

    def get_delegation_metrics(self) -> dict:
        """Get delegation-related metrics."""
        return {
            "tasks_delegated": 12,
            "estimated_context_saved": 45000,  # tokens
            "delegation_success_rate": 0.92
        }
```

### 7.3 Progress Tracking Integration

```markdown
# progress.md additions

### Delegation Summary
- Delegated tasks: 4/7
- Estimated context saved: ~45K tokens
- Delegation results:
  - [x] Explore auth patterns -> Found 3 key files
  - [x] Write login tests -> 8 tests created
  - [ ] Document API endpoints -> Pending
  - [x] Review security -> 2 issues found
```

---

## 8. Potential Challenges and Mitigations

### 8.1 Challenge: Subagent Quality Variance

**Problem:** Subagent output quality may vary; poor summaries waste main context.

**Mitigation:**
- Structured output templates with validation
- Length limits enforced in prompts
- Retry mechanism for low-quality outputs
- Option to expand summary if critical info missing

### 8.2 Challenge: Context Loss in Handoff

**Problem:** Important details may be lost in summarization.

**Mitigation:**
- Require specific output sections (files, decisions, issues)
- Allow main agent to request elaboration
- Store full subagent output in harness for reference
- Include "expand" markers for detail retrieval

### 8.3 Challenge: Coordination Overhead

**Problem:** Managing multiple subagents adds complexity.

**Mitigation:**
- Limit parallel subagents (default: 3)
- Clear naming and tagging in summaries
- Harness-managed coordination hints in CLAUDE.md
- Progress tracking integration

### 8.4 Challenge: User Learning Curve

**Problem:** Users may not understand when delegation helps.

**Mitigation:**
- Clear documentation with examples
- Sensible default rules
- Optional auto-delegation mode
- CLI feedback on delegation decisions

### 8.5 Challenge: Over-Delegation

**Problem:** Delegating too much loses coherence and integration quality.

**Mitigation:**
- Priority system for delegation rules
- "Core task" markers that prevent delegation
- Context threshold: only delegate when context > 50% used
- User override capabilities

---

## 9. Implementation Roadmap

### Phase 1: Foundation (v1.3.0)

**Timeline:** 2-3 weeks

**Deliverables:**
1. DelegationConfig schema in config.json
2. Basic DelegationManager class
3. CLI commands: `delegation enable/disable/rules`
4. CLAUDE.md template with delegation section
5. Documentation

**Success Criteria:**
- Configuration persisted and loaded correctly
- CLAUDE.md includes delegation instructions
- Users can enable/disable delegation

### Phase 2: Rules Engine (v1.3.1)

**Timeline:** 2 weeks

**Deliverables:**
1. Pattern-based rule matching
2. Custom rule creation via CLI
3. Rule priority system
4. Subtask delegation tracking in features.json

**Success Criteria:**
- Rules correctly match subtask names
- Custom rules persist across sessions
- Delegation tracked per subtask

### Phase 3: Prompt Templates (v1.3.2)

**Timeline:** 2 weeks

**Deliverables:**
1. Subagent prompt templates library
2. Context injection (stack, files, constraints)
3. Output format validation
4. Template customization

**Success Criteria:**
- Generated prompts follow templates
- Templates produce consistent subagent behavior
- Users can customize templates

### Phase 4: Metrics & Optimization (v1.4.0)

**Timeline:** 2-3 weeks

**Deliverables:**
1. Delegation metrics in context_tracker
2. Context savings estimation
3. Integration with progress tracking
4. Dashboard/report showing delegation impact

**Success Criteria:**
- Accurate context savings estimates
- Metrics visible in `claude-harness status`
- Progress.md includes delegation summary

### Phase 5: Advanced Features (v1.5.0)

**Timeline:** 3-4 weeks

**Deliverables:**
1. Auto-delegation mode
2. Parallel subagent orchestration hints
3. Subagent result caching
4. Integration with CI/CD for batch delegation

**Success Criteria:**
- Auto-delegation makes correct decisions >80% of time
- Parallel hints improve efficiency measurably
- Cache reduces redundant exploration

---

## 10. Conclusion

### 10.1 Summary

Subagent delegation is a viable and valuable feature for claude-harness that addresses the real problem of context exhaustion in complex coding sessions. The feature:

- **Leverages existing Claude Code capabilities** (Task tool)
- **Integrates naturally with harness architecture** (features, progress, context)
- **Provides measurable benefits** (40-70% context savings on complex tasks)
- **Maintains user control** (configurable rules, overrides)

### 10.2 Recommendation

**Proceed with implementation** following the phased roadmap:

1. **Priority:** Medium-High (significant user value, moderate complexity)
2. **Target Version:** v1.3.0 for foundation, v1.4.0 for full feature set
3. **Key Success Metric:** Average context savings > 30% for delegatable tasks
4. **Risk Level:** Low-Medium (builds on proven Claude Code features)

### 10.3 Next Steps

1. Review this research report with stakeholders
2. Finalize configuration schema
3. Begin Phase 1 implementation
4. Create user documentation draft
5. Plan beta testing with real feature workflows

---

## Appendix A: References

- [Claude Code Subagents Documentation](https://code.claude.com/docs/en/sub-agents)
- [Task/Agent Tools - ClaudeLog](https://claudelog.com/mechanics/task-agent-tools/)
- [Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Claude Context Window Limits](https://www.datastudios.org/post/claude-context-window-token-limits-memory-policy-and-2025-rules)
- [Claude Code Pricing](https://claudelog.com/claude-code-pricing/)
- [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **Main Agent** | The primary Claude Code instance handling user interaction |
| **Subagent** | A specialized agent spawned via Task tool with isolated context |
| **Task Tool** | Claude Code tool for delegating work to subagents |
| **Context Window** | The token limit for a single agent's working memory |
| **Delegation Rule** | Pattern-based configuration for automatic task delegation |
| **Orchestration** | Coordinating multiple agents to complete a larger task |

## Appendix C: Example Feature with Delegation

```yaml
feature:
  id: "F-012"
  name: "Add Payment Processing"
  status: "in_progress"
  subtasks:
    - name: "Explore payment patterns in codebase"
      delegation:
        enabled: true
        type: "explore"
        estimated_savings: 25000 tokens

    - name: "Design payment service interface"
      delegation:
        enabled: false
        reason: "Core architecture decision"

    - name: "Implement Stripe integration"
      delegation:
        enabled: false
        reason: "Core implementation"

    - name: "Write unit tests for payment service"
      delegation:
        enabled: true
        type: "test"
        estimated_savings: 18000 tokens

    - name: "Add E2E tests for checkout flow"
      delegation:
        enabled: true
        type: "test"
        estimated_savings: 15000 tokens

    - name: "Document payment API endpoints"
      delegation:
        enabled: true
        type: "document"
        estimated_savings: 12000 tokens

    - name: "Security review of payment handling"
      delegation:
        enabled: true
        type: "review"
        estimated_savings: 20000 tokens

estimated_total_savings: 90000 tokens (45% of typical feature context)
```

---

*End of Research Report*
