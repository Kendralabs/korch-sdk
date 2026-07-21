#!/usr/bin/env bash
# Import-isolation gate (spec 03 §9 D3, spec 09 §9 gate 9).
#
# The SDK is self-contained: it must never import from an external application package
# (backend/apps/services/frontend). Note that korchestrator's OWN `services/` package is the
# façade and is legal — the ban is on a TOP-LEVEL external `services`, matched only as
# `from services.` / `import services.`, never as `korchestrator.services`.
#
# Prints "OK" and exits 0 when clean; prints the offending lines and exits 1 on a violation.
set -euo pipefail

SRC="src/korchestrator"
PATTERN='from (backend|apps|services|frontend)\.|import (backend|apps|services|frontend)\.'

if [ ! -d "$SRC" ]; then
  echo "isolation: $SRC not found" >&2
  exit 1
fi

if grep -RnE "$PATTERN" "$SRC"; then
  echo "" >&2
  echo "ISOLATION VIOLATION: the SDK must not import from backend/apps/services/frontend." >&2
  echo "Fix: define the smallest contract in interfaces/ and inject an implementation." >&2
  exit 1
fi

echo "OK"
