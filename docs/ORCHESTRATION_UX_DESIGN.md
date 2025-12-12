# Orchestration Mode UX Design

**Document Type:** Experience Design Specification
**Author:** Experience Designer Agent
**Date:** 2025-12-12
**Status:** Draft for Review

---

## Executive Summary

This document defines the user experience for claude-harness orchestration mode, where the system automatically identifies delegatable tasks and coordinates subagent execution to achieve 40-70% context savings.

**Design Principles:**
1. Progressive disclosure - Simple entry, advanced control available
2. Transparency - Users always know what is happening
3. Control - Easy pause, skip, and override at any time
4. Value visibility - Show context savings achieved

---

## 1. User Journey Overview

```
                          ORCHESTRATION FLOW

  +----------------+      +------------------+      +------------------+
  |   USER INTENT  | ---> |  TASK ANALYSIS   | ---> |    DELEGATION    |
  |                |      |                  |      |                  |
  | "Build feature |      | - Parse subtasks |      | - Match rules    |
  |  X with tests" |      | - Identify scope |      | - Estimate save  |
  +----------------+      +------------------+      | - Plan parallel  |
                                                    +------------------+
                                                            |
                                                            v
  +----------------+      +------------------+      +------------------+
  |    RESULTS     | <--- |   MONITORING     | <--- |   EXECUTION      |
  |                |      |                  |      |                  |
  | - Summary      |      | - Live status    |      | - Spawn agents   |
  | - Files        |      | - Progress bars  |      | - Track progress |
  | - Savings      |      | - Error alerts   |      | - Collect output |
  +----------------+      +------------------+      +------------------+
```

---

## 2. Orchestration Initiation

### 2.1 Recommended Approach: Explicit Command

**Primary Entry Point:**
```
/harness-orchestrate "Build user authentication with JWT, tests, and docs"
```

**Rationale:** Explicit commands give users control over when orchestration happens. This avoids unexpected behavior and context consumption from unwanted delegation.

### 2.2 Alternative Entry Points

**A. Feature-Triggered Orchestration:**
```
/harness-feature-add "User Auth" -s "Explore patterns" -s "Implement" -s "Write tests" --orchestrate
```
The `--orchestrate` flag enables automatic delegation analysis when adding features.

**B. Context-Aware Suggestion:**
When context exceeds 50% usage and delegatable tasks are detected:
```
[ * ] Context at 62% | Delegation could save ~35K tokens
      Run /harness-orchestrate to optimize remaining work
```

**C. Session Setting (Toggle):**
```
/harness-settings orchestration on
```
When enabled, harness automatically suggests orchestration for new features.

### 2.3 Design Decision

**Recommended MVP:** Start with explicit `/harness-orchestrate` command only.

**Why:**
- Lowest risk of unexpected behavior
- Clear user mental model
- Easy to explain and document
- Can add automatic triggers in v1.1

---

## 3. Orchestration Planning Screen

When user invokes orchestration, show a planning summary before execution:

### 3.1 Planning Output Format

```
================================================================================
                         ORCHESTRATION PLAN
================================================================================

Task: Build user authentication with JWT, tests, and docs

+----------------------------------------------------------------------------+
| ANALYSIS                                                                    |
+----------------------------------------------------------------------------+
| Detected 5 subtasks:                                                        |
|   1. Explore existing auth patterns                                         |
|   2. Implement JWT authentication service                                   |
|   3. Write unit tests for auth module                                       |
|   4. Add E2E tests for login flow                                           |
|   5. Document authentication API                                            |
+----------------------------------------------------------------------------+

+----------------------------------------------------------------------------+
| DELEGATION PLAN                                                             |
+----------------------------------------------------------------------------+
| DELEGATE (via subagents):                                                   |
|   [explore]  Explore existing auth patterns .............. ~22K tokens saved|
|   [test]     Write unit tests for auth module ............ ~13K tokens saved|
|   [test]     Add E2E tests for login flow ................ ~13K tokens saved|
|   [document] Document authentication API ................. ~9K tokens saved |
|                                                                             |
| KEEP (main agent):                                                          |
|   [core]     Implement JWT authentication service                           |
|                                                                             |
| Parallel execution: 2 subagents max (configurable)                          |
+----------------------------------------------------------------------------+

+----------------------------------------------------------------------------+
| ESTIMATED SAVINGS                                                           |
+----------------------------------------------------------------------------+
|   Delegated work:    ~57K tokens                                            |
|   Summary returns:   ~14K tokens                                            |
|   NET SAVINGS:       ~43K tokens (75% reduction on delegated work)          |
+----------------------------------------------------------------------------+

Proceed with orchestration? [Y/n/edit]
  Y     - Execute plan
  n     - Cancel
  edit  - Modify which tasks to delegate
```

