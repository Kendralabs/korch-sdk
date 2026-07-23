# How To Continue

What is left, and the exact prompt to paste into a new session.

---

## Where we stopped

- `develop` (pushed to GitHub) = **P0–P9 complete**.
- `feat/p9-remote-client` (pushed, merged `--no-ff` into `develop`) = **P9.1–P9.8 complete** — all
  of Phase 9 (the optional Python remote client) merged.
- Immediate next step: start **Phase 10 — Testing, benchmarks & quality gates** on a new
  `feat/p10-*` branch off `develop`.

## What Phase 9 shipped

1. **P9.1 — Transport + auth**: `KorchestratorClient` (`clients/`, re-exported as
   `korchestrator.remote`) — `Authorization: Bearer` (one header for a static key or a JWT), 30s
   default timeout, 3 retries with full-jitter backoff on `429`/`502`/`503`/`504` and connection
   failures. New `ApiError` (`status`/`code`/`trace_id`).
2. **P9.2 — Credential safety**: a credential-safe `repr` (`base_url` only); test-locked that no
   error path leaks the API key; a static check that `clients/` performs no file I/O.
3. **P9.3 — Run lifecycle**: `run`, `run_swarm`, `get_run`, `wait`, `run_and_wait`, `list_runs`,
   `get_run_summary`; numeric→string status normalization for all 7 `RunStatus` values. New wire
   models `RemoteRunResult`/`RunSummary` — deliberately not the local kernel's `RunResult`.
4. **P9.4 — Control + identity**: `resume`, `cancel`, `edit_resume` (mirrors the local kernel's
   signal shape), `me`, `my_quota`, `my_runs`, `create_key`/`list_keys`/`revoke_key`. `ApiKey.key`
   is a `SecretStr`.
5. **P9.5 — Streaming**: `stream(run_id)` — a native async iterator (the one non-sync-wrapped
   method), auto-reconnecting on a dropped connection (no `Last-Event-ID` resumption — documented,
   not silently overstated).
6. **P9.6 — Discovery**: `tools`, `models` (reuses the local kernel's `ModelCard`),
   `swarm_templates` — completes the method surface.
7. **P9.7 — Contract-conformance tests**: a table-driven suite proving all 20 methods surface
   exactly `ApiError` on a non-2xx response, with a guard against a future method missing a table
   entry.
8. **P9.8 — Parity matrix**: `docs/parity-matrix.md` — every method marked `TS: planned` (ADR
   0008), three sketch-vs-implementation discrepancies resolved and labelled.

**Phase 9 acceptance, met:** every documented method exists and is tested against a mocked
transport (`respx`); credentials never appear in any output (test-asserted); streaming consumes
SSE as an async iterator; the parity matrix is complete with planned gaps labelled; the local
kernel remains fully usable without `[remote]` installed (nothing in `korchestrator/__init__.py`
imports `clients`/`remote`, statically checked).

**Public surface note (corrects earlier guidance in this file):** `korchestrator.remote.
KorchestratorClient` did **not** need a `tests/unit/public_surface.json` update. Spec 04 §7's own
intro states `korchestrator.remote` is never imported by `korchestrator/__init__.py` — it is a
separate, optional import path (`from korchestrator.remote import KorchestratorClient`), exactly
like `korchestrator.config`/`korchestrator.logging`, not an addition to top-level `__all__`. The
golden file only guards `korchestrator/__init__.py`'s own `__all__`.

**One open item, unchanged since Phase 7, not blocking:** `pytest -m temporal` still cannot run in
*this* dev machine's environment (pre-existing `beartype`/site-packages conflict, unrelated to any
korchestrator dependency — see the P7.4 engineering-log entry). Worth confirming once CI exists
(P12), or sooner if convenient.

## Phase 10 — Testing, benchmarks & quality gates (next)

**Branch prefix:** `feat/p10-*` · **Goal:** the committed benchmark baseline, the coverage ratchet,
and the remaining compliance checks noted as owed since P0–P3 (spec 11 Phase 10, spec 12
P10.1–P10.x — read the exact task breakdown there before starting; it has not been restated here
in detail yet).

Known, already-tracked inputs to this phase (see `PROJECT_STATE.md` §6 "Known gaps"):

