# CLAUDE.md — Korchestrator SDK

This is the operating manual for any AI agent (and human) working in this repository. Claude Code
loads it automatically. The detailed design lives in `docs/specs/` (sequenced 00–12); this file is
the condensed, always-on ruleset. **On any conflict, the specs win.**

## Where to look

| Need | Go to |
|---|---|
| The task you are implementing | `docs/specs/12-implementation-plan.md` for the task list, `11-build-phase-plan.md` for its acceptance criteria, then `/phase P<n>.<m>` |
| Where code goes / what it may import | `docs/specs/03-architecture.md`, `.claude/rules/architecture-boundaries.md` |
| The public surface and compatibility | `docs/specs/04-public-api.md`, `.claude/rules/api-and-compatibility.md` |
| Why something was decided | `docs/adr/` |
| What has been built so far | `.claude/memory/ENGINEERING_LOG.md` |
| Where the project stands right now | `.claude/memory/PROJECT_STATE.md` |
| Rules that are easy to break by accident | `.claude/rules/determinism.md` |

Commands: `/phase` (start a task) · `/verify` (run all gates) · `/log` (engineering log) · `/adr`
(record a decision). Subagents: `boundary-auditor`, `api-reviewer`. Skill: `add-module`.

`docs/background/` holds the **source inputs** that `docs/specs/` was derived from. Read them for
product context; never build from them. Where they disagree with `docs/specs/`, the specs win —
notably on the TypeScript client, which they show as in scope but ADR 0008 defers.

---

## 1. What this repo is

The installable **Korchestrator SDK** — a durable multi-agent execution kernel (Temporal for
durability/replay, Pregel BSP for deterministic parallel supersteps, DSPy compiled signatures for
typed reasoning). Package: `korchestrator`. Branches: `main` (released) / `develop` (integration).

**You build ONE thing: this SDK.** Not a frontend, backend, service, or app.

## 2. Golden rules (never violate)

1. **One product — the SDK.** No frontend/backend/service in this repo, ever. The external backend
   (Phase 13) is out of scope and never a dependency.
2. **Self-contained.** Never import from `backend.*`, `apps.*`, `services.*`, `frontend`. If you
   need external behavior, define the smallest interface in `interfaces/` and inject an
   implementation.
3. **Dynamic, not hardcoded.** No hardcoded URLs/keys/models/paths. Environment variables are read
   **only** in `config/`.
4. **Determinism & backward-compatibility are features.** The kernel behaves identically across
   runs and Temporal replays; the public API stays compatible within a major version.
5. **Don't over-engineer.** Simplest correct design. No interface with a single forever-
   implementation; no speculative abstraction.
6. **Deployment = publishing artifacts, not running a service.** If asked to deploy a server from
   this repo, it's out of scope — say so and stop.

## 3. Architecture & boundaries (dependencies point inward only)

```
services (façade) → agents → core (Pregel) → interfaces / models
        └── routing, tools, mcp, a2a, governance, persistence, context, events, runtime
                                 → depend inward on interfaces / models only
providers, runtime/temporal_runtime → implement interfaces
config, exceptions, logging, telemetry, serializers, validators, security → leaf utilities
```

- **`core/` is framework-free** — imports only `interfaces/`, `models/`, stdlib, `pydantic`. No
  FastAPI/HTTP/Temporal/DSPy in `core/`.
- **Heavy deps are lazy & confined:** `dspy`→`agents/`, `temporalio`→`runtime/temporal_runtime.py`,
  `httpx`→`clients/`, OTel→`telemetry/`. Import inside the function that needs them, never at module
  top level.
- **No sideways sibling imports; no cycles.** Feature folders meet at `interfaces/`/`models/`.
- **Wiring happens only at the façade** (`services/`). Nothing below constructs its own
  collaborators — inject them (DIP).
- **Three ARI ports** give portability (local default ↔ Kendra): `IIdentityProvider`,
  `IExecutionSandbox`, `IModelGateway`. A port exists only when there's >1 implementation.

Detail: `docs/specs/03-architecture.md`, `docs/specs/05-modules-and-data-models.md`.

## 4. Coding standards

- **Python ≥3.10, `src/` layout.** Full type hints; `mypy --strict` must be clean. Public functions
  return typed Pydantic models, never bare dicts. Ship `py.typed`.
- **One responsibility per module** (<~500 lines/file, <~50 lines/function). Explicit `__all__`.
- **Errors:** everything catchable is a `KorchError` subclass (`AuthError`, `ValidationError`,
  `NetworkError`, `ProviderError`, `TimeoutError`, `RateLimitError`, `QuotaExceededError`,
  `RoutingError`, `GovernanceHaltError`, `RunFailedError`, `RunTimeoutError`, `ToolError`). Never
  leak raw `temporalio`/`httpx`/`dspy` exceptions — wrap with `raise ... from exc`. Messages are
  actionable.