### 3.2 Plan Editing Mode

If user chooses `edit`:

```
================================================================================
                       EDIT DELEGATION PLAN
================================================================================

For each subtask, choose: [d]elegate, [k]eep in main, [s]kip entirely

  1. Explore existing auth patterns
     Current: DELEGATE (explore) | Est. savings: 22K tokens
     Choice [d/k/s]: _

  2. Implement JWT authentication service
     Current: KEEP (core implementation)
     Choice [d/k/s]: _

  3. Write unit tests for auth module
     Current: DELEGATE (test) | Est. savings: 13K tokens
     Choice [d/k/s]: _

  4. Add E2E tests for login flow
     Current: DELEGATE (test) | Est. savings: 13K tokens
     Choice [d/k/s]: _

  5. Document authentication API
     Current: DELEGATE (document) | Est. savings: 9K tokens
     Choice [d/k/s]: _

[Enter] when done, [c] to cancel
```

---

## 4. Visibility During Execution

### 4.1 Live Status Display

During orchestration, show a compact live status panel:

```
================================================================================
                      ORCHESTRATION IN PROGRESS
================================================================================

Feature: User Authentication (F-012)
Started: 14:32 UTC | Elapsed: 2m 15s

SUBAGENT STATUS:
  [####------] explore    | Exploring auth patterns      | 40% complete
  [##########] test       | Writing unit tests           | DONE (8 tests)
  [waiting]   test        | E2E tests                    | Queued (after explore)
  [waiting]   document    | API documentation            | Queued

MAIN AGENT:
  [pending]   Implement JWT service                      | After exploration

METRICS:
  Context saved so far: ~13K tokens
  Subagent outputs collected: 1/4

--------------------------------------------------------------------------------
Commands: [p]ause  [r]esume  [s]kip current  [a]bort  [v]iew details
================================================================================
```

### 4.2 Status States

| State | Icon | Description |
|-------|------|-------------|
| Running | `[####----]` | Progress bar showing completion |
| Done | `[##########]` | Completed with checkmark |
| Waiting | `[waiting]` | Queued for execution |
| Paused | `[paused]` | User paused execution |
| Failed | `[FAILED]` | Error occurred (red) |
| Skipped | `[skipped]` | User chose to skip |

### 4.3 Subagent Output Streaming (Optional)

For users wanting more detail, `[v]iew details` shows:

```
================================================================================
                      SUBAGENT: explore (auth patterns)
================================================================================

Status: Running | Progress: 40%

Live Output:
  > Reading auth/middleware.py...
  > Found decorator pattern: @require_auth
  > Reading auth/jwt_handler.py...
  > Analyzing token validation flow...

Files Examined: 4
Patterns Found: 2
Est. Completion: 45 seconds

[b] Back to overview | [f] Follow mode (tail output)
================================================================================
```

---

## 5. Control and Override

### 5.1 Control Commands During Execution

| Command | Shortcut | Effect |
|---------|----------|--------|
| Pause | `p` | Pause all subagents, preserve state |
| Resume | `r` | Continue paused orchestration |
| Skip | `s` | Skip current subagent, move to next |
| Abort | `a` | Stop all subagents, show partial results |
| View | `v` | Show detailed subagent output |
| Adjust | `j` | Modify parallelism on the fly |

