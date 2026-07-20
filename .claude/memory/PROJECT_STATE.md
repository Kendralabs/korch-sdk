# Project State — Korchestrator SDK

**What this file is.** The answer to "where is this project right now", in one read. The engineering
log is chronological history; this file is the current snapshot. Update it whenever a phase advances,
a module changes status, or the public surface moves — `/log` does both together.

**Last updated:** 2026-07-20 · **Version:** `0.1.0` (unreleased) · **Branch model:** `main` / `develop`

---

## 1. Current position

| | |
|---|---|
| **Active phase** | P0 — Foundations, Scope Freeze & Scaffolding — **not started** |
| **Last completed phase** | None. Planning and specification only. |
| **Blocking** | Nothing. P0 is ready to begin. |
| **Code written** | None. `src/korchestrator/` does not exist yet. |

The repository currently contains the specification set, the ADRs, and the Claude Code configuration.
No package source exists. The first implementation task is P0 scaffolding.

## 2. Phase progress

| Phase | Title | Status |
|---|---|---|
| P0 | Foundations, scope freeze, scaffolding | Not started |
| P1 | Public API & interface contracts | Not started |
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
| `config/` · `interfaces/` · `core/` · `models/` · `agents/` · `taxonomy/` · `routing/` · `runtime/` · `context/` · `persistence/` · `providers/` · `tools/` · `mcp/` · `a2a/` · `governance/` · `security/` · `events/` · `clients/` · `services/` · `serializers/` · `validators/` · `telemetry/` · `logging/` · `exceptions/` · `types/` · `constants/` | see spec 05 | not created | P0–P9 |

## 4. Public surface

**Currently exported:** nothing — the package does not exist.
**Target for P1 (frozen thereafter):** the `__all__` in `docs/specs/04-public-api.md` §6.

The surface is guarded by a golden-file snapshot test from P1 onward. Changing it is a deliberate
act requiring a CHANGELOG entry and a version decision in the same PR.

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

## 6. Known gaps and open items

| Item | Detail | Owner / when |
|---|---|---|
| Compliance checks named in ADRs do not exist yet | ADRs 0001–0008 reference `version-validate`, the import-purity test, the forbidden-spelling grep, and the event-history shape test. These are **commitments**, not fiction — P0/P2/P3/P9 must create them or the compliance sections become untrue. | P0, P2, P3, P9 |
| Coverage floor not yet enforced | Global 80%, `core/`+`models/` 95%. Wire into CI in P0, ratchet from P2. | P0 |
| `import-linter` contracts not yet configured | Proposed contract set is in spec 03 §9. | P0 |
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
