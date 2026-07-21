# Project State — Korchestrator SDK

**What this file is.** The answer to "where is this project right now", in one read. The engineering
log is chronological history; this file is the current snapshot. Update it whenever a phase advances,
a module changes status, or the public surface moves — `/log` does both together.

**Last updated:** 2026-07-21 · **Version:** `0.1.0` (unreleased) · **Branch model:** `main` / `develop`

---

## 1. Current position

| | |
|---|---|
| **Active phase** | P1 — Public API & Interface Contracts — **complete** (on branch `feat/p1-contracts`, off `chore/p0-foundations`; both pending push/PR) |
| **Last completed phase** | P1 — all six tasks (P1.1–P1.6) landed. Every contract is frozen. |
| **Blocking** | Nothing. P2 (Pregel kernel) is ready to begin once P0+P1 merge. |
| **Code written** | P0 foundation (see below) plus: the `KorchError` tree + error codes; the frozen domain models (`state`/`agent`/`plan`/`routing`/`result`/`tool` + `types.JSONValue`); the ARI ports and supporting protocols; and the frozen public façade (`Korch`/`Swarm`/`Agent`) with the 27-name `__all__` guarded by a golden snapshot. |

The package now builds standalone (`pip install -e .`, `python -m build`, clean-env wheel install all
verified), imports as `0.1.0`, and every local gate is green: ruff, ruff-format, `mypy --strict`,
`pytest` (100% coverage at this size), import-linter (3 contracts kept), the isolation gate,
env-confinement, and version single-sourcing. `mkdocs build --strict` passes on the stub site.

## 2. Phase progress

| Phase | Title | Status |
|---|---|---|
| P0 | Foundations, scope freeze, scaffolding | **Complete** (branch `chore/p0-foundations`) |
| P1 | Public API & interface contracts | **Complete** (branch `feat/p1-contracts`) |
| P2 | Core execution kernel (Pregel) | Not started |
| P3 | Runtime adapters (local + Temporal) | Not started |
| P4 | Cognitive layer (agents, signatures, taxonomy) | Not started |
| P5 | Model routing | Not started |
| P6 | Integration & observability (AUB, MCP, A2A, streaming, context) | Not started |
| P7 | Governance, security & context graph | Not started |
| P8 | Cross-cutting foundations | Not started |
| P9 | Remote client (Python only — TS deferred) | Not started |
| P10 | Testing, benchmarks & quality gates | Not started |
| P11 | Documentation, examples & DX | Not started |
| P12 | CI/CD, packaging & publishing | Not started |
| P13 | External backend adapter | **Out of scope** — separate repository |

## 3. Module status

Every module is **not created**. Populate this table as modules land: `not created` → `stub` →
`implemented` → `tested` → `documented`.

| Module | Layer | Status | Phase |
|---|---|---|---|
| `config/` | Leaf utility | **tested** (minimal `Settings` + `from_env`; P8 finalizes) | P0, P8 |
| `constants/` · `exceptions/` | Leaf utility | **tested** (`KorchError` tree + error codes, frozen) | P1 |
| `types/` · `models/` | Contract | **tested** (`JSONValue` + frozen domain models, frozen) | P1 |
| `interfaces/` | Contract | **tested** (ARI ports + supporting protocols, frozen) | P1 |
| `services/` | Façade | **tested** (`Korch`/`Swarm`/`Agent` signatures; `run` → `NotImplementedError` until P4.9) | P1, P4 |
| `core/` · `agents/` · `taxonomy/` · `routing/` · `runtime/` · `context/` · `persistence/` · `providers/` · `tools/` · `mcp/` · `a2a/` · `governance/` · `security/` · `events/` · `clients/` · `serializers/` · `validators/` · `telemetry/` · `logging/` | see spec 05 | **stub** (skeleton `__init__` with docstring + `__all__`) | P2–P9 |

## 4. Public surface

