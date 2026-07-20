#!/usr/bin/env bash
# pre-commit-check.sh — the two non-negotiables, checked before every git commit.
#   1. Import-isolation gate: the SDK must not import from backend/apps/services/frontend.
#   2. Engineering-log requirement: any src/ change must be accompanied by a log entry.
# Wired in .claude/settings.json (PreToolUse on git commit). A non-zero exit blocks the commit.
# Make executable once after cloning:  chmod +x .claude/hooks/pre-commit-check.sh

set -euo pipefail

SRC_DIR="src/korchestrator"
LOG="./.claude/memory/ENGINEERING_LOG.md"
FAIL=0

# ---------------------------------------------------------------------------
# 1. Import-isolation gate
# ---------------------------------------------------------------------------
if [ -d "$SRC_DIR" ]; then
  if grep -RnE "from (backend|apps|services|frontend)\.|import (backend|apps|services|frontend)\." "$SRC_DIR"; then
    echo ""
    echo "ISOLATION VIOLATION: the SDK must not import from backend/apps/services/frontend."
    echo "Fix: define the smallest contract in interfaces/ and inject an implementation."
    FAIL=1
  else
    echo "isolation: OK"
  fi
else
  echo "isolation: $SRC_DIR not found yet — skipping (pre-scaffold)."
fi

# ---------------------------------------------------------------------------
# 2. Engineering-log requirement
# ---------------------------------------------------------------------------
staged=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)
if [ -n "$staged" ]; then
  touches_source=$(printf "%s\n" "$staged" | grep -E "^(src/|clients/typescript/src/)" || true)
  touches_log=$(printf "%s\n" "$staged" | grep -E "^\.claude/memory/ENGINEERING_LOG\.md$" || true)
  if [ -n "$touches_source" ] && [ -z "$touches_log" ]; then
    echo ""
    echo "ENGINEERING LOG REQUIRED: this commit changes source but does not update the log."
    echo "Add an entry to $LOG (all ten fields) and stage it before committing."
    echo "See CLAUDE.md §8."
    FAIL=1
  else
    echo "engineering-log: OK"
  fi
fi

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo "Commit blocked. Fix the issues above and retry (do not use --no-verify)."
  exit 1
fi

echo "pre-commit checks passed."
exit 0