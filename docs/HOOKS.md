# Claude Code Hooks Setup

This guide explains how to configure Claude Code hooks to integrate with Claude Harness for automatic tracking and safety enforcement.

## What Are Claude Code Hooks?

Claude Code hooks are shell commands that execute automatically in response to events:
- **PreToolUse**: Before a tool (Bash, Read, Write, etc.) executes
- **PostToolUse**: After a tool completes
- **Stop**: When Claude Code stops (end of session)

## Hook Input Format

**IMPORTANT**: Hooks receive input via **stdin as JSON**, not environment variables. The JSON structure is:

```json
{
  "tool_name": "Read",
  "tool_input": {
    "file_path": "/path/to/file.py"
  }
}
```

For Bash tools:
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la"
  }
}
```

Use `jq` to parse the JSON in your hook scripts.

## Hook Configuration Format

Hooks must be configured with the nested `hooks` array structure:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/check-git-safety.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/track-read.sh"
          }
        ]
      }
    ]
  }
}
```

## Hook Configuration Locations

Hooks can be configured at three levels:

1. **Global** (`~/.claude/settings.json`) - Applies to all projects
2. **Project** (`.claude/settings.json`) - Applies to specific project
3. **Local** (`.claude/settings.local.json`) - User-specific, not committed

## Setting Up Harness Hooks

### Automatic Setup (Recommended)

When you run `claude-harness init`, hooks are automatically configured in `.claude/settings.json`.

### Manual Setup

Create or update `.claude/settings.json` in your project:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/check-git-safety.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/track-read.sh"
          }
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/track-write.sh"
          }
        ]
      },
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/track-edit.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/log-activity.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude-harness/hooks/session-stop.sh"
          }
        ]
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

## Hook Scripts

Claude Harness generates these hook scripts in `.claude-harness/hooks/`:

### check-git-safety.sh (PreToolUse)

Blocks dangerous git operations on protected branches:
- Commits directly to main/master
- Force pushes to protected branches
- Deleting backup branches

```bash
#!/bin/bash
# Claude Harness - Git Safety Hook (PreToolUse)
# Blocks commits to protected branches
# Input: JSON via stdin with tool_input.command

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract command
COMMAND=$(echo "$INPUT_JSON" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Skip if no command
[ -z "$COMMAND" ] && exit 0

# Protected branches
PROTECTED_BRANCHES="main master"

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

# Block commits on protected branches
for branch in $PROTECTED_BRANCHES; do
    if [ "$CURRENT_BRANCH" = "$branch" ]; then
        if echo "$COMMAND" | grep -qE "^git commit"; then
            echo "BLOCKED: Cannot commit on protected branch '$branch'." >&2
            exit 2  # Exit code 2 blocks the action
        fi
    fi
done

exit 0
```

### track-read.sh (PostToolUse)

Tracks file reads for context estimation:

```bash
#!/bin/bash
# Claude Harness - Track File Read (PostToolUse)
# Input: JSON via stdin with tool_input.file_path

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Skip if no file path or harness not initialized
[ -z "$FILE_PATH" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

# Get file size for token estimation
if [ -f "$FILE_PATH" ]; then
    CHAR_COUNT=$(wc -c < "$FILE_PATH" 2>/dev/null || echo 1000)
    claude-harness context track-file "$FILE_PATH" "$CHAR_COUNT" 2>/dev/null || true
fi

exit 0
```

### track-write.sh (PostToolUse)

Tracks file writes and adds to modified files list:

```bash
#!/bin/bash
# Claude Harness - Track File Write (PostToolUse)
# Input: JSON via stdin with tool_input.file_path

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract file path and content
FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
CONTENT=$(echo "$INPUT_JSON" | jq -r '.tool_input.content // empty' 2>/dev/null)

# Skip if no file path or harness not initialized
[ -z "$FILE_PATH" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

# Skip harness internal files
case "$FILE_PATH" in
    .claude-harness/*|.git/*|*.log|*.pyc|__pycache__/*|node_modules/*)
        exit 0
        ;;
esac

# Track as modified file
claude-harness progress file "$FILE_PATH" 2>/dev/null || true

# Track context usage (use content length if available)
if [ -n "$CONTENT" ]; then
    CHAR_COUNT=${#CONTENT}
else
    CHAR_COUNT=$(wc -c < "$FILE_PATH" 2>/dev/null || echo 1000)
fi
claude-harness context track-file "$FILE_PATH" "$CHAR_COUNT" 2>/dev/null || true

exit 0
```

