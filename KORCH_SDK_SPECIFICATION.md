<!-- Copyright (c) 2026 Kendra Laboratories Limited. All rights reserved. -->

# Korchestrator SDK — Framework & Library Build Specification

**Document type:** Implementation specification (companion to [`PRODUCTION_HARDENING_SPECIFICATION.md`](PRODUCTION_HARDENING_SPECIFICATION.md) and [`PRODUCTION_READINESS_AUDIT.md`](PRODUCTION_READINESS_AUDIT.md))
**Working branch:** `feature/korch-sdk` (a dedicated branch; do not commit to `dev`/`main`)
**Status:** Active build plan — Phases 0–12 in scope; Phase 13 (backend re-platform) is **future / out of scope / approval-gated**.
**Audience:** Any engineer or AI agent building the Korchestrator SDK. This document plus the referenced docs are self-sufficient.

---

## 0. Golden Rules (read first — these override everything)

1. **You build ONE thing: the SDK package under `packages/korchestrator/`.** Your entire purpose is to create this installable library. Nothing else.
2. **Do NOT alter `backend/`, `frontend/`, `apps/`, `services/`, `website/`, or any other module.** They are read-only reference. You *read* their code to understand behavior and *re-implement/relocate* the needed logic **inside** the SDK package. You never edit them. (Wiring the backend to consume the SDK is a **separate future effort** — see Phase 13, out of scope here.)
3. **The `packages/korchestrator/` package must be self-contained.** It must **not import from `backend.*`, `frontend`, `apps.*`, `services.*`, or any sibling in-repo package.** Its only dependencies are declared in its **own** `pyproject.toml` (a tiny core + optional extras). This is what lets it be built and published independently via a GitHub Actions release.
4. **Be dynamic, not hardcoded.** Everything configurable is config-driven and runtime-swappable (providers, runtime, router, persistence) behind interfaces. No hardcoded URLs, keys, models, or paths.
5. **Do not over-engineer.** Prefer the simplest correct design. Add only the abstraction the current requirement needs. Package the capabilities the engine already has — do not invent new product surface.
6. **Preserve behavior.** The SDK repackages an existing, working engine. Prove parity with tests; do not change what the product does.

---

## 1. Purpose & How to Use This Document

This spec defines **how to build the Korchestrator SDK** — a production-grade, installable Python (and TypeScript) library that packages the Korchestrator durable multi-agent orchestration kernel as a reusable framework, so developers integrate Korchestrator through **code** instead of editing the engine or hand-rolling HTTP.

It has two parts:

- **§2–§11 — Standards & context.** What Korchestrator is (the full vision and every functionality), what makes it different, the engineering/git discipline, package-isolation rules, the target structure, the public API, and the cross-cutting + release standards. These govern every phase.
- **§12 — Build phases (0–13).** The ordered implementation plan. Each phase: Objective · Build (what to create, from which existing module) · Public surface · Validation · Completion criteria.

**How to read it:** read §2–§11 once; then execute §12 phases **strictly in order**. Use §14 as the master checklist. For deeper engine detail, consult the docs referenced inline (they are read-only sources, not files to change).

> **Prime directive.** The SDK is a **product for developers**. Its success depends as much on architecture, stability, documentation, testing, versioning, and developer experience (DX) as on the engine underneath.

---

## 2. Context & Background — What Korchestrator Is

### 2.1 The vision: the Execution Kernel of the Agentic Enterprise

Korchestrator (Kendra Orchestrator) positions itself as **the Execution Kernel of the Agentic Enterprise** — an **Enterprise Agentic Operating System**, not a script runner or a prompt chainer. Its intended evolution:

```
Automation → Workflow Engine → Agent Framework → Enterprise Agentic Operating System
```

Instead of executing a fixed script or a DAG, it **continuously coordinates hundreds-to-thousands of autonomous AI agents** that collaborate to satisfy a high-level objective. It is built on three infrastructure primitives:

1. **Temporal.io** — durable workflow execution. Every superstep is checkpointed → crashes lose no progress, execution resumes, replay/time-travel debugging is possible, deterministic recovery, and native human-in-the-loop pause/resume via durable signals (up to 24h).
2. **Pregel (Bulk Synchronous Parallel) model** — the parallel engine. All active agents compute in parallel, exchange typed messages over directed edges, then a global synchronization barrier merges outputs via deterministic **reducers** — no locks, no races.
3. **DSPy — Compiled Signatures** — reasoning as declarative, typed, optimizable, **versioned** programs (a "compiled signature"), not a fragile prompt string. Each agent can run on a **different model** in the same superstep via scoped `dspy.context(lm=...)`.

### 2.2 Why traditional orchestrators fail — the differentiators

The whole reason the SDK exists is that traditional DAG/workflow/prompt-chaining orchestrators break at enterprise-scale autonomous AI. Encode this positioning in the README, the architecture guide, and the public API shape:

| Traditional systems | Korchestrator |
|---|---|
| Linear **DAG** / sequential pipelines / fixed paths | **FractalFlow** — recursive, event-driven, self-correcting, parallel, resilient, continuously adapting |
| **Stateless** execution | **Event-sourced** execution (durable, replayable) |
| Vector **RAG** / prompt memory | **Context Graph** (bitemporal, governed, provenance, confidence) |
| **Prompt-based**, fragile | **Compiled Signatures** (deterministic, reproducible, reusable, versioned) |
| Workflow scripting | **Agent Operating System** |
| No memory · hard recovery · poor coordination | Durable memory · deterministic recovery · synchronized coordination |

**The coordination-explosion problem.** As enterprises move from `A → B → C` to every-agent-may-talk-to-every-agent (`A ↔ B ↔ C ↔ …`), coordination complexity grows ~**O(N²)** and ad-hoc orchestration becomes impossible. The answer is a **central execution kernel** that owns scheduling, synchronization, and communication — which is exactly what the SDK exposes.

**FractalFlow vs DAG.** Instead of `Task1 → Task2 → Task3`, execution is a continuous loop:

```
event → decision → branch → parallel agents → merge → feedback → repeat
```

### 2.3 The Six Principles (design pillars the SDK must preserve)

1. **Workflows must survive failures** — Temporal + event sourcing + durable execution → crashes don't lose progress, replay possible, deterministic recovery.
2. **Context is the execution substrate** — not prompt memory. Context layers (system, semantic, execution, environment, interaction) unify into **one Context Graph**.
3. **Universal tool connectivity** — one unified tool layer over APIs, cloud apps, databases, **MCP**, external services (the AUB) — instead of bespoke integrations.
4. **Meta-agents** — **Architect Agents** that generate, optimize, and synthesize other agents' workflows/execution graphs.
5. **Deep observability** — execution graph, agent reasoning, event tracing, context evolution, decision history, dependencies — far beyond `print()`.
6. **Zero-trust governance** — policy enforcement, approval workflows, permissions, auditing, security boundaries, human approval inserted where required.

### 2.4 The Five-Layer Control Plane (the architecture the SDK packages)