### 5.2 Pause Behavior

When paused:
```
================================================================================
                      ORCHESTRATION PAUSED
================================================================================

Reason: User requested pause
Time paused: 14:35 UTC

In-flight work:
  - explore: Saved state at file #4 (can resume)
  - test: Completed, results cached

Options:
  [r] Resume from current point
  [s] Skip current subagent, continue with next
  [a] Abort and show results so far
  [m] Return to main agent with partial results

================================================================================
```

### 5.3 Skip Specific Delegation

Users can skip a queued task before it starts:
```
/harness-orchestrate-skip "E2E tests"
```

Or during execution, pressing `s` prompts:
```
Skip which task?
  1. [running] Exploring auth patterns - Cannot skip (in progress)
  2. [waiting] E2E tests             - Press 2 to skip
  3. [waiting] API documentation     - Press 3 to skip

Choice: _
```

### 5.4 Adjust Parallelism

```
/harness-orchestrate-parallel 3
```
Or during execution, `j` prompts:
```
Current parallel limit: 2 subagents
New limit [1-5]: _
```

---

## 6. Results Presentation

### 6.1 Completion Summary

After orchestration completes:

```
================================================================================
                      ORCHESTRATION COMPLETE
================================================================================

Feature: User Authentication (F-012)
Duration: 8m 32s

SUMMARY BY SUBAGENT:
--------------------------------------------------------------------------------
[explore] Explore auth patterns                                     SUCCESS
  - Found 3 existing auth files
  - Identified @require_auth decorator pattern
  - Discovered JWT helper in utils/tokens.py
  Files examined: 12 | Summary: 342 words

[test] Unit tests for auth module                                   SUCCESS
  - Created 8 unit tests in tests/unit/test_auth.py
  - Coverage: +18% on auth module (now 92%)
  - All tests passing
  Files created: 1 | Summary: 287 words

[test] E2E tests for login flow                                     SUCCESS
  - Created 4 E2E tests in e2e/tests/test_login.py
  - Tests: login_success, login_invalid_password, login_rate_limit, logout
  Files created: 1 | Summary: 198 words

[document] API documentation                                        SUCCESS
  - Created docs/api/authentication.md
  - Documented 5 endpoints with examples
  - Added to docs/api/README.md index
  Files created: 1 | Files modified: 1 | Summary: 412 words

--------------------------------------------------------------------------------
MAIN AGENT WORK:
--------------------------------------------------------------------------------
  - Implement JWT service: Ready to begin with exploration insights

================================================================================
                           METRICS
================================================================================

Context Efficiency:
  Traditional execution:        ~95,000 tokens (estimated)
  With orchestration:           ~38,000 tokens
  TOKENS SAVED:                 ~57,000 (60% reduction)

Files Created:      4
Files Modified:     1
Tests Added:        12 (8 unit + 4 E2E)
Coverage Delta:     +18%

================================================================================
                         COLLECTED INSIGHTS
================================================================================

Key findings from exploration:
  1. Existing auth uses decorator pattern - recommend same approach
  2. JWT handler exists in utils/tokens.py - extend rather than duplicate
  3. Rate limiting middleware already present - can hook into it

Recommended next step:
  Implement JWT authentication service using existing patterns.
  Start with: auth/jwt_service.py

================================================================================

View full subagent outputs?  [y/N]
Continue to main implementation? [Y/n]
```

### 6.2 Partial Results (After Abort/Failure)

If orchestration is aborted or a subagent fails:

```
================================================================================
                      ORCHESTRATION INCOMPLETE
================================================================================

Status: Aborted by user after 4m 12s

COMPLETED (results available):
  [explore] Auth patterns - SUCCESS (insights collected)
  [test] Unit tests       - SUCCESS (8 tests created)

INCOMPLETE:
  [test] E2E tests        - ABORTED (was 60% complete)
  [document] API docs     - NOT STARTED

PARTIAL RESULTS FROM ABORTED TASK:
  E2E tests: 2 of 4 tests written
  Files: e2e/tests/test_login.py (partial)
  Note: File may need cleanup or completion

CONTEXT SAVED: ~30,000 tokens (partial savings)

Options:
  [c] Continue with completed results only
  [r] Resume E2E tests from checkpoint
  [f] Finish E2E tests in main agent
================================================================================
```

