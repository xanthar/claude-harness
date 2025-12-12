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
