# Claude Code Hooks Setup

This guide explains how to configure Claude Code hooks to integrate with Claude Harness for automatic tracking and safety enforcement.

## What Are Claude Code Hooks?

Claude Code hooks are shell commands that execute automatically in response to events:
- **PreToolUse**: Before a tool (Bash, Read, Write, etc.) executes
- **PostToolUse**: After a tool completes
- **Stop**: When Claude Code stops (end of session)

## Hook Configuration Locations

Hooks can be configured at three levels:

1. **Global** (`~/.claude/settings.json`) - Applies to all projects
2. **Project** (`.claude/settings.json`) - Applies to specific project
3. **Local** (`.claude/settings.local.json`) - User-specific, not committed

## Setting Up Harness Hooks

### Option 1: Project-Level (Recommended)

Create or update `.claude/settings.json` in your project:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": ".claude-harness/hooks/check-git-safety.sh \"$TOOL_INPUT\""
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read",
        "command": "claude-harness context track-file \"$TOOL_INPUT\" $(wc -c < \"$TOOL_INPUT\" 2>/dev/null || echo 0)"
      },
      {
        "matcher": "Write",
        "command": "claude-harness context track-file \"$TOOL_INPUT\" $(wc -c < \"$TOOL_INPUT\" 2>/dev/null || echo 0) --write"
      },
      {
        "matcher": "Bash",
        "command": ".claude-harness/hooks/log-activity.sh \"Bash\" \"$TOOL_INPUT\""
      }
    ],
    "Stop": [
      {
        "command": "claude-harness context show --full && claude-harness progress show"
      }
    ]
  }
}
```

### Option 2: Global Hooks

For hooks you want on ALL projects, add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "if [ -f .claude-harness/hooks/check-git-safety.sh ]; then .claude-harness/hooks/check-git-safety.sh \"$TOOL_INPUT\"; fi"
      }
    ]
  }
}
```

## Hook Scripts

Claude Harness generates these hook scripts in `.claude-harness/hooks/`:

### check-git-safety.sh

Blocks dangerous git operations:
- Commits directly to protected branches (main/master)
- Force pushes to protected branches
- Deleting backup branches

```bash
#!/bin/bash
INPUT="$1"
PROTECTED_BRANCHES="main master"

# Block direct commits to protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$INPUT" | grep -qE "git commit.*$branch"; then
        echo "BLOCKED: Cannot commit directly to protected branch '$branch'."
        exit 1
    fi
done

exit 0
```

### log-activity.sh

Logs tool usage for session tracking:

```bash
#!/bin/bash
TOOL_NAME="$1"
TOOL_INPUT="$2"
LOG_DIR=".claude-harness/session-history"
LOG_FILE="$LOG_DIR/activity-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
echo "[$(date -Iseconds)] $TOOL_NAME: ${TOOL_INPUT:0:200}" >> "$LOG_FILE"
```

### track-progress.sh

Automatically tracks modified files in progress.md:

```bash
#!/bin/bash
# Claude Harness - Auto Progress Tracker
# Automatically tracks modified files in progress.md

FILEPATH="$1"
ACTION="${2:-write}"  # write or edit

# Skip if not a harness project
[ -f ".claude-harness/config.json" ] || exit 0

# Skip harness internal files and common non-code files
case "$FILEPATH" in
    .claude-harness/*|.git/*|*.log|*.pyc|__pycache__/*|node_modules/*|.env*)
        exit 0
        ;;
esac

# Track the file modification
claude-harness progress file "$FILEPATH" 2>/dev/null || true
```

## Context Tracking Hooks

To track context usage via hooks:

### Track File Reads

```json
{
  "matcher": "Read",
  "command": "claude-harness context track-file \"$TOOL_INPUT\" $(stat -c%s \"$TOOL_INPUT\" 2>/dev/null || stat -f%z \"$TOOL_INPUT\" 2>/dev/null || echo 0)"
}
```