| Layer | Name | Responsibilities | SDK home |
|---|---|---|---|
| **L1** | **Runtime Kernel** | Execution loop, scheduling, synchronization (Pregel supersteps), communication, computation. Backed by Temporal + Postgres. | `core/`, `runtime/` |
| **L2** | **Cognitive Reasoning** | Planner, LLM routing, reasoning, task decomposition, validation — the "AI thinking layer." | `agents/`, `routing/` |
| **L3** | **Context Management** | Context Compiler, memory, state, event sourcing, Context Graph — enterprise memory. Includes **Minimum Viable Context (MVC)** extraction. | `persistence/`, `context/`, `models/state.py` |
| **L4** | **Interface & Tool Integration** | APIs, MCP, applications, enterprise systems, search, databases — everything external connects here. | `tools/` (AUB), `mcp/` |
| **L5** | **Governance & Security** | RBAC, authn/authz, audit logs, encryption, policy engine, PII/Shield, HITL. | `governance/`, `security/` |

**Runtime execution loop (L1):** `Receive event → Reason → Schedule → Execute → Synchronize → Communicate → Repeat.`

### 2.5 Complete functionality catalogue (package ALL of these)

Every functionality below already exists in the engine and must be reachable through the SDK's public surface. This table is the coverage contract — each maps to an SDK module and a build phase.

| Category | Functionality | SDK module | Phase |
|---|---|---|---|
| **Execution** | Durable, distributed, parallel, recursive, event-driven execution; recovery; scheduling; synchronization barriers | `core/`, `runtime/` | P2, P3 |
| **Agent management** | Multi-agent coordination; meta-agents; planner agents; **Architect** agents; autonomous execution; per-agent model isolation | `agents/` | P4 |
| **Context** | Context Compiler; Context Graph (bitemporal); memory management; context layering; **Minimum Viable Context (MVC)**; event sourcing; context pruning/summarization | `context/`, `persistence/` | P3(kernel), P7 |
| **Reasoning** | Task decomposition; planning; validation; **LLM routing** (v2.1); intent + difficulty classification (taxonomy); decision making; **compiled signatures** | `agents/`, `routing/`, `taxonomy/` | P4, P5 |
| **Integration** | Unified tool layer (AUB); **MCP** integration; API/cloud/database/enterprise-tool connectors; **A2A** typed message passing | `tools/`, `mcp/`, `a2a/` | P6 |
| **Governance & security** | Trust scoring; policies; RBAC; audit logs; **human approval / HITL**; compliance; PII/Shield redaction; zero-trust boundaries | `governance/`, `security/` | P7 |
| **Observability** | Execution tracing; agent-reasoning traces; context tracing; event logs; decision history; real-time **streaming** (SSE / AG-UI); OTel metrics/traces | `events/`, `telemetry/` | P6, P8 |
| **Scalability** | Distributed execution; independent vertices; horizontal scaling; failure recovery; synchronization barriers | `core/`, `runtime/` | P2, P3 |
| **Interface** | Local one-liner, typed swarm builder, kernel-direct embed, and remote HTTP client | `services/`, `clients/` | P2–P9 |

**End-to-end flow the SDK must be able to drive:**

```
User Goal → Intent Analysis → Planner (Cognitive) → Compiled Signature → Context Compiler
→ Minimum Viable Context → FractalFlow Graph Generation → Meta-Agent Optimization
→ Task Scheduling → Parallel Agent Execution → Tool/API/MCP Integrations
→ Synchronization (Pregel Supersteps) → Context Updates & Event Sourcing
→ Governance & Policy Validation → Observability & Tracing → Final Response / Continuous Execution
```

### 2.6 What makes this SDK different from LangChain / CrewAI / AutoGen

| Dimension | LangChain / CrewAI / AutoGen | **Korchestrator SDK** |
|---|---|---|
| Failure model | In-memory / ephemeral — a crash loses all progress | **Durable-by-default** (Temporal event sourcing): resumes from last superstep |
| Concurrency | Ad-hoc sequential/async; shared-state races | **Deterministic Pregel BSP** with conflict-free reducers |
| Model use | One model per chain (typically) | **Per-agent model isolation** — heterogeneous models in one parallel step |
| Memory | Flat string / vector RAG | **Bitemporal governed Context Graph** + MVC compiler |
| Prompts | Fragile prompt strings | **Compiled Signatures** (typed, versioned, reproducible) |
| Human-in-the-loop | Bolt-on callbacks | **Native durable HITL** via signals (pause up to 24h) |
| Governance | None / bolt-on | **Zero-trust governance** (trust scores, policy, audit, approval) |
| Portability | Framework-coupled | **ARI ports** (Identity, Sandbox, Model Gateway) — runs local with just a key, or plugs into Kendra enterprise services with no agent-logic change |

The SDK is **not** a generic prompt-chaining toolkit. It is a durable execution substrate for long-running, auditable, governed, multi-model agent workflows.

### 2.7 Why an SDK, and the SDK-first architecture

Today the engine lives in `backend/` and is usable only by (a) running it as a service and driving REST/WebSocket, or (b) editing repo source (add a `dspy.Module`, a connector, a topology). There is **no installable library**. The existing `sdk/` is only a thin remote HTTP client (§2.9).

The docs already anticipate this: the **Standalone Execution Kernel** spec ([`docs/architecture/korchestrator-standalone-spec.md`](docs/architecture/korchestrator-standalone-spec.md)) defines Korchestrator as *"a standalone Python library … without being tied to any specific platform, model provider, or security engine,"* interacting with the outside world only through the **Agent Runtime Interface (ARI)**. This SDK realizes that.

Target architecture (SDK-first):

```
korchestrator  (SDK / framework — the product: kernel + ARI ports + agents + routing + tools + governance)
      ▲ (future) built on top of
backend/api    (FastAPI service — a THIN adapter that imports the SDK and adds HTTP/auth/tenancy)   ← Phase 13, NOT in scope now
      ▲ called by
korchestrator-client  (remote SDK — the existing thin HTTP client, folded in for remote consumers)
```

### 2.8 The ARI ports (the portability contract)

The SDK interacts with the outside world only through three abstract ports, each with a local default and a Kendra implementation:

| Port | Role | Local default | Kendra implementation |
|---|---|---|---|
| `IIdentityProvider` | Authenticate agents → DID | Local (unsecured) identity | KIAM / KACP |
| `IExecutionSandbox` | Isolated tool/code execution | Local subprocess | OpenSandbox |
| `IModelGateway` | Route reasoning to an LLM | Direct OpenAI/Anthropic / gateway | Kendra AI Gateway |

A developer can run the SDK with **just an OpenAI key and a local process**; as they scale they plug in KACP/OpenSandbox/gateway **without changing agent logic**.

### 2.9 What exists today (fold in — do not duplicate)