**Currently exported (frozen at P1):** 27 names — `Agent`, `AgentState`, `Korch`, `Swarm`, the 4 ARI
ports (`IDurableRuntime`/`IExecutionSandbox`/`IIdentityProvider`/`IModelGateway`), the 13 top-level
`KorchError` subclasses, `Message`/`RunResult`/`RunStatus`/`StateUpdate`, `Settings`, and
`__version__`. Full list in `tests/unit/public_surface.json`.

**Grows in P8** by four names (`configure`, `enable_logging`, `from_json`, `to_json`) — each a MINOR
addition that updates the golden snapshot. `korchestrator.exceptions.TimeoutError` is part of the
compatibility surface but intentionally not top-level.

The surface is guarded by the golden-file snapshot test (`tests/unit/test_public_surface.py`).
Changing it is a deliberate act requiring a CHANGELOG entry and a version decision in the same PR.

## 5. Settled decisions

All recorded in [`docs/adr/`](../../docs/adr/README.md) and binding.

| Decision | Outcome | ADR |
|---|---|---|
| Package / client naming | `korchestrator`; `korchestrator.remote`; `KorchestratorClient`; `run`/`run_swarm`/`run_and_wait` | 0001 |
| Version source | `src/korchestrator/version.py`, single literal, starts `0.1.0` | 0002 |
| License | Apache-2.0 | 0003 |
| Dependencies | `pydantic` only in core; extras `dspy`/`temporal`/`routing`/`mcp`/`remote`/`otel`/`all`/`dev` | 0004 |
| Remote auth | `Authorization: Bearer <api-key \| KIAM JWT>`, one scheme | 0005 |
| Runtime | Local + Temporal behind `IDurableRuntime`; one activity per superstep | 0006 |
| Backend boundary | One-way; the SDK never depends on a service | 0007 |
| TypeScript client | Specified, **deferred** — not built in P0–P12 | 0008 |
| Settings dependency | `Settings` on `pydantic.BaseModel`, env read in `config/` — keeps base pydantic-only (not `pydantic-settings`) | 0009 |

## 6. Known gaps and open items

| Item | Detail | Owner / when |
|---|---|---|
| Compliance checks named in ADRs | `version-validate`, the isolation gate, and env-confinement now **exist and pass** (`scripts/`). The import-purity subprocess test (ADR 0004) and the event-history shape test are still owed by P2/P3. | P2, P3, P9 |
| Coverage floor enforced | Global 80% is wired (`fail_under=80`) and green (100% at this size); `core/`+`models/` 95% checked in CI. Ratchet from P2 as behaviour lands. | P2+ |
| `import-linter` contracts configured | `.importlinter` with 3 contracts (framework-free, layers, feature-independence); `lint-imports` reports 3 kept, 0 broken. `include_external_packages=True` added (import-linter requirement, omitted from spec §9 snippet). | ✔ P0 |
| Manifest corrections during P0 | `--xfail-strict` → `xfail_strict=true` (spec named a nonexistent pytest flag); `import-linter` added to `[dev]`. Both recorded in the engineering log. | ✔ P0 |
| Benchmark baseline not established | Committed baseline lands in P10. | P10 |
| TS parity matrix | Ships as documentation in P9 with every method marked `TS: planned`. | P9 |
| Backlog capabilities deliberately unbuilt | Context Graph external backends, speculative execution, FinOps quotas, KL DSL. Interface-now/implement-minimally; revisit post-1.0 only with real demand. | Post-1.0 |

## 7. Where things live

| What | Where |
|---|---|
| Authoritative design | `docs/specs/` (00–12) — on conflict, the specs win over `.claude/CLAUDE.md` |
| Decisions | `docs/adr/` |
| History | `.claude/memory/ENGINEERING_LOG.md` |
| Current state | this file |
| Agent rules | `.claude/rules/` |
| Commands | `.claude/commands/` — `/phase`, `/verify`, `/log`, `/adr` |
| Subagents | `.claude/agents/` — `boundary-auditor`, `api-reviewer` |
| Skills | `.claude/skills/add-module/` |
| Source inputs (superseded) | `docs/background/` — provenance only, do not build from |
