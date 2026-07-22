# How To Continue

What is left, and the exact prompt to paste into a new session.

---

## Where we stopped

- `develop` (pushed to GitHub) = **P0–P6 complete**.
- `feat/p7-governance-security` (local, **not pushed**) = **P7.1 (Shield redactor)** committed on top
  of `develop`.
- The next task is **P7.2 (trust scoring)**.

## What is left in Phase 7 (current phase)

Build these in order; the plan groups them into 3 more commits (see
`docs/specs/12-implementation-plan.md`, Phase 7).

1. **P7.2 — Trust scoring** (`governance/`): a 0.0–1.0 score, checked each superstep, that persists
   across supersteps.
2. **P7.3 — Policy + audit**: a policy engine, an audit log, and per-agent `hitl_threshold` with a
   global `GOVERNANCE_TRUST_THRESHOLD` fallback.
   → Commit: `feat(governance): add trust scoring and policy engine [P7]`
3. **P7.4 — Human-in-the-loop controls**: when trust drops below threshold, the run pauses; expose
   `pause` / `resume` / `cancel` / `edit_resume` on the façade (uses the Temporal runtime's signals).
   → Commit: `feat(governance): add durable HITL controls [P7]`
4. **P7.5 — Graph repository** (`persistence/`): an in-memory `GraphRepository` as the default;
   `PERSISTENCE_BACKEND=none` still runs fully standalone.
5. **P7.6 — Context Graph client**: `ContextGraphClient` with bitemporal nodes (valid-time +
   transaction-time), confidence, provenance, event sourcing, tenant scoping, and time-travel queries.
   → Commit: `feat(persistence): add bitemporal context graph client [P7]`

**Phase 7 acceptance:** a run auto-pauses below the trust threshold and resumes on a signal; redaction
covers every required format and fails closed; graph queries are tenant-scoped; a fully standalone run
completes with no external store.

When all four P7 commit groups are done: push the branch, merge into `develop` (`--no-ff`), push
`develop`.

## Phases after P7

- **P8** — Cross-cutting foundations (finalize config/logging/telemetry/serializers/validators;
  `.env` loading; `configure()`/`get_settings()`; also resolve the `ConfigurationError` vs
  `ValidationError` decision noted in `PROJECT_STATE.md`).
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
6. Commit with a Conventional Commit message tagged `[P7]` (etc.).
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
- Branch `feat/p7-governance-security` (local, NOT pushed) = P7.1 (Shield PII redactor) committed.
- Next task = P7.2 (trust scoring), then P7.3 (policy + audit), P7.4 (HITL controls),
  P7.5 (in-memory GraphRepository), P7.6 (bitemporal ContextGraphClient).

Standing authorization (already given by the user): after finishing a phase, automatically
commit → push the feature branch → merge into `develop` with --no-ff → push `develop` → start the
next phase, without asking for per-phase approval. Do NOT push/merge to `main`. Never edit
version.py. Never use --no-verify.

How to work each task:
- Build task-by-task on the current P7 branch; use the commit groupings the build-phase plan lists.
- Design the public surface first, put code in the correct layer, write tests that fail without the
  change, then make every gate green: ruff, ruff format, mypy --strict, pytest + coverage (floor
  80% global, 95% for core/ and models/), the import-isolation gate, lint-imports (4 contracts),
  and doctests. Tools run via `python -m ruff|mypy|pytest`; import-linter via the lint-imports.exe
  in %APPDATA%\Python\Python311\Scripts.
- Keep the base install pydantic-only (heavy deps behind extras, lazily imported). Keep the kernel
  deterministic (no wall-clock/randomness in core/ or workflow scope).
- Update .claude/memory/ENGINEERING_LOG.md BEFORE each commit (a hook enforces it) and CHANGELOG.md
  for user-visible changes. Record structural decisions as short ADRs in docs/adr/.
- When P7's four commit groups are done, push + merge P7 into develop, then continue to P8.
- Keep docs/status/*.md and .claude/memory/PROJECT_STATE.md up to date as phases complete.

Start now with P7.2: read its objective/acceptance in the specs, design the governance trust-scoring
surface, implement it, and drive it to green.
```