- The telemetry-on/off delta regression spec 08 §4 requires (`benchmarks/` doesn't exist yet).
- The import-purity subprocess test (ADR 0004) and the event-history shape test, owed since
  P2/P3.
- Continue the coverage ratchet (global 80% floor, `core/`+`models/` 95%) upward as behaviour has
  landed — check the current numbers in `PROJECT_STATE.md` §1 before deciding the next target.

## Phases after P10

- **P11** — Docs, examples, developer experience.
- **P12** — CI/CD, packaging, publishing.
- (P13 — external backend adapter — out of scope, separate repo.)

## The rules to keep following (every task)

1. Read the task in `docs/specs/12-implementation-plan.md`; restate its goal from
   `11-build-phase-plan.md`.
2. Design the public surface first; place code in the correct layer.
3. Write tests that fail without the change.
4. Run all gates until green: `ruff`, `ruff format`, `mypy --strict`, `pytest` + coverage, the
   isolation gate, `lint-imports`, and doctests.
5. Update `.claude/memory/ENGINEERING_LOG.md` **before** committing (a hook enforces this), and the
   `CHANGELOG.md` for user-visible changes.
6. Commit with a Conventional Commit message tagged `[P8]` (etc.).
7. Keep the base install `pydantic`-only; keep the kernel deterministic; never edit `version.py`;
   never use `--no-verify`.

## Standing permission already granted

The user authorized **automatic phase progression**: after a phase is done, commit → push the branch
→ merge into `develop` (`--no-ff`) → push → start the next phase, without asking each time. (This is
also saved in the assistant's memory as `autonomous-phase-progression`.)

## Handy commands

```bash
# tools are invoked via python -m on this machine
python -m ruff check src/korchestrator tests
python -m ruff format --check src/korchestrator tests
python -m mypy --strict src/korchestrator
python -m pytest tests -m "not temporal" --cov=korchestrator --cov-report=term-missing
python -m pytest --doctest-modules src/korchestrator
bash scripts/check_isolation.sh
python scripts/check_env_reads.py
python scripts/validate_version.py
# import-linter: the lint-imports console script isn't reliably on PATH in this git-bash shell;
# invoke its CLI programmatically instead (PYTHONIOENCODING=utf-8 avoids a cp1252 crash on its
# box-drawing banner):
PYTHONIOENCODING=utf-8 python -c "
from click.testing import CliRunner
from importlinter.cli import lint_imports_command
result = CliRunner().invoke(lint_imports_command, ['--config', '.importlinter'])
print(result.output); raise SystemExit(result.exit_code)
"
```

---

## ▶️ Prompt to paste into a NEW session

Copy everything in the box below into a fresh session to continue exactly where this left off.

```text
You are continuing the build of the Korchestrator SDK (package: korchestrator), a durable
multi-agent execution kernel. Work in the repo at d:\GitHub\Fintricity\korch-sdk.

First, read these to load context (in this order):
1. .claude/CLAUDE.md and the .claude/rules/*.md (the operating rules).
2. .claude/memory/PROJECT_STATE.md and .claude/memory/ENGINEERING_LOG.md (current state + history).
3. docs/status/README.md, docs/status/what-has-been-built.md, docs/status/how-to-continue.md.
4. docs/specs/12-implementation-plan.md and docs/specs/11-build-phase-plan.md (the task list +
   acceptance criteria). On any conflict, the specs win.

Current state:
- Branch `develop` (pushed) = Phases P0 through P9 complete and merged.
- Branch `feat/p9-remote-client` = P9.1-P9.8 complete (all of Phase 9, the optional Python remote
  client), pushed and merged into develop.
- Next phase = P10 (testing, benchmarks & quality gates) — read its exact task breakdown in
  docs/specs/12-implementation-plan.md and docs/specs/11-build-phase-plan.md before starting;
  known inputs are listed in this file's "Phase 10" section and PROJECT_STATE.md §6.

Standing authorization (already given by the user): after finishing a phase, automatically
commit → push the feature branch → merge into `develop` with --no-ff → push `develop` → start the
next phase, without asking for per-phase approval. Do NOT push/merge to `main`. Never edit
version.py. Never use --no-verify.

How to work each task:
- Build task-by-task on a new feat/p10-* branch off develop; use the commit groupings the
  build-phase plan lists.
- Design the public surface first, put code in the correct layer, write tests that fail without the
  change, then make every gate green: ruff, ruff format, mypy --strict, pytest + coverage (floor
  80% global, 95% for core/ and models/), the import-isolation gate, lint-imports (4 contracts),
  and doctests. Tools run via `python -m ruff|mypy|pytest`; import-linter via
  `python -c "from click.testing import CliRunner; from importlinter.cli import
  lint_imports_command; ..."` (see this file's "Handy commands") since the console script isn't
  reliably on PATH in this shell.
- Keep the base install pydantic-only (heavy deps behind extras, lazily imported). Keep the kernel
  deterministic (no wall-clock/randomness in core/ or workflow scope).
- Update .claude/memory/ENGINEERING_LOG.md BEFORE each commit (a hook enforces it) and CHANGELOG.md
  for user-visible changes. Record structural decisions as short ADRs in docs/adr/.
- When P10's commit groups are done, push + merge P10 into develop, then continue to P11.
- Keep docs/status/*.md and .claude/memory/PROJECT_STATE.md up to date as phases complete.

Start now: read Phase 10's exact objective/acceptance/task list in the specs (it has not been
task-by-task detailed in docs/status/ yet — do that as the first step), then begin its first task
and drive it to green.
```