---

## 7. Error Handling

### 7.1 Subagent Failure

If a subagent fails:

```
================================================================================
                      SUBAGENT FAILURE
================================================================================

Task: Write unit tests for auth module
Subagent: test
Error: Unable to import auth module - missing dependency 'pyjwt'

Details:
  File: tests/unit/test_auth.py (partial, 3 of 8 tests)
  Last successful: test_login_valid_credentials

Options:
  [r] Retry after installing dependency
  [s] Skip this task, continue orchestration
  [f] Fix in main agent, then resume
  [a] Abort orchestration

Suggested fix:
  pip install pyjwt

Run fix and retry? [y/N]: _
================================================================================
```

### 7.2 Multiple Failures

If multiple subagents fail:

```
================================================================================
                      ORCHESTRATION ISSUES
================================================================================

2 of 4 subagents encountered errors:

  [FAILED] test: Missing dependency 'pyjwt'
  [FAILED] document: No docs/ directory found

Healthy tasks:
  [SUCCESS] explore: Completed successfully
  [WAITING] test-e2e: Queued

Recommendations:
  1. Install missing dependency: pip install pyjwt
  2. Create docs directory: mkdir -p docs/api

Options:
  [f] Apply fixes and retry failed tasks
  [c] Continue with healthy tasks only
  [a] Abort and return to main agent
================================================================================
```

### 7.3 Error Recovery

```
/harness-orchestrate-retry "test"
```

Retries the failed subagent from the beginning or last checkpoint.

---

## 8. Commands Reference

### 8.1 Primary Commands

| Command | Description |
|---------|-------------|
| `/harness-orchestrate "<task>"` | Start orchestrated execution |
| `/harness-orchestrate-status` | Show current orchestration status |
| `/harness-orchestrate-pause` | Pause orchestration |
| `/harness-orchestrate-resume` | Resume paused orchestration |
| `/harness-orchestrate-abort` | Abort and show partial results |

### 8.2 Control Commands

| Command | Description |
|---------|-------------|
| `/harness-orchestrate-skip "<task>"` | Skip a specific queued task |
| `/harness-orchestrate-retry "<task>"` | Retry a failed task |
| `/harness-orchestrate-parallel <n>` | Set parallelism (1-5) |

### 8.3 Configuration Commands

| Command | Description |
|---------|-------------|
| `/harness-settings orchestration on|off` | Toggle orchestration suggestions |
| `/harness-settings parallel-limit <n>` | Default parallelism |
| `/harness-settings auto-delegate on|off` | Auto-suggest delegation |

---

## 9. Example Session Transcript

