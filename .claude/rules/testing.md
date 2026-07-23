# Rule — Testing

Repository-specific. The org-wide testing baseline still applies.
Authority: `docs/specs/09-testing-and-quality.md`.

## Hard rules

| # | Rule |
|---|---|
| T1 | No test touches the network, a real model, or a real external service |
| T2 | No test uses `sleep`, wall-clock timing, or shared developer state |
| T3 | No test depends on execution order or on another test having run |
| T4 | MockLM is the default gateway. The full agent path runs in CI with no keys and no network. |
| T5 | Every skip and xfail names a specific reason and an owner. `xfail` is strict. |
| T6 | New behaviour ships with a test that **fails without the change** |
| T7 | A bug fix ships a regression test that **failed on the old code** |
| T8 | Never lower a coverage or quality threshold to make a change pass |

## Determinism tests are mandatory

Any change to the kernel, runtime, reducers, or serialization ships with:

- **Repeatability** — same graph + seed produces an identical result across repeated runs
- **Reducer laws** — property-based (Hypothesis) tests for associativity and order-independence
- **Replay** — the Temporal replay test passes, when the Temporal path changed
- **Serde stability** — round-trip is exact and stable across a version bump

## The base-install test

The kernel suite MUST pass with **only `pydantic` installed**. This is a distinct CI job. If a
kernel test needs an extra, the test is in the wrong place or the kernel gained an illegal import.

## Test doubles

| Boundary | Use |
|---|---|
| Model gateway | `MockLM` — deterministic, offline |
| Persistence | In-memory `GraphRepository` |
| Clock | Injected fake clock — never `freezegun`-style patching of workflow code |
| HTTP (remote client) | `respx` against the documented contract |
| Tools | A registered fake connector |

Prefer a deterministic fake over a mock. Assert on behaviour and outputs, not on call counts —
call-count assertions couple tests to implementation and break on every refactor.

## Coverage

- Global floor **90%**; `core/` **97%**; `models/` **99%** (ratcheted from 80/95/95 at P10.6). Ratchet up, never down.
- Coverage is necessary, not sufficient. Assertions must be **meaningful** — a test that executes a
  line without asserting on its effect adds coverage and no safety.

## Layout

Tests mirror `src/`. One test module per source module: `tests/unit/core/test_pregel.py`.
Categories live in `tests/{unit,integration,e2e,regression,smoke}/`.

## Before committing

```bash
ruff check src/korchestrator tests
ruff format --check src/korchestrator tests
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing
```

All four green, plus the isolation gate printing `OK`. Never claim a check passed unless it ran —
if you skipped one, say which and why.