- **Logging:** one namespaced logger `logging.getLogger("korchestrator")` with a `NullHandler`, off
  by default. No `print()`, never mutate the root logger, never log secrets.
- **Naming:** `PascalCase` classes, `lower_snake` functions/modules, `I<Name>` for ARI ports. The
  remote client is always `KorchestratorClient`.
- **Docstrings** (Google-style) on every public callable, with a runnable example (MockLM/offline).

## 5. Determinism (kernel / runtime / serde)

No wall-clock (`datetime.now()`/`time.time()`) or randomness in workflow-path code — use the
runtime's injected clock. Agents compute against a **frozen snapshot** and emit `StateUpdate`
deltas; the barrier applies reducers. Reducers (`LastValue`/`Append`/`UniqueAppend`/`MergeDict`)
are **associative and order-independent**. Serialization is deterministic and version-tagged.
Nondeterminism lives in activities, never workflow scope.

## 6. Testing

- No test touches the network, a real model, `sleep`, or shared state. **MockLM** is the default
  gateway.
- New behavior ships with tests that fail without the change; a bug fix ships a regression test that
  failed on the old code.
- Kernel/runtime/serde changes ship determinism tests (repeatability, reducer laws, Temporal replay,
  serde stability).
- Command: `pytest tests --cov=korchestrator --cov-report=term-missing`. Coverage floor is enforced
  and ratcheted up, never down. Assertions must be meaningful, not just line-hitting.

## 7. Git & commit workflow

- Branch off `develop` as `<type>/p<phase>-<slug>` (`feat`/`fix`/`docs`/`refactor`/`test`/`chore`/
  `security`/`perf`). **Never commit directly to `main` or `develop`.**
- **Conventional Commits**, phase-tagged: `feat(core): implement Pregel kernel + reducers [P2]`.
  Commit phase/task-wise; every commit leaves the package green (build + tests pass).
- **Before every commit** (enforced by the hook in §9): lint + format clean, `mypy --strict` clean,
  `pytest` green + coverage ≥ floor, **isolation gate prints `OK`**, **engineering log updated**,
  CHANGELOG updated for user-visible changes. Never `git commit --no-verify`.
- Reach `develop`/`main` only via reviewed PRs.
- **Never edit `src/korchestrator/version.py`** outside a release PR — it's the single source of the
  SemVer version (all else derives; CI fails on mismatch). Start at `0.1.0`.

## 8. Engineering log — MANDATORY before every commit

> Whenever a feature, enhancement, refactor, bug fix, or architectural change is completed, add an
> entry to `.claude/memory/ENGINEERING_LOG.md` **before committing.** The hook in §9 blocks any commit that
> changes `src/` without a fresh log entry.

Each entry records all ten fields (template lives at the bottom of `ENGINEERING_LOG.md`):

1. **What** was implemented · 2. **Why** · 3. **Design decisions** · 4. **Architecture changes** ·
2. **Files/modules affected** · 6. **Breaking changes** · 7. **Feature version/revision** ·
3. **Migration notes** · 9. **Testing status** · 10. **Known limitations / future improvements**.

Breaking change → the entry must include a migration note + major-bump plan, and the decision needs
a short ADR under `docs/adr/`.

## 9. Enforcement hook

`settings.json` runs `hooks/pre-commit-check.sh` before every `git commit`. It (a) runs the
import-isolation gate and (b) requires an engineering-log update when `src/` changed. It also
denies editing `version.py`, reading secrets, and `--no-verify`. After cloning, make the hook
executable once: `chmod +x .claude/hooks/pre-commit-check.sh`.

## 10. Standing workflow for any task

1. Find the task in `docs/specs/12-implementation-plan.md`; restate its Objective/Build/Validation/DoD
   from `docs/specs/11-build-phase-plan.md`.
   Confirm it's in scope (§2).
2. Design the public surface first (API-first); check names/compat against
   `docs/specs/04-public-api.md`.
3. Place code in the correct layer (§3); implement the simplest correct version.
4. Write the tests that lock the behavior (§6).
5. Run the gates until green (§7).
6. Update docstrings, docs, and CHANGELOG for user-visible changes.
7. **Update `.claude/memory/ENGINEERING_LOG.md` (§8) — before committing.**
8. Commit conventionally; open a PR into `develop`.

**When unsure or a request conflicts with a golden rule:** stop, state the conflict, and if it's a
structural decision or a deviation from a spec, write a short ADR before coding.