### log-activity.sh (PostToolUse)

Logs Bash commands for session tracking:

```bash
#!/bin/bash
# Claude Harness - Log Activity (PostToolUse)
# Input: JSON via stdin with tool_input.command

# Read JSON from stdin
INPUT_JSON=$(cat)

# Extract command
COMMAND=$(echo "$INPUT_JSON" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Skip if no command or harness not initialized
[ -z "$COMMAND" ] && exit 0
[ -f ".claude-harness/config.json" ] || exit 0

# Track command execution
CHAR_COUNT=${#COMMAND}
claude-harness context track-command "$CHAR_COUNT" 2>/dev/null || true

exit 0
```

### session-stop.sh (Stop)

Shows session summary when Claude Code stops:

```bash
#!/bin/bash
# Claude Harness - Session Stop Hook
# Shows context and progress summary

[ -f ".claude-harness/config.json" ] || exit 0

echo "=== Claude Harness Session Summary ==="
claude-harness context show 2>/dev/null || true
echo "---"
claude-harness progress show 2>/dev/null || true

exit 0
```

## Hook Exit Codes

| Exit Code | Effect |
|-----------|--------|
| 0 | Allow operation to proceed |
| 2 | Block operation (PreToolUse only) |
| Other | Allow operation (logged as warning) |

**Important**: Only exit code **2** blocks operations in PreToolUse hooks.

## Testing Hooks

Test your hooks manually by piping JSON to them:

```bash
# Test file read tracking
echo '{"tool_input": {"file_path": "app.py"}}' | .claude-harness/hooks/track-read.sh

# Test git safety (should block on main branch)
echo '{"tool_input": {"command": "git commit -m test"}}' | .claude-harness/hooks/check-git-safety.sh

# Check context tracking worked
claude-harness context show
```

## Troubleshooting

### Hooks Not Running

1. Check file permissions: `chmod +x .claude-harness/hooks/*.sh`
2. Verify settings.json syntax: `cat .claude/settings.json | jq .`
3. Ensure `jq` is installed: `which jq` (install with `apt install jq` or `brew install jq`)
4. Check Claude Code logs for errors

### Context Showing 0

If context shows 0 files read/commands despite activity:

1. Verify hooks are using the correct JSON input format (stdin, not env vars)
2. Check that hook scripts use `jq` to parse the JSON
3. Run hooks manually to test: `echo '{"tool_input": {"file_path": "test.py"}}' | .claude-harness/hooks/track-read.sh`

### Performance Issues

If hooks slow down Claude Code:

1. Keep hook scripts lightweight
2. Use early exit for skipped cases
3. Run non-critical logging in background: `command &`

### Hook Errors Blocking Work

If a broken hook blocks all operations:

1. Remove or fix the hook in settings.json
2. Or temporarily rename `.claude/settings.json`

## Best Practices

1. **Use JSON parsing** - Always use `jq` to parse stdin, never rely on env vars
2. **Test locally first** - Pipe test JSON to hooks before deploying
3. **Exit code 2 to block** - Only exit code 2 blocks PreToolUse hooks
4. **Keep hooks fast** - Slow hooks degrade UX
5. **Use conditional checks** - `[ -f ".claude-harness/config.json" ] || exit 0`
6. **Project-level hooks** - Avoid global hooks that might break other projects

## Disabling Hooks

To temporarily disable all hooks:

```bash
# Rename settings file
mv .claude/settings.json .claude/settings.json.disabled

# Re-enable
mv .claude/settings.json.disabled .claude/settings.json
```

Or disable specific hooks by removing them from the JSON.

## Dependencies

The hook scripts require:
- `jq` - For JSON parsing (install: `apt install jq` or `brew install jq`)
- `claude-harness` - For context/progress tracking

## Migration from Old Format

If you have hooks using the old `$TOOL_INPUT` environment variable format, update them to:

1. Read JSON from stdin: `INPUT_JSON=$(cat)`
2. Parse with jq: `FILE_PATH=$(echo "$INPUT_JSON" | jq -r '.tool_input.file_path // empty')`
3. Use the nested `hooks` array format in settings.json