```
User: /harness-orchestrate "Add password reset functionality with email, tests, and docs"

Claude: Analyzing task for orchestration...

================================================================================
                         ORCHESTRATION PLAN
================================================================================

Task: Add password reset functionality with email, tests, and docs

Detected 5 subtasks:
  1. Explore existing password/email patterns
  2. Implement password reset service
  3. Create email templates for reset flow
  4. Write unit tests for password reset
  5. Document password reset API

DELEGATION PLAN:
  DELEGATE:
    [explore]  Explore password/email patterns ............ ~22K tokens saved
    [test]     Write unit tests ........................... ~13K tokens saved
    [document] Document API ............................... ~9K tokens saved

  KEEP (main agent):
    [core]     Implement password reset service
    [core]     Create email templates

ESTIMATED SAVINGS: ~44K tokens (65% reduction on delegated work)

Proceed? [Y/n/edit]: Y

Claude: Starting orchestration...

================================================================================
                      ORCHESTRATION IN PROGRESS
================================================================================

SUBAGENT STATUS:
  [####------] explore    | Scanning password patterns   | 40%
  [waiting]   test        | Unit tests                   | Queued
  [waiting]   document    | API docs                     | Queued

MAIN AGENT: Waiting for exploration results...

User: p

Claude: Orchestration paused. [r]esume [s]kip [a]bort?

User: r

Claude: Resuming...

[... time passes ...]

================================================================================
                      ORCHESTRATION COMPLETE
================================================================================

Duration: 6m 45s

COMPLETED:
  [explore] Password patterns - Found existing reset flow in legacy code
  [test] Unit tests - Created 6 tests, all passing
  [document] API docs - Created docs/api/password-reset.md

INSIGHTS:
  - Legacy reset flow uses time-based tokens (recommend JWT instead)
  - Email service wrapper exists in services/email.py
  - Rate limiting recommended for reset endpoint

TOKENS SAVED: ~44,000 (65% reduction)

Ready to implement password reset service. Key files to modify:
  - auth/password_reset.py (new)
  - services/email.py (add reset template)
  - routes/auth.py (add reset endpoints)

Shall I proceed with implementation? [Y/n]

User: Y

Claude: Beginning implementation using subagent insights...
```

---

## 10. Minimal Viable UX (Simplest Path to Value)

For the initial release, implement this minimal set:

### 10.1 MVP Commands

1. **`/harness-orchestrate "<task>"`** - Start orchestration with plan display
2. **`/harness-orchestrate-status`** - View current status
3. **`/harness-orchestrate-abort`** - Stop and show results

### 10.2 MVP Display

**Planning:** Show task breakdown and estimated savings, auto-proceed after 5s.

**Execution:** Simple text updates:
```
Orchestrating: Add password reset...
  [DONE] Exploration (22K saved)
  [RUNNING] Unit tests...
  [QUEUED] Documentation
```

**Results:** Summary of files created, tokens saved, insights collected.

### 10.3 MVP Error Handling

On failure: Show error, offer to continue without failed task or abort.

### 10.4 MVP Deferred Features

- Interactive plan editing
- Pause/resume (just abort)
- Parallelism adjustment
- Detailed streaming output
- Checkpoint-based resume

---

## 11. User Stories and Acceptance Criteria

### US-1: Start Orchestrated Task

**As a** developer using claude-harness
**I want to** orchestrate a complex task with automatic delegation
**So that** I can preserve context for more important work

**Acceptance Criteria:**
- [ ] `/harness-orchestrate "<task>"` parses task into subtasks
- [ ] Plan shows which tasks will be delegated vs kept
- [ ] Estimated token savings displayed
- [ ] User can proceed or cancel
- [ ] Execution begins after confirmation

### US-2: View Orchestration Status

**As a** developer running an orchestrated task
**I want to** see the current status of all subagents
**So that** I know what is happening

**Acceptance Criteria:**
- [ ] Status shows each subagent with state (running/done/waiting/failed)
- [ ] Progress indication for running subagents
- [ ] Summary of results collected so far
- [ ] Context savings displayed

### US-3: Abort Orchestration

**As a** developer who needs to stop
**I want to** abort orchestration and keep partial results
**So that** completed work is not lost

**Acceptance Criteria:**
- [ ] `/harness-orchestrate-abort` stops all subagents
- [ ] Completed results are preserved and displayed
- [ ] Partial files are flagged for review
- [ ] User can continue with partial results

### US-4: Handle Subagent Failure

**As a** developer whose subagent encountered an error
**I want to** understand the failure and choose how to proceed
**So that** one failure does not block all work

**Acceptance Criteria:**
- [ ] Error message clearly explains failure
- [ ] Suggested fix provided when possible
- [ ] Options: retry, skip, fix manually, abort
- [ ] Other subagents continue if possible

### US-5: View Orchestration Results

**As a** developer after orchestration completes
**I want to** see a summary of all work done
**So that** I can verify results and continue