### Track File Writes

```json
{
  "matcher": "Write",
  "command": "claude-harness context track-file \"$TOOL_OUTPUT\" $(stat -c%s \"$TOOL_OUTPUT\" 2>/dev/null || echo 0) --write"
}
```

### Track Commands

```json
{
  "matcher": "Bash",
  "command": "claude-harness context track-command \"$TOOL_INPUT\""
}
```

## Complete Example Configuration

Here's a full `.claude/settings.json` with all recommended hooks:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "[ -f .claude-harness/hooks/check-git-safety.sh ] && .claude-harness/hooks/check-git-safety.sh \"$TOOL_INPUT\""
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read",
        "command": "[ -f .claude-harness/config.json ] && claude-harness context track-file \"$TOOL_INPUT\" $(wc -c < \"$TOOL_INPUT\" 2>/dev/null || echo 1000)"
      },
      {
        "matcher": "Write",
        "command": "[ -f .claude-harness/hooks/track-progress.sh ] && .claude-harness/hooks/track-progress.sh \"$TOOL_INPUT\" write"
      },
      {
        "matcher": "Edit",
        "command": "[ -f .claude-harness/hooks/track-progress.sh ] && .claude-harness/hooks/track-progress.sh \"$TOOL_INPUT\" edit"
      },
      {
        "matcher": "Bash",
        "command": "[ -f .claude-harness/hooks/log-activity.sh ] && .claude-harness/hooks/log-activity.sh \"Bash\" \"$TOOL_INPUT\""
      }
    ],
    "Stop": [
      {
        "command": "[ -f .claude-harness/config.json ] && (claude-harness context show; echo '---'; claude-harness progress show)"
      }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(claude-harness:*)"
    ]
  }
}
```

## Hook Variables

Available variables in hooks:

| Variable | Description |
|----------|-------------|
| `$TOOL_NAME` | Name of the tool (Bash, Read, Write, etc.) |
| `$TOOL_INPUT` | Input provided to the tool |
| `$TOOL_OUTPUT` | Output from the tool (PostToolUse only) |
| `$EXIT_CODE` | Exit code from tool (PostToolUse only) |

## Blocking vs Logging

- **Return exit code 1** from PreToolUse to BLOCK the operation
- **Return exit code 0** to allow the operation
- PostToolUse hooks cannot block, only log/track

## Testing Hooks

Test your hooks manually:

```bash
# Test git safety
.claude-harness/hooks/check-git-safety.sh "git commit -m 'test' main"
# Should output: BLOCKED: Cannot commit directly to protected branch 'main'.

# Test context tracking
claude-harness context track-file README.md 5000
claude-harness context show --full
```

## Troubleshooting

### Hooks Not Running

1. Check file permissions: `chmod +x .claude-harness/hooks/*.sh`
2. Verify settings.json syntax: `cat .claude/settings.json | jq .`
3. Check Claude Code logs for errors

### Performance Issues

If hooks slow down Claude Code:
1. Use conditional checks: `[ -f .claude-harness/config.json ] && ...`
2. Keep hook scripts lightweight
3. Use background logging: `command &`

### Hook Errors Blocking Work

If a broken hook blocks all operations:
1. Remove or fix the hook in settings.json
2. Or temporarily rename `.claude/settings.json`

## Best Practices

1. **Always use conditionals** - Check if harness exists before running harness commands
2. **Keep hooks fast** - Slow hooks degrade UX
3. **Test locally first** - Verify hooks work before adding to settings
4. **Use project-level hooks** - Avoid global hooks that might break other projects
5. **Log errors** - Redirect stderr to a log file for debugging

## Disabling Hooks

To temporarily disable all hooks:

```bash
# Rename settings file
mv .claude/settings.json .claude/settings.json.disabled

# Re-enable
mv .claude/settings.json.disabled .claude/settings.json
```

Or disable specific hooks by removing them from the JSON.
