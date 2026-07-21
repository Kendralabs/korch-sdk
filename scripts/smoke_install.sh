#!/usr/bin/env bash
# Clean-environment install smoke test (spec 02 §5.3, spec 09 §9 gate 13).
#
# Builds the wheel, installs it into a throwaway virtual environment OUTSIDE the source tree
# (so imports cannot resolve against src/), then imports the package and prints its version.
# Exits non-zero on any failure.
set -euo pipefail

VENV="$(mktemp -d)/venv"
DIST="$(pwd)/dist"

python -m build
python -m venv "$VENV"

# Resolve the venv python across POSIX (bin) and Windows Git-Bash (Scripts) layouts.
PY="$VENV/bin/python"
[ -x "$PY" ] || PY="$VENV/Scripts/python"

"$PY" -m pip install --upgrade pip
"$PY" -m pip install "$DIST"/*.whl

# Leave the source tree so a stray local import cannot mask a packaging defect.
cd /
"$PY" -c "import korchestrator; print('smoke OK:', korchestrator.__version__)"