**Acceptance Criteria:**
- [ ] Each subagent's output summarized
- [ ] Files created/modified listed
- [ ] Total token savings displayed
- [ ] Key insights highlighted
- [ ] Recommended next steps provided

---

## 12. Edge Cases and Error States

### 12.1 No Delegatable Tasks

```
================================================================================
                         ORCHESTRATION ANALYSIS
================================================================================

Task: Implement core authentication logic

Analysis: This task appears to be core implementation work with no clear
delegation candidates.

Recommendation: Execute directly without orchestration.

Proceed without orchestration? [Y/n]
================================================================================
```

### 12.2 Context Already Low

```
================================================================================
                         ORCHESTRATION NOTE
================================================================================

Current context usage: 12% (~24K tokens used)

Orchestration provides most value when context > 50%. With current low usage,
delegation overhead may not be worthwhile.

Proceed anyway? [y/N]
================================================================================
```

### 12.3 All Subagents Fail

```
================================================================================
                      ORCHESTRATION FAILED
================================================================================

All 3 subagents encountered errors:
  [FAILED] explore: Network timeout
  [FAILED] test: Missing pytest
  [FAILED] document: Permission denied on docs/

No results to collect. Returning to main agent.

Suggestion: Fix environment issues and retry, or proceed manually.
================================================================================
```

### 12.4 Task Too Vague

```
================================================================================
                         ORCHESTRATION ANALYSIS
================================================================================

Task: "Make it work better"

Unable to identify specific subtasks from this description.

Please provide more detail:
  - What specific functionality needs improvement?
  - What kind of work is needed (tests, docs, refactoring)?
  - Which parts of the codebase are involved?

Example: "Improve authentication with better error handling, add tests, update docs"
================================================================================
```

---

## 13. Design Recommendations Summary

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| **Initiation** | Explicit command only (MVP) | Control, clarity, low risk |
| **Planning** | Show full plan, require confirmation | Transparency, user control |
| **Status** | Compact live updates | Balance info vs. noise |
| **Control** | Abort only (MVP), add pause later | Simplicity first |
| **Results** | Structured summary with savings | Value visibility |
| **Errors** | Per-task handling, continue-if-possible | Resilience |

---

## 14. Future Enhancements (Post-MVP)

1. **Orchestration Templates** - Pre-built orchestration plans for common tasks
2. **Learning Mode** - System learns which tasks users prefer to delegate
3. **Dependency Graph** - Visual representation of task dependencies
4. **Collaborative Orchestration** - Multiple users viewing same orchestration
5. **Scheduled Orchestration** - Queue orchestration for later execution
6. **Cost Tracking** - Show actual API cost savings, not just token estimates

---

## Appendix A: Command Quick Reference

```
ORCHESTRATION COMMANDS
======================

Start/Stop:
  /harness-orchestrate "<task>"    Start orchestrated execution
  /harness-orchestrate-abort       Stop and show results

Status:
  /harness-orchestrate-status      Current status
  /harness-orchestrate-results     Last orchestration results

Control (Post-MVP):
  /harness-orchestrate-pause       Pause execution
  /harness-orchestrate-resume      Resume paused
  /harness-orchestrate-skip "<t>"  Skip specific task
  /harness-orchestrate-retry "<t>" Retry failed task
  /harness-orchestrate-parallel N  Set parallelism

Settings:
  /harness-settings orchestration on|off
  /harness-settings parallel-limit N
  /harness-settings auto-delegate on|off
```

---

## Appendix B: Status Bar Reference

```
ORCHESTRATION STATUS LINE FORMAT
================================

Standard:
  [ORC] Feature-Name | 3/5 tasks | ~45K saved | 4m elapsed

With issues:
  [ORC!] Feature-Name | 2/5 tasks | 1 failed | 2m elapsed

Paused:
  [ORC||] Feature-Name | PAUSED | 2/5 tasks done

Complete:
  [ORC OK] Feature-Name | 5/5 done | ~62K saved | 8m total
```

---

*End of UX Design Document*
