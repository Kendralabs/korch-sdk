---
description: Run every quality gate the way CI runs them and report honestly
allowed-tools: Bash, Read, Grep, Glob
---

Run the full gate set below. Run them **all**, even after one fails — a single report is more useful
than an early exit.

```bash
ruff check src/korchestrator tests
ruff format --check src/korchestrator tests
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing
lint-imports                      # import-linter contracts (skip if not yet configured)

# Import-isolation gate — MUST print OK
grep -RnE "from (backend|apps|services|frontend)\.|import (backend|apps|services|frontend)\." src/korchestrator \
  && echo "ISOLATION VIOLATION" || echo "OK"

# Env must be read only inside config/
grep -RnE "os\.getenv|os\.environ" src/korchestrator --include="*.py" | grep -v "src/korchestrator/config/" \
  && echo "CONFIG LEAK" || echo "OK"

# Determinism: no wall-clock or randomness on the workflow path
grep -rnE "datetime\.now|time\.time\(|uuid4\(|\brandom\." src/korchestrator/core src/korchestrator/models \
  && echo "DETERMINISM VIOLATION" || echo "OK"

python -c "import korchestrator; print(korchestrator.__version__)"
```

If the base-install job is relevant to what changed (anything in `core/` or `models/`), also verify
the kernel suite passes with only `pydantic` present.

## Reporting rules

- Report **actual output**. Never claim a check passed unless it ran and you saw it pass.
- If a tool is not installed or a path does not exist yet, say so explicitly — do not silently skip it
  and do not count it as passing.
- For each failure: the gate, the file and line, the cause, and the smallest fix. Do not fix anything
  unless asked — this command reports.
- End with a one-line verdict: `ALL GATES GREEN` or `N GATE(S) FAILING: <names>`.

Gate definitions and coverage floors: `docs/specs/09-testing-and-quality.md`.
