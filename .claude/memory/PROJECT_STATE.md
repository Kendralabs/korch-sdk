# Project State — Korchestrator SDK

**What this file is.** The answer to "where is this project right now", in one read. The engineering
log is chronological history; this file is the current snapshot. Update it whenever a phase advances,
a module changes status, or the public surface moves — `/log` does both together.

**Last updated:** 2026-07-22 · **Version:** `0.1.0` (unreleased) · **Branch model:** `main` / `develop`

---

## 1. Current position

| | |
|---|---|
| **Active phase** | P5 — Model routing — **complete** (P5.1–P5.6) on branch `feat/p5-model-routing` (off `develop`). Per-agent model selection is wired into every run. |
| **Last completed milestone** | **P5.6 — routing wired into execution.** `get_router(settings)`/`resolve_router(settings, router=)` build a per-agent model router behind one `BaseRouter`: explicit (+fallback) is the zero-config default with no extra; algorithmic (weighted quality/cost/latency) and semantic (embedding similarity, `[routing]`) are the ranking strategies; `UserFunctionRouter` and injection (`Korch(router=)`) plug custom routers in with no package edit (ADR 0014). The composition root routes a model per default-worker agent at graph-build time (pure, replay-safe). |
| **Blocking** | Nothing. P6 (integration & observability — tools/MCP/A2A/context/streaming) is next. |
| **Pushed / merged** | `develop` (P0–P4) is pushed to `origin`. P5.1–P5.6 are committed on `feat/p5-model-routing`; the completed phase merges to `develop` next (awaiting user authorization). |

Every local gate is green: ruff, ruff-format, `mypy --strict` (73 source files), `pytest` (dspy +
non-dspy paths; **368 passed**, 94.55% cov, 9 Temporal excluded), import-linter (**4 contracts
kept**, incl. the ADR-0011 httpx confinement), the isolation gate, env-confinement, and version
single-sourcing. `import korchestrator.agents`/`korchestrator.routing` stay `dspy`/`[routing]`-free;
the base install stays `pydantic`-only.

## 2. Phase progress

| Phase | Title | Status |
|---|---|---|
| P0 | Foundations, scope freeze, scaffolding | **Complete** (branch `chore/p0-foundations`) |
| P1 | Public API & interface contracts | **Complete** (branch `feat/p1-contracts`) |
| P2 | Core execution kernel (Pregel) | **Complete** (merged to `develop`) |
| P3 | Runtime adapters (local + Temporal) | **Complete** (merged to `develop`) |
| P4 | Cognitive layer (agents, signatures, taxonomy) | **Complete** (P4.1–P4.9; first end-to-end run) |
| P5 | Model routing | **Complete** (P5.1–P5.6; routing wired into execution) |
| P6 | Integration & observability (AUB, MCP, A2A, streaming, context) | Not started — next |
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
| `services/` | Façade | **tested** (`Korch.run`/`Swarm.run` wired to the kernel via `_composition`; first end-to-end run) | P1, P4 |
| `core/` | Kernel (L1) | **tested** (reducers + laws, AgentGraph, ChannelSchema, PregelRunner; determinism-locked; ≥97% cov) | P2 |
| `runtime/` | Adapter | **tested** (LocalRuntime + resolve_runtime; TemporalRuntime PregelMaster/SuperstepActivity, retry/rollover, HITL signals; equivalence/replay/crash/rollover verified) | P3 |
| `providers/` | Adapter | **tested** (MockLM; local identity + subprocess sandbox; OpenAI gateway + `get_lm`; 99% cov) | P4 |
| `agents/` | Cognitive (L2) | **tested** (unified `Agent`; lazy DSPy `Signature`s; `WorkerAgent` + `ArchitectAgent` over a shared gateway bridge; 97% cov) | P4 |
| `taxonomy/` | Cognitive (L2) | **tested** (`TaxonomyClassifier` + agent descriptors; 100% cov) | P4 |
| `routing/` | Cognitive (L2) | **tested** (explicit+fallback default, algorithmic, semantic `[routing]`, composite, user-function behind one `BaseRouter`; `get_router`/`resolve_router`; model-card catalogue; wired into execution) | P5 |
| `context/` · `persistence/` · `tools/` · `mcp/` · `a2a/` · `governance/` · `security/` · `events/` · `clients/` · `serializers/` · `validators/` · `telemetry/` · `logging/` | see spec 05 | **stub** (skeleton `__init__` with docstring + `__all__`) | P6–P9 |

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
| `IDurableRuntime` shape | `now`/`start`/`wait`/`signal`; graph injected at construction | 0010 |
| `httpx` confinement | Owned by `clients/` + `providers/gateway_openai.py` (lazy, `[remote]`); machine-enforced (direct-import) | 0011 |
| Unified `Agent` | One class — declarative **and** subclassable; re-exported from `agents`/`services`/top level | 0012 |
| Cognitive layer needs `[dspy]` | One reasoning path (DSPy `WorkerAgent`); base install imports clean, `MissingExtraError` on run; target dspy 3.x (`dspy>=2.6,<4`) | 0013 |
| Custom router registration | By injection (`Korch(router=)`/`resolve_router`); `ROUTING_STRATEGY` selects built-ins only; entry-point discovery deferred | 0014 |

## 6. Known gaps and open items

| Item | Detail | Owner / when |
|---|---|---|
| Compliance checks named in ADRs | `version-validate`, the isolation gate, and env-confinement now **exist and pass** (`scripts/`). The import-purity subprocess test (ADR 0004) and the event-history shape test are still owed by P2/P3. | P2, P3, P9 |
| Coverage floor enforced | Global 80% is wired (`fail_under=80`) and green (100% at this size); `core/`+`models/` 95% checked in CI. Ratchet from P2 as behaviour lands. | P2+ |
| `import-linter` contracts configured | `.importlinter` with 3 contracts (framework-free, layers, feature-independence); `lint-imports` reports 3 kept, 0 broken. `include_external_packages=True` added (import-linter requirement, omitted from spec §9 snippet). | ✔ P0 |
| Manifest corrections during P0 | `--xfail-strict` → `xfail_strict=true` (spec named a nonexistent pytest flag); `import-linter` added to `[dev]`. Both recorded in the engineering log. | ✔ P0 |
| `ConfigurationError` vs `ValidationError` overlap | Both nominally cover "invalid configuration". `ConfigurationError` now has call sites (env-parse failures, bad model-card source/file in P5), but is still not in top-level `__all__`; spec 08 §1.2 says `configure()` raises `ValidationError`. Resolve via ADR (specify which failures use which, and whether `ConfigurationError` joins `__all__`) **before `configure()` lands**. Raised by the P1 API review. | P8 |
| `ToolError` default code is specific | `ToolError.default_code = TOOL_NOT_FOUND` — a raiser that omits `code=` gets a misleading "not found". No raiser exists until the tool bridge (P6); revisit then (generic default or required `code`). Raised by the P1 API review. | P6 |
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
