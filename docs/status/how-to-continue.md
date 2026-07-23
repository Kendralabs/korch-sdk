# How To Continue

What is left, and the exact prompt to paste into a new session.

---

## Where we stopped

- `develop` (pushed to GitHub) = **P0–P8 complete**.
- `feat/p8-cross-cutting-foundations` (pushed, merged `--no-ff` into `develop`) = **P8.1–P8.7
  complete** — all of Phase 8 (config, logging, exception audit, serialization, validation,
  telemetry) merged.
- Immediate next step: start **Phase 9 — Remote client** on a new `feat/p9-*` branch off `develop`.

## What Phase 8 shipped

1. **P8.1 — Settings finalized**: the full spec 08 §1.3 variable table (28 fields); `configure()`/
   `get_settings()`; resolved the `ConfigurationError` vs `ValidationError` overlap (ADR 0016).
2. **P8.2 — Config isolation test**: fails the build if env/`.env` reading escapes `config/`.
3. **P8.3 — Logging**: namespaced `korchestrator` logger, `NullHandler` by default,
   `enable_logging()`/`disable_logging()`.
4. **P8.4 — Exception audit**: found and fixed one real gap — the Temporal client boundary could
   leak a raw `temporalio` exception; now wrapped.
5. **P8.5 — Serialization**: `to_json`/`from_json`, deterministic and version-tagged, for
   `AgentState`/`ExecutionPlan`/`ModelCard`/`RunResult` (`AgentGraph` excluded, ADR 0017).
6. **P8.6 — Validation**: `validators/` closed two real, previously-silent gaps — unchecked
   `max_supersteps` bounds and silent duplicate-agent-id overwrite in `Swarm.add()`.
7. **P8.7 — Telemetry**: `telemetry/` — `start_span`/`record_metric`, zero-overhead no-op when
   `KORCH_TELEMETRY_ENABLED` is off (the default); the outer `agent.run` span and
   `korch.run.duration`/`korch.run.status` metrics are wired into the composition root. The rest
   of the span tree (`agent.superstep`/`agent.plan`/`tool.call`/`gen_ai.call`) and four of the six
   named metrics are defined (correct OTel instrument kind) but not yet wired into the kernel/
   tool/gateway call sites — a follow-up, not a blocker (see `PROJECT_STATE.md` §6).

**Phase 8 acceptance, met:** env read only in `config/` (test-enforced); logging fully disable-able;
no raw internal exception escapes uncaught; serde round-trips stay byte-stable and version-tagged;
telemetry costs nothing when off and raises actionably when enabled without the `[otel]` extra.

**One open item, unchanged since Phase 7, not blocking:** `pytest -m temporal` still cannot run in
*this* dev machine's environment (pre-existing `beartype`/site-packages conflict, unrelated to any
korchestrator dependency — see the P7.4 engineering-log entry). Worth confirming once CI exists
(P12), or sooner if convenient.

## Phase 9 — Remote client (next)

**Branch prefix:** `feat/p9-*` · **Goal:** ship the optional Python remote client as
`korchestrator.remote` (spec 11 Phase 9, spec 12 P9.1–P9.8). TypeScript is deferred (ADR 0008) —
Python only, no `clients/typescript/`, no npm job.

1. **P9.1 — Transport + auth**: `clients/` — `httpx` async+sync base (`[remote]`), `Authorization:
   Bearer`, 30s timeout, 3 retries with jittered backoff, retrying only 429/502/503/504.
2. **P9.2 — Credential safety**: redaction from logs, exceptions, telemetry; a test asserting
   credentials never appear in any output or on disk.
3. **P9.3 — Run lifecycle**: `run`, `run_swarm`, `run_and_wait`, `get_run`, `wait`, `list_runs`,
   `get_run_summary`; numeric→string status normalization.
4. **P9.4 — Control + identity**: `resume`, `cancel`, `edit_resume`, `me`, `my_quota`, `my_runs`,
   key management.
5. **P9.5 — Streaming**: SSE `stream` as an async iterator; reconnect semantics.
6. **P9.6 — Discovery**: `tools`, `models`, `swarm_templates`.
7. **P9.7 — Errors + tests**: `ApiError(status, message, code, trace_id)` as a `KorchError`; a full
   `respx`-mocked suite against the spec 04 §7 contract.
8. **P9.8 — Parity matrix**: `docs/parity-matrix.md` — every Python method marked `TS: planned`.

**Phase 9 acceptance:** every documented method exists and is tested against a mocked transport
(`respx`); credentials never appear in logs/exceptions/telemetry (test-asserted); the streaming
example consumes SSE; the parity matrix is complete with planned gaps labelled; the local kernel
remains fully usable without `[remote]` installed.

**Public surface added:** `korchestrator.remote.KorchestratorClient` (and its supporting models) —
this is a genuinely new top-level surface, so check names against spec 04 §7 and update
`tests/unit/public_surface.json` deliberately, with a CHANGELOG entry, per `api-and-compatibility.md`.

## Phases after P9

- **P10** — Testing, benchmarks, quality ratchet (includes the telemetry-on/off `benchmarks/`
  regression deferred from P8.7).
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
- Branch `develop` (pushed) = Phases P0 through P8 complete and merged.
- Branch `feat/p8-cross-cutting-foundations` = P8.1-P8.7 complete (all of Phase 8), pushed and
  merged into develop.
- Next phase = P9 (remote client): P9.1 transport+auth, P9.2 credential safety, P9.3 run lifecycle,
  P9.4 control+identity, P9.5 streaming, P9.6 discovery, P9.7 errors+tests, P9.8 parity matrix.

Standing authorization (already given by the user): after finishing a phase, automatically
commit → push the feature branch → merge into `develop` with --no-ff → push `develop` → start the
next phase, without asking for per-phase approval. Do NOT push/merge to `main`. Never edit
version.py. Never use --no-verify.

How to work each task:
- Build task-by-task on a new feat/p9-* branch off develop; use the commit groupings the
  build-phase plan lists.
- Design the public surface first, put code in the correct layer, write tests that fail without the
  change, then make every gate green: ruff, ruff format, mypy --strict, pytest + coverage (floor
  80% global, 95% for core/ and models/), the import-isolation gate, lint-imports (4 contracts),
  and doctests. Tools run via `python -m ruff|mypy|pytest`; import-linter via
  `python -c "from click.testing import CliRunner; from importlinter.cli import
  lint_imports_command; ..."` (see how-to-continue.md's own history) since the console script isn't
  on PATH in this shell.
- Keep the base install pydantic-only (heavy deps behind extras, lazily imported). Keep the kernel
  deterministic (no wall-clock/randomness in core/ or workflow scope).
- korchestrator.remote is a genuinely new top-level public surface (spec 04 §7) — design it against
  the documented remote contract exactly, and update tests/unit/public_surface.json deliberately
  with a CHANGELOG entry, per .claude/rules/api-and-compatibility.md.
- Update .claude/memory/ENGINEERING_LOG.md BEFORE each commit (a hook enforces it) and CHANGELOG.md
  for user-visible changes. Record structural decisions as short ADRs in docs/adr/.
- When P9's commit groups are done, push + merge P9 into develop, then continue to P10.
- Keep docs/status/*.md and .claude/memory/PROJECT_STATE.md up to date as phases complete.

Start now with P9.1: read its objective/acceptance in the specs, and build the httpx-based
transport + Bearer auth base in clients/ behind the [remote] extra, and drive it to green.
```
