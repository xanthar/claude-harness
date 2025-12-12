#!/bin/bash
# Claude Harness - Git Safety Hook
# Blocks dangerous git operations

INPUT="$1"
PROTECTED_BRANCHES="main master"

# Block direct commits to protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$INPUT" | grep -qE "git commit.*$branch"; then
        echo "BLOCKED: Cannot commit directly to protected branch '$branch'. Create a feature branch first."
        exit 1
    fi
done

# Block force pushes to protected branches
for branch in $PROTECTED_BRANCHES; do
    if echo "$INPUT" | grep -qE "git push.*(-f|--force).*$branch"; then
        echo "BLOCKED: Cannot force push to protected branch '$branch'."
        exit 1
    fi
done

# Block backup branch deletion
if echo "$INPUT" | grep -qiE "git branch -[dD].*[Bb]ackup"; then
    echo "BLOCKED: Cannot delete backup branches."
    exit 1
fi

exit 0