- **`sdk/python` — `korchestrator` v0.2.0.** A thin async+sync **HTTP client** (only dep: `httpx`). Methods: `run`, `run_swarm`, `get_run`, `wait`, `run_and_wait`, `run_sync`, `list_runs`, `get_run_summary`, `me`, `my_quota`, `my_runs`, `resume`, `cancel`. Models: `RunResult`, `AgentMessage`, `RunStatus`. Exceptions: `KOrchestratorError`/`AuthError`/`QuotaExceededError`/`RunTimeoutError`/`RunFailedError`.
- **`sdk/typescript` — `@kendralabs/korchestrator-sdk`.** Fetch-based client (Node 18+, zero runtime deps) with the same surface plus admin key management.
- **`sdk/SDK_REFERENCE.md`.** The 1093-line reference for the remote HTTP surface (see §13 for the concepts/auth/lifecycle detail the SDK's remote client must honor).
- **`docs/specs/dashboard/epic-9-sdk.md`.** The approved TypeScript-SDK epic (E9): auth (API key **or** KIAM JWT), retries with backoff, streaming, `waitForCompletion`, dual CJS/ESM, `msw` tests, npm publish on version tag, types from the engine OpenAPI via `openapi-typescript`. These are requirements for Phase 9.

> **Naming (record as ADR).** Flagship framework = Python package **`korchestrator`**. The thin HTTP client = **`korchestrator-client`** (TS twin stays `@kendralabs/korchestrator-sdk`). The framework MAY re-export a `korchestrator.remote` submodule wrapping the client; they are versioned/packaged separately.

### 2.10 Known drift to fix while building (do not carry forward)

- README typo `Kendra OrchestratorClient` (space) → `KOrchestratorClient`.
- Python client documents `create_key`/`list_keys`/`revoke_key` and a `task_queue` param that **do not exist in code**; TS has the key methods but no `taskQueue`. Reconcile to explicit Python/TS parity.
- Version drift: package `0.2.0`, `SDK_REFERENCE.md` `0.1.0-beta.1`, standalone spec `3.0.0`, master arch `v2.4.0`. Ship **one** authoritative version (§10.7); reconcile in Phase 0.
- epic-9 uses `Authorization: Bearer` + `launch`/`launchSwarm` naming; the shipped client uses `X-API-Key` + `run`/`run_swarm`. Pick one contract per the live engine and document the parity matrix (Phase 9).

---

## 3. Definition of "Production-Grade" (the whole-SDK Definition of Done)

An SDK lets developers integrate through code. Production-grade = **Easy to install · learn · document · extend · test · upgrade; Modular · Stable · Backward-compatible · Secure · Performant.** Every box below must be checked before release:

- [ ] Clean, modular architecture with a stable, curated public API
- [ ] Self-contained package (no internal-repo imports); own `pyproject.toml`; independently publishable
- [ ] Semantic Versioning + documented compatibility/deprecation policy
- [ ] Full type hints; typed responses; `py.typed`; `mypy --strict` clean; IDE autocomplete
- [ ] Tests: unit, integration, e2e, regression, performance, smoke — with an enforced coverage floor
- [ ] CI/CD: lint, format, type-check, security scan, build, version-validate, docs-build, publish (GitHub Actions release)
- [ ] Docs: install, quickstart, tutorials, API reference, architecture, examples, migration, FAQ, troubleshooting
- [ ] Secure config (no hardcoded secrets), input validation, output sanitization (PII/Shield)
- [ ] Custom exception hierarchy; no raw internal exception leaks
- [ ] Configurable logging + optional telemetry (OTel metrics/tracing)
- [ ] Executable examples for every common use case
- [ ] Extensible plugin/provider/middleware/hook system
- [ ] Performance: lazy loading, caching, efficient imports, real parallelism
- [ ] OSS-readiness files (LICENSE, README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates)

---

## 4. Core Principles (apply to EVERY task)

- **SRP / OCP / DIP** — one concern per module; extend via new providers/plugins, not by editing core; depend on **interfaces** (ARI ports, protocols), never concrete infra.
- **Composition over inheritance · Separation of concerns · Interface-driven design.**
- **Convention over configuration** — zero-config local run with just a model key (or MockLM).
- **Dependency injection at the edges** — no import-time global singletons; collaborators are injected.
- **Explicit over implicit · API-first design · DX first** — common tasks in minimal code.
- **Backward compatibility · SemVer** — never break the public API without a major bump + migration guide.

**Korchestrator-specific invariants:**

- **`core` is framework-free.** The kernel must not import FastAPI/HTTP/Temporal/DSPy. (Already true for the engine's `core/runtime`, `core/state`, `agent_graph`, context-graph client — that is the extraction seam.)
- **One implementation per concern.** Never a second router, PII redactor, error base, or config source. Variation = one interface + strategy.
- **Determinism inside workflows.** No wall-clock/`random` in workflow-path code; use the runtime's clock; preserve Temporal sandbox constraints.
- **Behavior-preserving.** Repackaging must not change what the engine does; prove with parity tests.

---

## 5. Package Isolation & Scope Rules (hard boundaries)

These make the golden rules (§0) enforceable:

1. **The SDK package imports nothing from the repo.** No `from backend...`, `from apps...`, `from services...`, no sibling-package imports. If the SDK needs engine logic, **relocate a self-contained copy** into the SDK package (framework-free code lifts cleanly; contaminated code is re-implemented minimally). CI enforces this with an import-linter/grep gate: any `backend.`/`apps.`/`services.` import in `packages/korchestrator/src` **fails the build**.
2. **Own dependency manifest.** `packages/korchestrator/pyproject.toml` declares its own deps: a tiny core (`pydantic` only) plus **optional extras** (§10.6). It never inherits the backend's `pyproject`.
3. **Touch only the SDK package.** All work happens under `packages/korchestrator/` (and, for the TS client, `packages/korchestrator-client-ts/`). Do not modify `backend/`, `frontend/`, `apps/`, `services/`, `website/`, or root configs — except adding the package to the workspace member list and its own CI workflow file.
4. **Dynamic, not hardcoded.** Runtime (local/Temporal), model gateway, router strategy, and persistence backend are all selected by config at runtime behind interfaces. No hardcoded endpoints, keys, models, or file paths anywhere in the package.
5. **Independently releasable.** Because it is self-contained with its own manifest and CI, the package builds to a wheel/sdist and publishes on a version tag via GitHub Actions with **no dependency on the rest of the monorepo building**.

---

## 6. Engineering, Git & Commit Discipline (from the hardening standard)

Apply the repository's existing engineering standard to all SDK work:

**Branching & commits**
- Work only on the dedicated SDK branch (`feature/korch-sdk`). **Never commit to `dev` or `main`.**
- Commit **phase-wise or task-wise** — not one giant commit. Prefer one commit per coherent unit.
- **Conventional-commit** messages, professional and descriptive, referencing the phase/story. Examples:
  - `feat(sdk): scaffold korchestrator package with pydantic-only core [P0]`
  - `feat(sdk-core): lift framework-free Pregel kernel + reducers [P2]`
  - `feat(sdk-routing): package v2.1 routers behind BaseRouter [P5]`
  - `test(sdk): add parity tests vs engine pregel runner [P2]`
- **No co-author trailers.** Each commit leaves the package **green** (build + tests pass).

**Definition of Done per phase** — a phase is complete only when: all its tasks are done; all tests pass and behavior changes are covered by tests; `ruff` + `mypy --strict` are clean on the package; the phase's Validation and Completion Criteria pass; work is committed with professional messages; the §14 checklist row is checked.

**ADR discipline** — record non-obvious decisions (naming, version, license, extras matrix, runtime split) as short ADRs in `packages/korchestrator/docs/adr/`. Any structural deviation from this spec needs an ADR + reviewer sign-off.

**Anti-patterns to reject in review (hard "no")** — a second copy of a concern (router/PII/errors/config); a framework import inside `core/`; a feature smeared across horizontal `models/`/`utils/` instead of one module; a God file (>~500 lines) or God function (>~50 lines); a sideways import between sibling SDK modules or a cycle; a raw `os.getenv`/hardcoded endpoint outside `config/`; **any import from `backend`/`apps`/`services`.**

---

## 7. Target SDK Package Structure (professional, publish-ready)

The SDK is a **package under the monorepo** (`packages/`, per the hardening standard §6.5), self-contained, with an internal layout that follows the universal SDK standard mapped onto Korchestrator's real modules.

### 7.1 Layout

```text
packages/korchestrator/                 the SDK / framework (Python) — self-contained, independently publishable
├── src/
│   └── korchestrator/
│       ├── __init__.py                  PUBLIC API — the only surface users import (explicit __all__)
│       ├── py.typed                     ships type information
│       ├── version.py                   single source of truth for the version
│       ├── config/                      typed Settings (arg > env > file > default); the ONLY place env is read
│       ├── interfaces/                  ARI ports + protocols (the contracts)
│       │   ├── identity.py              IIdentityProvider
│       │   ├── sandbox.py               IExecutionSandbox
│       │   ├── model_gateway.py         IModelGateway
│       │   ├── runtime.py               IDurableRuntime (Temporal/local behind one port)
│       │   ├── repository.py            GraphRepository / TenantStore protocols
│       │   ├── router.py                BaseRouter protocol
│       │   └── connector.py             AUBConnector / tool protocols
│       ├── core/                        FRAMEWORK-FREE kernel (Pregel) — pydantic only
│       │   ├── pregel.py                PregelRunner (run_superstep + synchronize)
│       │   ├── graph.py                 AgentGraph, Node, Edge, topology builder
│       │   └── reducers.py              reducer_append / reducer_merge_dict / reducer_last_value
│       ├── models/                      Pydantic domain models (DTOs)
│       │   ├── state.py                 AgentState, StateUpdate, Message, Performative, RunStatus
│       │   ├── agent.py                 AgentConfig, AgentPersona, AgentDescriptor
│       │   ├── plan.py                  ExecutionPlan, TaskDecomposition (compiled-signature plan)
│       │   └── routing.py               ModelCard, TaskSemantics, RoutingResult, RoutingContext
│       ├── agents/                      L2 Cognitive — DSPy intelligence (extra: [dspy])
│       │   ├── worker.py                WorkerAgent (TypedPredictor + ReAct loop)
│       │   ├── architect.py             ArchitectAgent (meta-agent: intent + plan)
│       │   ├── signatures.py            DSPy Signatures (compiled signatures)
│       │   └── base.py                  Agent base + think(state)->StateUpdate contract
│       ├── taxonomy/                    intent/difficulty classification + agent descriptors
│       ├── routing/                     L2 model routing v2.1 (strategies behind BaseRouter)
│       ├── runtime/                     L1 durability adapters implementing IDurableRuntime
│       │   ├── local_runtime.py         in-process (no Temporal) — dev/embed default
│       │   └── temporal_runtime.py      Temporal adapter (extra: [temporal])
│       ├── context/                     L3 Context Compiler + MVC + pruning/summarization
│       ├── persistence/                 L3 Context Graph client + backends (in-memory/mock/neo4j/pg)
│       ├── providers/                   default ARI implementations
│       │   ├── identity_local.py · sandbox_local.py · gateway_openai.py · mock_lm.py
│       ├── tools/                       L4 Agent Utility Bridge (AUB)
│       │   ├── bridge.py · registry.py · connectors/ (base + search + file_system)
│       ├── mcp/                         L4 MCP client + tool registry
│       ├── a2a/                         A2A typed message passing / handoff transformer
│       ├── governance/                  L5 trust scoring, HITL, policy
│       ├── security/                    L5 Shield / PII redaction, secret handling, sanitization
│       ├── events/                      streaming / AG-UI publisher (transport-agnostic)
│       ├── clients/                     remote client (korchestrator.remote) (extra: [remote])
│       ├── services/                    high-level façade (Korch / Swarm / Agent builders)
│       ├── serializers/                 object<->JSON/dict/YAML (version-tagged)
│       ├── validators/                  input/config/response/runtime validation
│       ├── telemetry/                   optional OTel metrics + tracing (extra: [otel])
│       ├── logging/                     namespaced, disable-able logging (no root-logger mutation)
│       ├── exceptions/                  custom exception hierarchy
│       ├── types/                       shared typing/Protocols/TypedDicts
│       └── constants/                   defaults, enums, error codes
├── tests/                              unit / integration / e2e / regression / smoke
├── examples/                           executable examples (local + remote)
├── docs/                               SDK docs source + docs/adr/
├── scripts/                            build/release/validation scripts
├── benchmarks/                         performance suites
├── .github/workflows/                  release.yml (build+publish on tag), ci.yml
├── pyproject.toml                      OWN manifest — pydantic core + optional extras
├── README.md · LICENSE · CHANGELOG.md · CONTRIBUTING.md
├── CODE_OF_CONDUCT.md · SECURITY.md · MANIFEST.in
├── .gitignore · .editorconfig · .pre-commit-config.yaml
└── mkdocs.yml                          (or feed the existing website/ Docusaurus site)
```

**TypeScript client** lives at `packages/korchestrator-client-ts/` (`@kendralabs/korchestrator-sdk`), mirroring the remote surface only, with dual CJS/ESM build and its own release workflow (§10.8, Phase 9).

### 7.2 Layering & dependency rule (hard "no" in review)

```
services (façade) → agents → core (Pregel) → interfaces / models
        │                        ▲
        └── routing, tools, mcp, a2a, governance, persistence, context, events, runtime  → depend inward on interfaces/models
providers, runtime/temporal → implement interfaces (depend inward only)
config, exceptions, logging, telemetry, serializers, validators, security → leaf utilities (no upward deps)
```

- `core/` imports only `interfaces/` + `models/` + stdlib + `pydantic`. **No** FastAPI/HTTP/Temporal/DSPy.
- `agents/` may import `dspy`; `runtime/temporal_runtime.py` may import `temporalio` — both **optional extras**, lazy-imported.
- No sideways imports between sibling feature folders; communicate via `interfaces`/`models`.
- **No import of any in-repo package** (§5).

---

## 8. Public API Design

Users interact with a **small, curated surface** — everything else is internal. `__init__.py` exports only public names via explicit `__all__`. Every public callable has full type hints + a docstring with an example. Public functions return typed models (e.g. `RunResult`), not raw dicts.

**Four tiers of use, all from `from korchestrator import ...`:**

```python
# Tier 1 — one-liner (local, zero infra; MockLM or a model key from env)
from korchestrator import Korch
print(Korch().run("Research durable agent execution and summarize the top 3").final_answer)

# Tier 2 — build a swarm explicitly (typed, fan-in topology)
from korchestrator import Swarm, Agent
swarm = (Swarm(objective="Review this PR for security and performance")
    .add(Agent(id="security", role="security-reviewer", model="claude-3.5-sonnet"))
    .add(Agent(id="perf",     role="performance-reviewer", model="gpt-4o-mini"))
    .add(Agent(id="lead",     role="review-lead"))
    .edges([("security", "lead"), ("perf", "lead")]))
result = swarm.run(max_supersteps=5)

# Tier 3 — kernel directly (embed / advanced)
from korchestrator.core import PregelRunner, AgentGraph
from korchestrator.models import AgentState
state = await PregelRunner(graph=my_graph, model_gateway=my_gateway).run_superstep(state)

# Tier 4 — remote (drive a hosted engine)
from korchestrator.remote import KorchestratorClient
result = KorchestratorClient("https://engine.example.com", api_key="sk-...").run_and_wait("...")
```

---

## 9. Cross-Cutting Standards (apply to every phase)

- **9.1 Configuration** — precedence **arg > env > `.env` > default**; one typed `Settings` (`pydantic-settings`) is the only place env is read; map every engine env var (§13.5); zero-config local default = MockLM.
- **9.2 Type safety** — full hints, typed responses, `py.typed`, `mypy --strict` clean.
- **9.3 Error handling** — one hierarchy rooted at `KorchError`: `AuthError`, `ValidationError`, `NetworkError`, `ProviderError`, `TimeoutError`, `RateLimitError`, `QuotaExceededError`, `RoutingError`, `GovernanceHaltError`, `RunFailedError`, `RunTimeoutError`, `ToolError` (codes `TOOL_NOT_FOUND`/`TOOL_ACCESS_DENIED`/`NOT_IMPLEMENTED`). Never leak a raw `temporalio`/`httpx`/`dspy` exception — wrap it.
- **9.4 Logging** — namespaced `korchestrator` logger, off by default, fully disable-able; never mutate the root logger; no `print()`.
- **9.5 Observability** — optional OTel metrics + tracing behind a flag; zero overhead when off; deep traces (execution graph, reasoning, context evolution, decision history).
- **9.6 Security** — no hardcoded secrets; read secrets via Settings/secret provider; validate input; sanitize output (PII/Shield); fail **closed** for high-sensitivity flows.
- **9.7 Validation** — validate params, config, responses, runtime state; fail fast with actionable messages (objective ≥10 chars, graph validity, model resolvability, tool schema).
- **9.8 Serialization** — round-trip `AgentState`/`AgentGraph`/`ExecutionPlan`/`ModelCard`/`RunResult` between object⇄JSON⇄dict⇄YAML; deterministic, version-tagged.
- **9.9 Extensibility** — developers can add providers (ARI), routers (`BaseRouter`), tools/connectors (`AUBConnector`), MCP servers, persistence backends (`GraphRepository`), middleware (pre/post superstep, pre/post tool), and hooks/events (on-superstep, on-message, on-governance-pause) — all behind the composition root, never editing core.
- **9.10 Performance** — lazy-import heavy extras (`dspy`, `temporalio`, `sentence-transformers`); cache router/embedding singletons; idempotent LM caching; run blocking DSPy via `asyncio.to_thread` for real parallelism; ship state deltas per superstep.
- **9.11 DX** — easy install/config/debug/extend/test/upgrade; actionable errors; first-class autocomplete.

---

## 10. Release Engineering Standards

- **10.1 Testing** — unit, integration, e2e, regression, performance, smoke; coverage floor enforced (baseline then ratchet). MockLM makes the full agent path runnable in CI with no network.
- **10.2 Documentation** — install, quickstart, tutorials, API reference (autogenerated), architecture, examples, migration, FAQ, troubleshooting. Feed the existing `website/` Docusaurus site with a new SDK section.
- **10.3 Examples** — executable-without-modification for: local one-liner, typed swarm, custom agent, custom tool/connector, custom router, MCP server, remote client, HITL pause/resume, streaming.
- **10.4 CI/CD** — lint (ruff), format, type-check (mypy), test+coverage, security scan (bandit/pip-audit/gitleaks), build, version-validate, docs-build, publish.
- **10.5 Code quality** — Ruff, ruff-format, MyPy, Pytest, Coverage, pre-commit.
- **10.6 Dependency management** — core depends only on `pydantic`. Extras: `[dspy]` (agents), `[temporal]` (durable runtime), `[routing]` (semantic/embedding routing), `[mcp]` (MCP tools), `[remote]` (HTTP client), `[otel]` (telemetry), `[all]`. Pin appropriately; minimize transitive deps.
- **10.7 Versioning & compatibility** — SemVer, single source in `version.py`, templated everywhere; reconcile the §2.10 drift at Phase 0; never break public API without a major bump; deprecate ≥1 minor before removal; ship migration guides; maintain `CHANGELOG.md`.
- **10.8 Packaging & publishing (GitHub Actions release)** — build wheel + sdist; ship `py.typed`; **publish on a `v*` version tag** via `.github/workflows/release.yml` (Python → internal registry / PyPI; TS → npm with `NODE_AUTH_TOKEN`, dual CJS/ESM via `dist/cjs` + `dist/esm` and `package.json` `exports`). SBOM + signed artifacts. Each release: version, changelog, migration notes, release notes, tested build, published docs.
- **10.9 OSS-readiness** — LICENSE (decide Apache-2.0/MIT/BSD vs Proprietary), README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates, GitHub Actions.

---

## 11. The SDK Development Lifecycle

```
Requirements → Architecture → Public API → Core Modules → Internal Implementation
→ Testing → Documentation → Examples → CI/CD → Package Build → Versioning → Publishing
→ Adoption → Feedback → Maintenance
```

§12 executes this in order.

---

## 12. Build Phases

> Each phase: **Objective · Build · Public surface · Validation · Completion criteria.** Execute in order. Every change is behavior-preserving over the engine and confined to the SDK package.

### PHASE 0 — Foundations, Scope Freeze & Scaffolding
**Objective:** Stand up the self-contained package skeleton; decide naming/version/license/extras; put the quality + isolation net in place.
**Build:** (1) Create `packages/korchestrator/` with the §7.1 layout (stub modules + `__init__.py`), its **own** `pyproject.toml` (name `korchestrator`, `hatchling`, `requires-python >=3.10`, core dep `pydantic` only, extras per §10.6), `version.py`, `py.typed`. (2) OSS-readiness files + `.pre-commit-config.yaml`. (3) ADRs: naming, one authoritative version, license, extras matrix. (4) CI: ruff, `mypy --strict` on the package, pytest+coverage floor, build check, **and the import-isolation gate** (fail on any `backend.`/`apps.`/`services.` import). (5) `.github/workflows/release.yml` skeleton (publish on `v*` tag).
**Public surface:** `__version__`.
**Validation:** `pip install -e packages/korchestrator`; `import korchestrator`; CI green including the isolation gate.
**Completion:** Package builds standalone; naming/version/license/extras ADR'd; CI + isolation gate active; version drift reconciled.

### PHASE 1 — Public API & Interface Contracts (ARI + Protocols)
**Objective:** Design the public surface and contracts first (API-first).
**Build:** (1) ARI ports in `interfaces/`: `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway` (abc/Protocol + documented contract + declared default). (2) Supporting protocols: `IDurableRuntime`, `GraphRepository`/`TenantStore`, `BaseRouter` (`async select_model(task, models) -> RoutingResult`), `AUBConnector` (`async execute(tool, args, invocation) -> ToolResult`). (3) Façade signatures (`Korch`, `Swarm`, `Agent`) + `__init__.__all__` — types only; §8 examples as doctests (xfail until implemented). (4) Freeze the exception hierarchy (§9.3).
**Public surface:** interfaces + exceptions + façade type signatures.
**Validation:** `mypy --strict` on interfaces; façade imports; doctests collected.
**Completion:** Every port/protocol defined + documented; façade API frozen; exception hierarchy final. (Anti-rework crux — no contract change after this without an ADR.)

### PHASE 2 — Core Execution Kernel (Pregel, framework-free)
**Objective:** Relocate the deterministic BSP engine as the dependency-light heart (pydantic only).
**Build:** (1) Re-implement (lift the framework-free code from `backend/core/state` + `backend/core/runtime`) into `models/state.py` (`AgentState`, `StateUpdate`, `Message`, `Performative`, `RunStatus`), `core/reducers.py`, `core/pregel.py` (`PregelRunner.run_superstep` via `asyncio.gather` + `synchronize`), `core/graph.py` (`AgentGraph`, `Node`, `Edge`, topology builder). Assert no framework/`backend.` imports remain. (2) Parameterize the runner to take an injected `IModelGateway`/agent-callable (DIP). Preserve activation rules (step 0 = all nodes; later = nodes with inbox messages; halt on `max_supersteps` default 10 or `halted=True`).
**Public surface:** `korchestrator.core`, `korchestrator.models`.
**Validation:** Port the engine's Pregel unit tests to run against the package with **only `pydantic`** installed; supersteps/reducers/routing/halting behave identically (parity test).
**Completion:** Kernel runs a superstep with only pydantic; behavior matches the engine on ported tests.

### PHASE 3 — Runtime Adapters (Local + Durable behind IDurableRuntime)
**Objective:** Run locally with no infra AND durably on Temporal — selected by config.
**Build:** (1) `runtime/local_runtime.py` — in-process `IDurableRuntime` driving the Pregel loop (no Temporal import). Default for embed/dev/CI. (2) `runtime/temporal_runtime.py` — re-implement the Temporal workflow/activity adapter behind `IDurableRuntime`, preserving determinism (`workflow.now()`, `patched()` gates), retry policy, HITL signals (pause/resume up to 24h), activity boundary. `temporalio` imported only here (extra `[temporal]`). (3) Config selects runtime (`KORCH_RUNTIME=local|temporal`).
**Public surface:** `Korch(runtime=...)`/Settings; `IDurableRuntime` for custom runtimes.
**Validation:** Same swarm completes on both runtimes with equivalent `RunResult`; Temporal replay test passes; forced mid-run crash resumes from last superstep.
**Completion:** Local runtime works zero-infra; Temporal preserves durability/HITL/determinism; runtime swappable by config.

### PHASE 4 — Cognitive Layer (Agents, Compiled Signatures, Taxonomy, Model Gateway)
**Objective:** Package the reasoning layer (L2) — meta-agents, workers, compiled signatures, intent taxonomy, model providers.
**Build:** (1) `agents/worker.py` (`WorkerAgent`: `TypedPredictor` + ReAct loop ≤3, per-agent `dspy.context`), `agents/architect.py` (`ArchitectAgent` meta-agent: intent+difficulty → `ExecutionPlan`), `agents/signatures.py` (compiled signatures), `agents/base.py` (`think(state)->StateUpdate`, `is_complete`). Extra `[dspy]`. (2) `taxonomy/` — intent/difficulty classification + agent descriptors. (3) `providers/`: `gateway_openai.py` (default `IModelGateway`), `mock_lm.py` (deterministic MockLM), `identity_local.py`, `sandbox_local.py`; `get_lm(model_name)` factory.
**Public surface:** `Agent`, `WorkerAgent`, `ArchitectAgent`, `Signature` base, taxonomy classifier, `IModelGateway` + providers.
**Validation:** A custom agent (new signature + `think`) runs under MockLM; heterogeneous per-agent models honored in one superstep; ported intelligence tests pass.
**Completion:** Agents run under MockLM with no network; real models via gateway; adding an agent needs no core edit.

### PHASE 5 — Model Routing Subsystem (v2.1)
**Objective:** Per-agent model selection as strategies behind one `BaseRouter`, simplest path default.
**Build:** `routing/` with models (`ModelCard`, `TaskSemantics`, `RoutingResult`, `RoutingContext`), `get_router()` factory, and strategies Explicit / Semantic / Algorithmic / Composite / UserFunction + legacy Financial fallback. Semantic/embedding + ModelCard-DB are opt-in (extra `[routing]`); Explicit + one fallback is default. Config: `ROUTING_STRATEGY`, `AGENT_MODEL_MAP`, `ROUTING_WEIGHTS`, `ROUTING_PRIORITY_ORDER`, `EMBEDDING_PROVIDER`, `MODELCARD_*`. Cache router/embedding singletons.
**Public surface:** `get_router()`, `BaseRouter`, routing models.
**Validation:** Explicit mapping picks the named model; custom `BaseRouter` plugs in via config; cost influences algorithmic ranking; embedding cache expires.
**Completion:** Routing works on the default (no-embedding) install; advanced strategies load only with the extra.

### PHASE 6 — Integration & Observability (AUB, MCP, A2A, Streaming, Context Compiler)
**Objective:** Package L4 tool integration, A2A messaging, real-time streaming, and the L3 context compiler/MVC.
**Build:** (1) `tools/` AUB — `bridge.py` (`invoke_tool`, schema validation, timeout, rate limiting, OTel spans, Shield gate), `registry.py` (`ConnectorRegistry` + plugin loading), `connectors/` (base + search + file_system, MockSearch fallback). Preserve `TOOL_ACCESS_DENIED`/`TOOL_NOT_FOUND`. (2) `mcp/` — MCP client + hierarchical tool registry. (3) `a2a/` — typed directed messages / `HandoffTransformer` (reads `messages`, passes structured findings). (4) `context/` — Context Compiler + **Minimum Viable Context** extraction + pruning/summarization (off-loop, graceful degradation). (5) `events/` — streaming / AG-UI publisher (transport-agnostic; SSE-capable). (6) Extension framework: `middleware`/`events` registration (pre/post-superstep, pre/post-tool, on-message, on-governance-pause).
**Public surface:** `AUBConnector`, `register_tool`/`register_connector`, MCP client, `register_middleware`, `on(event, handler)`, streaming subscriber, context compiler.
**Validation:** A custom connector is invokable by an agent; an MCP tool loads; a middleware/hook fires; MVC reduces token usage; Shield denies an over-privileged call.
**Completion:** Adding a tool/MCP server/hook needs no core edit; streaming + context compilation work.

### PHASE 7 — Governance, Security & Context Graph (Zero-Trust)
**Objective:** Package L5 governance + the bitemporal Context Graph (L3).
**Build:** (1) `governance/` — trust scoring (`ControlTowerTelemetry`), `check_governance`/intervention → runtime pause signal, HITL resume/modify/cancel, per-agent `hitl_threshold` with global `GOVERNANCE_TRUST_THRESHOLD` fallback, policy engine + audit. (2) `security/` Shield — the single consolidated PII redactor (PAN+Luhn, IBAN, intl phone, SSN, secrets), fail-closed for high-sensitivity flows. (3) `persistence/` — `ContextGraphClient` (bitemporal `DecisionNode`/`EventNode`, valid-time/transaction-time, confidence, provenance, event sourcing) behind `GraphRepository`; backends in-memory (default), mock, Neo4j/Postgres (extras). `PERSISTENCE_BACKEND=none` runs fully standalone.
**Public surface:** governance config on `Korch`/`Swarm`, HITL controls (`pause`/`resume`/`cancel`/`edit_resume`), `ContextGraphClient`, `GraphRepository`.
**Validation:** Run auto-pauses below threshold and resumes on signal; PII redaction covers required formats and fails closed; context-graph queries tenant-scoped + time-travel; standalone (no KCG) run completes.
**Completion:** Governance/HITL, Shield, Context Graph usable from the SDK; standalone default needs no external services.

### PHASE 8 — Config, Telemetry, Logging, Errors, Serialization, Validation
**Objective:** Finalize the §9 cross-cutting foundations as first-class, tested modules.
**Build:** `config/` (one typed `Settings`, precedence arg>env>file>default, every engine env var, zero-config MockLM default); `logging/` (namespaced, disable-able); `telemetry/` (optional OTel, zero-cost off, extra `[otel]`); `exceptions/` (finalized, wrapping all internal errors); `serializers/` (version-tagged round-trip); `validators/`; `security/` secret handling; `constants/` (error codes/defaults).
**Public surface:** `Settings`/`configure()`, `enable_logging()`, exceptions, `to_json`/`from_json`.
**Validation:** env read only inside `config/`; logging fully disable-able; every internal exception surfaces as `KorchError`; serialization round-trips stable across a version bump.
**Completion:** All §9 standards implemented + tested; no raw internal exception escapes; config single-sourced.

### PHASE 9 — Client SDKs (remote HTTP + TypeScript parity)
**Objective:** Fold the thin client into the SDK as `korchestrator.remote`, close its gaps, and ship the first-class TypeScript SDK (epic E9).
**Build:** (1) Relocate the Python thin client to `clients/`, re-export as `korchestrator.remote.KorchestratorClient` (extra `[remote]`). Honor the remote contract in §13 (auth header/scopes, run lifecycle, status normalization, webhook). Fix documented-but-missing methods (`create_key`/`list_keys`/`revoke_key`, `task_queue`); add wrappers for unwrapped endpoints (SSE `stream`, `edit-resume`, raw-`AgentState` submit, `tools`, `models`, `swarm-templates`). (2) TypeScript SDK per **epic-9-sdk.md**: `KorchestratorClient` with `baseUrl`, `apiKey?`/`accessToken?` (API key **or** KIAM JWT, mutually exclusive, `Authorization: Bearer`), `tenantId?`, `timeout` (30s), `retries` (3, exp backoff; 429+503 retry, 4xx never); `ApiError { status, message, code, traceId }`; runs API (`launch`/`launchSwarm`/`get`/`list`/`cancel`/`resume`/`stream` AsyncIterable/`waitForCompletion`); swarms/models/keys APIs; types from engine OpenAPI via `openapi-typescript`; JSDoc on every method; `msw` tests (`runs`/`stream`/`auth`/`errors`); dual CJS/ESM (`dist/cjs` + `dist/esm`, `package.json` `exports`); GitHub Action publishes to npm on `v*` tag. Fix the `KOrchestratorClient` README typo. Document the Python/TS parity matrix.
**Public surface:** `korchestrator.remote` (Python) + `@kendralabs/korchestrator-sdk` (TS).
**Validation:** Every documented method exists + tested (respx / `msw`); parity matrix complete; streaming example consumes SSE; TS works in Node **and** browser; CJS+ESM both resolve.
**Completion:** Thin client folded in, gaps closed, TS SDK shipped per E9 acceptance, docs match code.

### PHASE 10 — Testing, Benchmarks & Quality Gates
**Objective:** Comprehensive, enforced coverage against the final shape.
**Build:** unit (every module), integration (runtime swap, routing, tools, MCP, governance), e2e (full swarm local + Temporal), regression (behavior-parity vs engine), performance (`benchmarks/`: superstep parallelism ~1× not N×, startup, memory), smoke (import + one-liner). Enforce coverage floor; ratchet it. Temporal replay test + live-mode smoke against a stub gateway.
**Validation:** CI full matrix green; benchmarks baseline; parity confirms no behavior change.
**Completion:** All test types present + green; coverage floor enforced; benchmarks recorded.

### PHASE 11 — Documentation, Examples & DX
**Objective:** Ship docs as part of the product.
**Build:** Add an SDK section to the `website/` Docusaurus site: Installation, Quick Start (§8 one-liner), Tutorials (swarm, custom agent, custom tool, MCP, custom router, HITL, streaming), auto-generated API Reference, Architecture Guide (ARI ports, BSP, FractalFlow, durability, context graph), Migration Guide (from raw REST / in-repo extension → SDK), FAQ, Troubleshooting. Every `examples/` script runs unmodified.
**Validation:** Docs build in CI; every example green; a new dev goes install→first-run from the Quick Start alone.
**Completion:** Full doc set published; examples executable; migration guide present.

### PHASE 12 — CI/CD, Packaging, Versioning & Publishing
**Objective:** Automated, reproducible GitHub Actions release.
**Build:** CI stages — lint, format, type-check, test+coverage, security scan (bandit/pip-audit/gitleaks), build (wheel+sdist / CJS+ESM), version-validate (single source), docs-build, publish on `v*` tag (Python → registry/PyPI; TS → npm). SBOM + signed artifacts. `CHANGELOG.md` discipline; release notes; SemVer + deprecation policy.
**Validation:** A tagged release builds, tests, scans, versions, publishes, updates docs automatically; installing the published artifact reproduces the examples.
**Completion:** One-tag release; artifacts signed; versioning enforced; publishing automated.

### PHASE 13 — Backend Re-platform on the SDK — ⚠️ FUTURE / OUT OF SCOPE ⚠️
> **Do NOT execute during SDK creation.** This phase modifies `backend/`, which §0 forbids for this effort. It is planned as a **separate, approval-gated** initiative after the SDK ships.
**Objective (future):** Make the FastAPI backend a thin consumer of the SDK (imports `korchestrator`; adds only transport/auth/tenancy; the SDK never imports the service), proving the SDK-first architecture.
**Completion (future):** Backend is a thin adapter; the SDK is the single source of truth for engine logic; parity tests pass.

---

## 13. Remote API & Concepts Reference (for the Phase-9 client)

The `korchestrator.remote` client and the TS SDK must honor the live engine contract from `sdk/SDK_REFERENCE.md`:

**13.1 Concepts** — `run_id` (UUID, stable), `objective` (NL goal, ≥10 chars), `swarm` (directed agent graph), `superstep` (one parallel round), `agent`, `message` (`type` ∈ thought/tool/answer/handoff), `final_answer` (concatenated `answer` messages), `governance_paused`, `trust_score` (0.0–1.0, persists), `mock_mode`, `task_queue`.

**13.2 Auth** — `X-API-Key: sk-...` (per-tenant, shown once). Scopes: `korchestrator:read` (GET), `korchestrator:write` (POST run/resume/cancel), `korchestrator:admin` (keys). Errors: 401 (bad key), 403 (scope), 402 (quota). *(epic-9 alternative: `Authorization: Bearer` with API key or KIAM JWT — reconcile to the live engine and document.)*

**13.3 Endpoints** — `POST /v1/run/auto` (plan), `POST /v1/run/swarm` (explicit graph), `POST /v1/run` (raw AgentState), `GET /v1/run/{id}`, `GET /v1/run/{id}/stream` (SSE), `POST /v1/run/{id}/{resume|cancel|edit-resume}`, `GET /v1/runs`, `GET /v1/runs/{id}/summary`, `GET /v1/me[/quota|/runs]`, `POST|GET /v1/keys`, `DELETE /v1/keys/{id}`, `GET /v1/tools`, `POST /v1/tools/register`, `GET /v1/models`, `GET /v1/swarm-templates`.

**13.4 Lifecycle & status** — `started → running → (governance_paused → resume/cancel/edit-resume) → completed|failed|cancelled|timed_out`. Normalize numeric Temporal statuses (`1→running, 2→completed, 3→failed, 4→cancelled, 6→timed_out`). Webhook: single POST on terminal state (`run_id, status, superstep, completed_at, final_answer, message_count`), 10s timeout, no retry — handle idempotently.

**13.5 Engine env vars the client/Settings must recognize** — `MOCK_LLM`, `KENDRA_AI_GATEWAY_URL`/`LLM_GATEWAY_URL`, `KENDRA_GATEWAY_API_KEY`, `GOVERNANCE_TRUST_THRESHOLD`, `PERSISTENCE_BACKEND` (`kcg`/`none`), `ROUTING_STRATEGY` (`explicit`/`semantic`/`algorithmic`/`composite`), `AGENT_MODEL_MAP`, `KORCH_ENGINE_*` (address/namespace/queue/api-key), embedding/ModelCard vars.

---

## 14. Traceability & Production-Readiness Checklist

| Phase | Delivers | Key public surface |
|---|---|---|
| P0 Foundations | Self-contained scaffold, naming/version/license, CI + isolation gate, release workflow | `__version__` |
| P1 Contracts | ARI ports + protocols + façade signatures + exceptions | `interfaces/`, `KorchError`, `Korch`/`Swarm`/`Agent` |
| P2 Kernel | Framework-free Pregel + state + reducers (pydantic only) | `korchestrator.core`, `korchestrator.models` |
| P3 Runtime | Local + Temporal behind `IDurableRuntime` | runtime selection |
| P4 Cognitive | DSPy agents, compiled signatures, taxonomy, gateway providers | `Agent`, `WorkerAgent`, `ArchitectAgent`, `IModelGateway` |
| P5 Routing | v2.1 strategies behind `BaseRouter` | `get_router`, `BaseRouter` |
| P6 Integration | AUB, MCP, A2A, streaming, context compiler/MVC, middleware | `AUBConnector`, MCP client, `register_*`, `on(...)` |
| P7 Governance | Trust/HITL/policy, Shield/PII, Context Graph | HITL controls, `ContextGraphClient` |
| P8 Cross-cutting | Config, logging, telemetry, errors, serde, validation | `Settings`, exceptions, `to/from_json` |
| P9 Clients | Remote client folded in; TS SDK (E9) | `korchestrator.remote`, `@kendralabs/korchestrator-sdk` |
| P10 Testing | Full test matrix + benchmarks | — |
| P11 Docs | SDK docs + examples | — |
| P12 Release | GitHub Actions publish on tag | published artifact |
| P13 Re-platform | *(future, out of scope)* backend consumes SDK | thin `backend/api` |

**Final gate (all required):** §3 checklist satisfied; SDK is self-contained (isolation gate green); the §8 one-liner runs zero-infra; durable mode preserves crash-recovery/HITL/determinism; every §2.5 functionality reachable; docs/examples/tests/CI-CD/versioning/OSS files complete; package publishes on tag.

---

## 15. Standard Validation Commands

```bash
# Quality (package-scoped only)
ruff check packages/korchestrator
mypy --strict packages/korchestrator/src/korchestrator
pytest packages/korchestrator/tests --cov=korchestrator --cov-report=term-missing

# Isolation gate — MUST return nothing
grep -RnE "from (backend|apps|services)\.|import (backend|apps|services)\." packages/korchestrator/src && echo "ISOLATION VIOLATION" || echo "OK"

# Zero-infra smoke (only pydantic + base install)
python -c "from korchestrator import Korch; print(Korch().run('Summarize durable agent execution').final_answer)"

# Durable path (extra)
pip install -e 'packages/korchestrator[temporal]' && pytest packages/korchestrator/tests/e2e -k temporal

# Build & publish dry-run
python -m build packages/korchestrator
```

---

## 16. Final Notes for the Executing Agent

- **Build only the SDK package** under `packages/korchestrator/` (+ `packages/korchestrator-client-ts/` for the TS client). **Do not modify `backend/`, `frontend/`, `apps/`, `services/`, or `website/`.** Backend re-platform (Phase 13) is a future, separate effort.
- **Keep the package self-contained** — no imports from any in-repo module; its own `pyproject.toml`; publishable via GitHub Actions on a version tag.
- **Be dynamic** — runtime, gateway, router, and persistence are config-selected behind interfaces; nothing hardcoded.
- Execute phases **in order**; the contract (Phase 1) is frozen thereafter without an ADR.
- Keep `core` framework-free; heavy capabilities as optional extras; never leak an internal exception; never break the public API without a major bump + migration guide.
- **Don't over-engineer.** Package the functionality the engine already has (§2.5), simply. The SDK is a product for developers — architecture, stability, docs, tests, versioning, and DX matter as much as the engine underneath.
