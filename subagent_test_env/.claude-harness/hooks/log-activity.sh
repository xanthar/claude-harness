#!/bin/bash
# Claude Harness - Activity Logger
# Logs tool usage for session tracking

TOOL_NAME="$1"
TOOL_INPUT="$2"
LOG_DIR=".claude-harness/session-history"
LOG_FILE="$LOG_DIR/activity-$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
echo "[$(date -Iseconds)] $TOOL_NAME: ${TOOL_INPUT:0:200}" >> "$LOG_FILE"
