#!/bin/bash
# Example session-start hook for ccpm.
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'not a git repo')"
echo "Last 3 commits:"
git log --oneline -3 2>/dev/null || echo "  (no git history)"
echo "Uncommitted changes: $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
