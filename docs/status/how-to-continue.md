# How To Continue

What is left, and the exact prompt to paste into a new session.

---

## Where we stopped

- `develop` (pushed to GitHub) = **P0–P6 complete**.
- `feat/p7-governance-security` (local, **not yet pushed**) = **P7.1–P7.6 complete** — all of
  Phase 7 (governance, security, bitemporal Context Graph) committed on top of `develop`.
- Immediate next step: push the branch, merge into `develop` (`--no-ff`), push `develop`, then
  start **Phase 8 — cross-cutting foundations**.

## What Phase 7 shipped

1. **P7.1 — Shield**: the consolidated PII/secret redactor (`security/`).
2. **P7.2 — Trust scoring**: the kernel barrier folds `trust_delta` into `AgentState.trust_score`
   every superstep; `governance.check_governance` reads it back with per-superstep telemetry.
3. **P7.3 — Policy + audit**: `evaluate_policy(...)` (per-agent `hitl_threshold` with a
   `GOVERNANCE_TRUST_THRESHOLD` fallback) and an append-only `AuditLog`.
4. **P7.4 — HITL controls**: the Temporal runtime auto-pauses on a trust-threshold breach (the
   same mechanism an operator's `pause` signal uses); a new `edit_resume` signal; `Korch`/`Swarm`
   expose `pause`/`resume`/`cancel`/`edit_resume`.
5. **P7.5 — Graph repository**: `InMemoryGraphRepository` (the default, `PERSISTENCE_BACKEND=
   memory`); `Korch`/`Swarm` now checkpoint state to it after each superstep.
6. **P7.6 — Context Graph client**: `ContextGraphClient` — bitemporal `DecisionNode`/`EventNode`s
   (valid-time + transaction-time, confidence, provenance), Shield-redacted on write, tenant-scoped
   and time-travel-queryable.

**Phase 7 acceptance, met:** a run auto-pauses below the trust threshold and resumes on a signal;
redaction covers every required format and fails closed; graph queries are tenant-scoped; a fully
standalone run (`PERSISTENCE_BACKEND=none`) completes with no external store.

**One open item, not blocking the merge:** `pytest -m temporal` cannot run in *this* dev machine's
environment — a pre-existing conflict between Temporal's sandboxed workflow validation and
`beartype` (pulled in by unrelated globally-installed packages, not a `korchestrator` dependency).
Confirmed via `git stash` that it reproduces identically against the unmodified P3 code, so it
predates Phase 7 entirely. The P7.4 HITL logic was independently verified correct via an
unsandboxed diagnostic harness (see the P7.4 engineering-log entry). A clean CI environment should
not hit this — worth confirming once CI exists (P12), or sooner if convenient.

## Phase 8 — Cross-cutting foundations (next)

**Branch prefix:** `feat/p8-*` · **Goal:** finalize what P0.3 started, plus the remaining utilities
(spec 12, Phase 8).

1. **P8.1 — Settings finalized**: the full variable table from spec 08 §1.3, precedence
   `arg > env > .env > default`, `configure()`/`get_settings()`, zero-config `MockLM` default.
   Also resolve the `ConfigurationError` vs `ValidationError` overlap flagged in
   `PROJECT_STATE.md` §6 before `configure()` lands.
2. **P8.2 — Config isolation test**: assert no `os.getenv`/`os.environ` outside `config/`.
3. **P8.3 — Logging**: `logging/` — namespaced logger, `NullHandler`, `enable_logging()`,
   structured fields, secret-safe.
4. **P8.4 — Exception audit**: every internal exception wrapped; boundary tests asserting only
   `KorchError` subclasses ever escape.
5. **P8.5 — Serialization**: `serializers/` — deterministic, version-tagged round-trip for
   `AgentState`/`AgentGraph`/`ExecutionPlan`/`ModelCard`/`RunResult`; stable key ordering; a
   migration rule.
6. **P8.6 — Validation**: `validators/` — trust-boundary validation, fail-fast with actionable
   messages.
7. **P8.7 — Telemetry**: `telemetry/` — optional OTel spans/metrics (`[otel]` extra), the GenAI
   span tree `agent.run → agent.plan → tool.call → gen_ai.call`, zero overhead when off.

**Phase 8 acceptance:** env read only in `config/` (test-enforced); logging fully disable-able; no
raw internal exception escapes; serde round-trips stay stable across a version bump.

**Commits:** `feat(config): finalize typed Settings and configure() [P8]` ·
`feat(logging): add namespaced disable-able logging [P8]` ·
`feat(serializers): add version-tagged deterministic serialization [P8]` ·
`feat(telemetry): add optional OTel instrumentation [P8]`

## Phases after P8

- **P9** — Remote client (`KorchestratorClient`, `[remote]` extra).
- **P10** — Testing, benchmarks, quality ratchet.
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
python -m mypy --strict src/korchestrator
python -m pytest tests -m "not temporal" --cov=korchestrator --cov-report=term-missing
# import-linter console script:
"$APPDATA/Python/Python311/Scripts/lint-imports.exe"
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
- Branch `develop` (pushed) = Phases P0 through P6 complete and merged.
- Branch `feat/p7-governance-security` = P7.1-P7.6 complete (all of Phase 7), pushed and merged
  into develop (if this hasn't happened yet, do it first: push the branch, merge --no-ff into
  develop, push develop).
- Next phase = P8 (cross-cutting foundations): P8.1 Settings finalized, P8.2 config isolation
  test, P8.3 logging, P8.4 exception audit, P8.5 serialization, P8.6 validation, P8.7 telemetry.

Standing authorization (already given by the user): after finishing a phase, automatically
commit → push the feature branch → merge into `develop` with --no-ff → push `develop` → start the
next phase, without asking for per-phase approval. Do NOT push/merge to `main`. Never edit
version.py. Never use --no-verify.

How to work each task:
- Build task-by-task on a new feat/p8-* branch off develop; use the commit groupings the
  build-phase plan lists.
- Design the public surface first, put code in the correct layer, write tests that fail without the
  change, then make every gate green: ruff, ruff format, mypy --strict, pytest + coverage (floor
  80% global, 95% for core/ and models/), the import-isolation gate, lint-imports (4 contracts),
  and doctests. Tools run via `python -m ruff|mypy|pytest`; import-linter via the lint-imports.exe
  in %APPDATA%\Python\Python311\Scripts.
- Keep the base install pydantic-only (heavy deps behind extras, lazily imported). Keep the kernel
  deterministic (no wall-clock/randomness in core/ or workflow scope).
- Update .claude/memory/ENGINEERING_LOG.md BEFORE each commit (a hook enforces it) and CHANGELOG.md
  for user-visible changes. Record structural decisions as short ADRs in docs/adr/.
- When P8's commit groups are done, push + merge P8 into develop, then continue to P9.
- Keep docs/status/*.md and .claude/memory/PROJECT_STATE.md up to date as phases complete.

Start now with P8.1: read its objective/acceptance in the specs, finalize the Settings surface
(full variable table, configure()/get_settings(), and resolve the ConfigurationError vs
ValidationError overlap noted in PROJECT_STATE.md), and drive it to green.
```
