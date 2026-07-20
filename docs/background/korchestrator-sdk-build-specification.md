<!-- Copyright (c) 2026 Kendra Laboratories Limited. All rights reserved. -->

# Korchestrator SDK — Developer Guide & Build Specification

> **⚠️ Superseded as the working specification.** This document is a **source input**. The
> authoritative, maintained specification set now lives in [`docs/specs/`](../specs/README.md)
> (00–11), with decisions recorded in [`docs/adr/`](../adr/README.md). Where the two disagree,
> `docs/specs/` wins.
>
> Known differences, all deliberate and ADR-backed:
> - **TypeScript client** — §7.1 and §12 Phase 9 here treat it as in scope. It is **deferred**:
>   specified for parity, not built in Phases 0–12 ([ADR 0008](../adr/0008-typescript-client-deferred.md)).
>   There is no `clients/typescript/` directory and no npm job in CI.
> - **License** — settled as Apache-2.0 ([ADR 0003](../adr/0003-license-apache-2-0.md)).
> - **Remote auth** — settled as `Authorization: Bearer` ([ADR 0005](../adr/0005-remote-auth-bearer-token.md)).
> - **Engineering log path** — `.claude/memory/ENGINEERING_LOG.md`.
>
> Keep this file for provenance. Do not build from it directly.

**Document type:** Authoritative developer guide and build specification for the standalone SDK repository. This document is self-sufficient — it is the single ground truth for what the SDK is, how it is built, versioned, released, and deployed.
**Repository:** `korch-sdk` (branches: `main` = released, `develop` = integration).
**Package:** Python `korchestrator` (optional TypeScript twin `@kendralabs/korchestrator-sdk`).
**Status:** Active build plan — Phases 0–12 are in scope. Phase 13 (external backend adapter) is **future / out of scope / approval-gated**.
**Audience:** SDK maintainers, contributors, integrators, and AI agents building in this repository.

---

## 0. Golden Rules (read first — these override everything)

1. **You build ONE thing: the installable Korchestrator SDK in this repository.** The repository *is* the SDK product — not a frontend, not a backend, not an application.
2. **Do not add or require a frontend or backend here.** Any service, dashboard, or hosted API is external to this repository and is maintained elsewhere. Backend integration is a separate future effort (Phase 13) and must never become a build, test, or release dependency of the SDK.
3. **The SDK must be self-contained.** It must not import from `backend.*`, `frontend`, `apps.*`, `services.*`, or any external application package. Its only runtime dependencies are declared in this repository's own `pyproject.toml` (a tiny core plus optional extras). This is what lets it build, version, and publish independently.
4. **Be dynamic, not hardcoded.** Everything configurable is config-driven and runtime-swappable (providers, runtime, router, persistence) behind interfaces. No hardcoded URLs, keys, models, or paths.
5. **Do not over-engineer.** Prefer the simplest correct design. Add only the abstraction the current requirement needs. Build the capability surface defined in §2.5 — do not invent new product surface.
6. **Determinism and stability are features.** The execution kernel must behave identically across runs and replays, and the public API must stay backward compatible within a major version (§10.7).

---

## 1. Purpose & How to Use This Document

This guide defines **how to build and how to use the Korchestrator SDK** — a production-grade, installable Python (and TypeScript) library that packages the Korchestrator durable multi-agent orchestration kernel as a reusable framework. Developers integrate through **code**; they do not run a service or hand-roll HTTP to get value.

It has two parts:

- **§2–§11 — Standards & context.** What Korchestrator is, what makes it different, the repository boundary, target structure, public API, cross-cutting standards, and release/versioning/deployment standards. These govern every phase.
- **§12 — Build phases (0–13).** The ordered implementation plan. Each phase: Objective · Build · Public surface · Validation · Completion criteria.

**How to read it:** read §2–§11 once; then execute §12 phases **strictly in order**. Use §14 as the master checklist and §15 as the standard command set.

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
| **L1** | **Runtime Kernel** | Execution loop, scheduling, synchronization (Pregel supersteps), communication, computation. Local in-process by default; Temporal for durability. | `core/`, `runtime/` |
| **L2** | **Cognitive Reasoning** | Planner, LLM routing, reasoning, task decomposition, validation — the "AI thinking layer." | `agents/`, `routing/` |
| **L3** | **Context Management** | Context Compiler, memory, state, event sourcing, Context Graph — enterprise memory. Includes **Minimum Viable Context (MVC)** extraction. | `persistence/`, `context/`, `models/state.py` |
| **L4** | **Interface & Tool Integration** | APIs, MCP, applications, enterprise systems, search, databases — everything external connects here. | `tools/` (AUB), `mcp/` |
| **L5** | **Governance & Security** | RBAC, authn/authz, audit logs, encryption, policy engine, PII/Shield, HITL. | `governance/`, `security/` |

**Runtime execution loop (L1):** `Receive event → Reason → Schedule → Execute → Synchronize → Communicate → Repeat.`

### 2.5 Complete functionality catalogue (the coverage contract)

Every capability below must be reachable through the SDK's public surface by the end of the build. This table is the coverage contract — each row maps to an SDK module and a build phase.

| Category | Functionality | SDK module | Phase |
|---|---|---|---|
| **Execution** | Durable, distributed, parallel, recursive, event-driven execution; recovery; scheduling; synchronization barriers | `core/`, `runtime/` | P2, P3 |
| **Agent management** | Multi-agent coordination; meta-agents; planner agents; **Architect** agents; autonomous execution; per-agent model isolation | `agents/` | P4 |
| **Context** | Context Compiler; Context Graph (bitemporal); memory management; context layering; **Minimum Viable Context (MVC)**; event sourcing; context pruning/summarization | `context/`, `persistence/` | P6, P7 |
| **Reasoning** | Task decomposition; planning; validation; **LLM routing**; intent + difficulty classification (taxonomy); decision making; **compiled signatures** | `agents/`, `routing/`, `taxonomy/` | P4, P5 |
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

Orchestration capability that only exists inside a running service is reachable only two ways: operate the service and drive its HTTP API, or fork and edit that service's source. Neither is a developer product. This repository makes the kernel an **installable library** — importable, embeddable, testable offline, and versioned on its own cadence.

The SDK is a **standalone Python library** that works without being tied to any specific platform, model provider, or security engine, interacting with the outside world only through the **Agent Runtime Interface (ARI)** (§2.8).

Target architecture (SDK-first):

```
korchestrator   (THIS repository: the SDK/framework — kernel + ARI ports + agents
                 + routing + tools + governance. The product.)
      ▲ optionally consumed by
external service / backend   (HTTP, auth, tenancy adapter — a THIN consumer, maintained
                              in a different repository; never a dependency of this one)   ← Phase 13, NOT in scope
      ▲ optionally called by
korchestrator remote client  (thin HTTP client surface for driving a hosted engine)
```

The arrows point **one way**: the SDK never imports, requires, or is blocked by anything above it.

### 2.8 The ARI ports (the portability contract)

The SDK interacts with the outside world only through three abstract ports, each with a local default and a Kendra implementation:

| Port | Role | Local default | Kendra implementation |
|---|---|---|---|
| `IIdentityProvider` | Authenticate agents → DID | Local (unsecured) identity | KIAM / KACP |
| `IExecutionSandbox` | Isolated tool/code execution | Local subprocess | OpenSandbox |
| `IModelGateway` | Route reasoning to an LLM | Direct OpenAI/Anthropic / gateway | Kendra AI Gateway |

A developer can run the SDK with **just an OpenAI key and a local process**; as they scale they plug in KACP/OpenSandbox/gateway **without changing agent logic**.

### 2.9 Repository starting point (greenfield)

This is a **new repository**. There is no existing package, client, or docs site to migrate, and no backend in this repository to read from or wire into. Everything in §12 is built here from this specification.

Consequences to keep front of mind:

- **No parity fallback.** Correctness is defined by this document and by the tests written alongside each phase — not by diffing against another implementation. Where an existing Korchestrator engine is available externally, it may be consulted as a *behavioral reference*, but it is never imported, vendored, or required by CI.
- **Contracts are decided here, once.** Naming, version, license, extras matrix, auth scheme, and the remote contract are decided in Phase 0/Phase 1 and recorded as ADRs in `docs/adr/`. Later phases consume those decisions rather than re-litigating them.
- **The remote client is a Phase 9 deliverable, not an inheritance.** It is built to the contract in §13, as an optional extra, and stays independent of the local kernel.
- **The TypeScript client is optional.** When enabled, `clients/typescript/` publishes `@kendralabs/korchestrator-sdk` (Node 18+, minimal runtime dependencies) mirroring the remote surface only.

> **Naming (record as ADR in Phase 0).** Flagship framework = Python package **`korchestrator`**. The thin HTTP client surface ships as the `korchestrator.remote` submodule behind the `[remote]` extra (TS twin: `@kendralabs/korchestrator-sdk`). If the client is ever split into its own distribution, it becomes **`korchestrator-client`**, versioned and packaged separately.

### 2.10 Decisions to settle before coding (do not defer)

Settle each of these in Phase 0/1 and record the outcome as an ADR. Leaving them open is what produces drift later.

- **One authoritative version.** A single source of truth in `src/korchestrator/version.py`; package metadata, docs, TS manifest, changelog, and release tags all derive from it (§10.7). Start at `0.1.0`.
- **One remote auth scheme.** Either `Authorization: Bearer <api-key|KIAM JWT>` or `X-API-Key: sk-...` — pick one, document it in §13.2, and implement it identically in the Python and TypeScript clients.
- **One remote method vocabulary.** Either `launch`/`launchSwarm` or `run`/`run_swarm` across both clients. Do not ship one name in Python and another in TypeScript.
- **Client naming and casing.** The client class is `KorchestratorClient` everywhere — in code, README, docstrings, and docs. No `KOrchestratorClient`, no `Kendra OrchestratorClient`.
- **Python/TypeScript parity is explicit.** Every method exists in both clients or is documented as intentionally absent, in the parity matrix maintained from Phase 9.
- **License.** Apache-2.0 / MIT / BSD / Proprietary — decided in Phase 0, applied to `LICENSE` and package metadata before the first release.

---

## 3. Definition of "Production-Grade" (the whole-SDK Definition of Done)

An SDK lets developers integrate through code. Production-grade = **Easy to install · learn · document · extend · test · upgrade; Modular · Stable · Backward-compatible · Secure · Performant.** Every box below must be checked before release:

- [ ] Clean, modular architecture with a stable, curated public API
- [ ] Self-contained package (no application-repo imports); own `pyproject.toml`; independently publishable
- [ ] Semantic Versioning + documented compatibility/deprecation policy
- [ ] Full type hints; typed responses; `py.typed`; `mypy --strict` clean; IDE autocomplete
- [ ] Tests: unit, integration, e2e, regression, performance, smoke — with an enforced coverage floor
- [ ] CI/CD: lint, format, type-check, security scan, build, version-validate, docs-build, publish (GitHub Actions release)
- [ ] Docs: install, quickstart, tutorials, API reference, architecture, examples, migration, FAQ, troubleshooting, versioning, release, deployment
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

- **`core` is framework-free.** The kernel imports only `interfaces/`, `models/`, stdlib, and `pydantic`. Never FastAPI/HTTP/Temporal/DSPy. This is the constraint that keeps the SDK embeddable and fast to import.
- **One implementation per concern.** Never a second router, PII redactor, error base, or config source. Variation = one interface + strategy.
- **Determinism inside workflows.** No wall-clock/`random` in workflow-path code; use the runtime's clock; preserve Temporal sandbox constraints so replay is exact.
- **Test-defined behavior.** Each phase lands its behavior together with the tests that define it. A capability with no test is not delivered.

---

## 5. Repository Isolation & Scope Rules (hard boundaries)

These make the golden rules (§0) enforceable:

1. **The SDK imports nothing from an application repository.** No `from backend...`, `from apps...`, `from services...`, and no dependency on an application package. If behavior is needed that exists elsewhere, implement the smallest required contract *here*. CI enforces this with an import-isolation gate (§15).
2. **Own dependency manifest.** This repository's `pyproject.toml` declares the SDK's dependencies: a tiny core (`pydantic` only) plus **optional extras** (§10.6). It never inherits another project's manifest.
3. **Only SDK concerns live here.** Source, tests, examples, docs, CI, and release configuration belong to this repository. Do not add frontend or backend application code, deployment manifests for a hosted service, or infrastructure-as-code for someone else's platform.
4. **Dynamic, not hardcoded.** Runtime (local/Temporal), model gateway, router strategy, and persistence backend are all selected by config at runtime behind interfaces. No hardcoded endpoints, keys, models, or file paths anywhere in the package.
5. **Independently buildable, releasable, and deployable.** Self-contained with its own manifest and CI, the SDK builds to a wheel/sdist (and a TypeScript package where enabled) and publishes on a version tag via GitHub Actions. No other repository needs to build, deploy, or even exist first.

---

## 6. Engineering, Git & Commit Discipline

**Branching**

- `main` — released state only; every commit on it corresponds to a tagged release.
- `develop` — integration branch; phases merge here.
- Work happens on short-lived branches off `develop`: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`, `security/` plus a concise slug (e.g. `feat/p2-pregel-kernel`).
- **Never commit directly to `main` or `develop`.** Open a PR into `develop`; release PRs go `develop → main`.

**Commits**

- Commit **phase-wise or task-wise** — not one giant commit. Prefer one commit per coherent unit.
- **Conventional-commit** messages, professional and descriptive, referencing the phase. Examples:
  - `feat(sdk): scaffold korchestrator package with pydantic-only core [P0]`
  - `feat(core): implement framework-free Pregel kernel + reducers [P2]`
  - `feat(routing): add router strategies behind BaseRouter [P5]`
  - `test(core): cover superstep activation and halting rules [P2]`
- Each commit leaves the package **green** (build + tests pass).

**Definition of Done per phase** — a phase is complete only when: all its tasks are done; all tests pass and behavior is covered by tests; `ruff` + `mypy --strict` are clean on the package; the phase's Validation and Completion Criteria pass; work is committed with professional messages and merged via PR; the §14 checklist row is checked.

**ADR discipline** — record non-obvious decisions (naming, version, license, extras matrix, runtime split, remote contract, external backend boundary) as short ADRs in `docs/adr/` with context, decision, alternatives, consequences, and rollback. Any structural deviation from this spec needs an ADR + reviewer sign-off.

**Anti-patterns to reject in review (hard "no")** — a second copy of a concern (router/PII/errors/config); a framework import inside `core/`; a feature smeared across horizontal `models/`/`utils/` instead of one module; a God file (>~500 lines) or God function (>~50 lines); a sideways import between sibling SDK modules or a cycle; a raw `os.getenv`/hardcoded endpoint outside `config/`; **any import from `backend`/`apps`/`services`.**

---

## 7. Target SDK Package Structure (professional, publish-ready)

The SDK is the primary and only product of this repository: a `src/`-layout Python package with a public API, a framework-free kernel, optional integrations, tests, documentation, and release tooling.

### 7.1 Layout

```text
korch-sdk/                              THIS repository — self-contained, independently publishable
├── src/                                Python source root (src-layout: imports resolve from the install, not the CWD)
│   └── korchestrator/
│       ├── __init__.py                 PUBLIC API — the only surface users import (explicit __all__)
│       ├── py.typed                    ships type information
│       ├── version.py                  single source of truth for the version
│       ├── config/                     typed Settings (arg > env > file > default); the ONLY place env is read
│       ├── interfaces/                 ARI ports + protocols (the contracts)
│       │   ├── identity.py             IIdentityProvider
│       │   ├── sandbox.py              IExecutionSandbox
│       │   ├── model_gateway.py        IModelGateway
│       │   ├── runtime.py              IDurableRuntime (Temporal/local behind one port)
│       │   ├── repository.py           GraphRepository / TenantStore protocols
│       │   ├── router.py               BaseRouter protocol
│       │   └── connector.py            AUBConnector / tool protocols
│       ├── core/                       FRAMEWORK-FREE kernel (Pregel) — pydantic only
│       │   ├── pregel.py               PregelRunner (run_superstep + synchronize)
│       │   ├── graph.py                AgentGraph, Node, Edge, topology builder
│       │   └── reducers.py             reducer_append / reducer_merge_dict / reducer_last_value
│       ├── models/                     Pydantic domain models (DTOs)
│       │   ├── state.py                AgentState, StateUpdate, Message, Performative, RunStatus
│       │   ├── agent.py                AgentConfig, AgentPersona, AgentDescriptor
│       │   ├── plan.py                 ExecutionPlan, TaskDecomposition (compiled-signature plan)
│       │   └── routing.py              ModelCard, TaskSemantics, RoutingResult, RoutingContext
│       ├── agents/                     L2 Cognitive — DSPy intelligence (extra: [dspy])
│       │   ├── worker.py               WorkerAgent (TypedPredictor + ReAct loop)
│       │   ├── architect.py            ArchitectAgent (meta-agent: intent + plan)
│       │   ├── signatures.py           DSPy Signatures (compiled signatures)
│       │   └── base.py                 Agent base + think(state)->StateUpdate contract
│       ├── taxonomy/                   intent/difficulty classification + agent descriptors
│       ├── routing/                    L2 model routing (strategies behind BaseRouter)
│       ├── runtime/                    L1 durability adapters implementing IDurableRuntime
│       │   ├── local_runtime.py        in-process (no Temporal) — dev/embed default
│       │   └── temporal_runtime.py     Temporal adapter (extra: [temporal])
│       ├── context/                    L3 Context Compiler + MVC + pruning/summarization
│       ├── persistence/                L3 Context Graph client + backends (in-memory/mock/neo4j/pg)
│       ├── providers/                  default ARI implementations
│       │   ├── identity_local.py · sandbox_local.py · gateway_openai.py · mock_lm.py
│       ├── tools/                      L4 Agent Utility Bridge (AUB)
│       │   ├── bridge.py · registry.py · connectors/ (base + search + file_system)
│       ├── mcp/                        L4 MCP client + tool registry
│       ├── a2a/                        A2A typed message passing / handoff transformer
│       ├── governance/                 L5 trust scoring, HITL, policy
│       ├── security/                   L5 Shield / PII redaction, secret handling, sanitization
│       ├── events/                     streaming / AG-UI publisher (transport-agnostic)
│       ├── clients/                    remote client (korchestrator.remote) (extra: [remote])
│       ├── services/                   high-level façade (Korch / Swarm / Agent builders)
│       ├── serializers/                object<->JSON/dict/YAML (version-tagged)
│       ├── validators/                 input/config/response/runtime validation
│       ├── telemetry/                  optional OTel metrics + tracing (extra: [otel])
│       ├── logging/                    namespaced, disable-able logging (no root-logger mutation)
│       ├── exceptions/                 custom exception hierarchy
│       ├── types/                      shared typing/Protocols/TypedDicts
│       └── constants/                  defaults, enums, error codes
├── clients/typescript/                 optional TS twin — @kendralabs/korchestrator-sdk (remote surface only)
├── tests/                              unit / integration / e2e / regression / smoke
├── examples/                           executable examples (local + remote)
├── docs/                               documentation source + docs/adr/
├── scripts/                            build/release/validation scripts
├── benchmarks/                         performance suites
├── .github/workflows/                  ci.yml · release.yml (publish on v* tag) · docs.yml
├── pyproject.toml                      authoritative Python manifest — pydantic core + optional extras
├── README.md · LICENSE · CHANGELOG.md · CONTRIBUTING.md
├── CODE_OF_CONDUCT.md · SECURITY.md · MANIFEST.in
├── .gitignore · .editorconfig · .pre-commit-config.yaml
└── mkdocs.yml                          documentation site build configuration
```

**TypeScript client.** `clients/typescript/` publishes `@kendralabs/korchestrator-sdk`, mirroring the **remote surface only** (never the local kernel), with a dual CJS/ESM build and its own release job (§10.8, Phase 9). It lives in this repository but is versioned and published as a separate package.

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
- **No import from any application repository** (§5).

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

Tiers 1–3 run entirely inside the installed package. Tier 4 is the **only** tier that talks to an external service, it is optional (`[remote]` extra), and nothing in Tiers 1–3 depends on it.

---

## 9. Cross-Cutting Standards (apply to every phase)

- **9.1 Configuration** — precedence **arg > env > `.env` > default**; one typed `Settings` (`pydantic-settings`) is the only place env is read; support every variable in §13.5; zero-config local default = MockLM.
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

## 10. Release, Versioning & Deployment Standards

- **10.1 Testing** — unit, integration, e2e, regression, performance, smoke; coverage floor enforced (baseline then ratchet). MockLM makes the full agent path runnable in CI with no network and no API keys.
- **10.2 Documentation** — install, quickstart, tutorials, API reference (autogenerated), architecture, examples, migration, FAQ, troubleshooting, versioning, release, and deployment. Documentation is **owned, built, and published from this repository** (MkDocs → GitHub Pages, or the configured docs host). No external website is required.
- **10.3 Examples** — executable-without-modification for: local one-liner, typed swarm, custom agent, custom tool/connector, custom router, MCP server, remote client, HITL pause/resume, streaming.
- **10.4 CI/CD** — lint (ruff), format, type-check (mypy), test+coverage, security scan (bandit/pip-audit/gitleaks), import-isolation gate, build, version-validate, clean-environment install smoke test, docs-build, publish, docs deploy.
- **10.5 Code quality** — Ruff, ruff-format, MyPy, Pytest, Coverage, pre-commit.
- **10.6 Dependency management** — core depends only on `pydantic`. Extras: `[dspy]` (agents), `[temporal]` (durable runtime), `[routing]` (semantic/embedding routing), `[mcp]` (MCP tools), `[remote]` (HTTP client), `[otel]` (telemetry), `[all]`. Pin appropriately; minimize transitive deps; every dependency must be necessary, maintained, licensed, and removable.

### 10.7 Versioning & compatibility

- **SemVer (`MAJOR.MINOR.PATCH`)** for the Python SDK and, independently, for the TypeScript client.
- **One authoritative version** lives in `src/korchestrator/version.py`. `pyproject.toml`, `__version__`, docs, the TS package manifest, and the release tag all derive from it. CI fails if any of them disagree.
- **Start at `0.1.0`.** While `0.x`, a **minor** bump may contain breaking changes — this must be stated plainly in the README and CHANGELOG. From `1.0.0` onward the full compatibility policy below applies without exception.
- **Never break the public API (§8) without a major bump** plus a migration guide.
- **Deprecation policy** — a deprecated public name emits a `DeprecationWarning`, stays for at least one minor release, and documents its replacement, migration path, and removal version before it is removed.
- **Compatibility surface** — the public API is `korchestrator.__all__`, the ARI ports, the documented models, and the remote contract in §13. Anything else is internal and may change in any release.
- **`CHANGELOG.md`** follows Keep a Changelog with ISO dates; every user-visible change lands with its changelog entry in the same PR.

### 10.8 Release process

1. Open a release PR into `main` with the version bump in `version.py` and a reviewed `CHANGELOG.md` entry.
2. Full CI must be green: lint, types, tests + coverage floor, security scan, isolation gate, build, version-validate, docs-build.
3. Merge, then create a signed **`vX.Y.Z`** tag on `main`.
4. The tag triggers `release.yml`: build wheel + sdist (and CJS+ESM for the TS client), smoke-test the built artifact in a clean environment, then publish (Python → configured registry/PyPI; TypeScript → npm).
5. Publish GitHub release notes stating supported Python/Node versions, dependency changes, public API changes, migrations, and known limitations.
6. Deploy the documentation for the released version.

Releases are **immutable**: a published version is never overwritten. A bad release is superseded by a new patch version, and yanked at the registry if it is harmful.

### 10.9 Deployment & consumption

The SDK is **deployed by publishing package artifacts**, not by running a service. There is no server, container, or environment to operate in this repository.

- **Consumers install it**: `pip install korchestrator` (plus the extras they need), pinned to a compatible range. TypeScript consumers `npm install @kendralabs/korchestrator-sdk`.
- **What "deployment" means here**: (a) immutable package artifacts on the configured registry, (b) the documentation site published from `docs/`, (c) the git tag and release notes.
- **Infrastructure the SDK may *connect to*** (Temporal, Postgres/Neo4j, a model gateway, MCP servers) is provisioned and operated by the consumer, selected by config at runtime (§5.4), and always optional — the default install runs with none of it.
- **A hosted backend is out of scope.** If a service later depends on the published SDK, its hosting, authentication, tenancy, scaling, and infrastructure live in that service's own repository (Phase 13). Nothing about its deployment belongs here.

### 10.10 Artifact integrity

Ship `py.typed` in the wheel; generate an SBOM per release; sign artifacts where the registry supports it; retain build provenance and checksums; verify a clean-environment install of the built artifact (not the source tree) before marking a release complete.

### 10.11 OSS-readiness

LICENSE (decision per §2.10), README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY (including the vulnerability-reporting channel and supported-version window), issue/PR templates, and GitHub Actions.

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

> Each phase: **Objective · Build · Public surface · Validation · Completion criteria.** Execute in order. Every phase is confined to this repository and lands with the tests that define its behavior.

### PHASE 0 — Foundations, Scope Freeze & Scaffolding
**Objective:** Stand up the self-contained repository skeleton; settle naming/version/license/extras; put the quality + isolation net in place.
**Build:** (1) Create the §7.1 layout (`src/korchestrator/` with stub modules + `__init__.py`), the **authoritative** `pyproject.toml` (name `korchestrator`, `hatchling`, `requires-python >=3.10`, core dep `pydantic` only, extras per §10.6), `version.py` (`0.1.0`), and `py.typed`. (2) OSS-readiness files + `.pre-commit-config.yaml`. (3) ADRs for every §2.10 decision: naming, single authoritative version, license, extras matrix, remote contract, external-backend boundary. (4) CI (`ci.yml`): ruff, `mypy --strict`, pytest + coverage floor, build check, version-validate, and the **import-isolation gate**. (5) `release.yml` skeleton (publish on `v*` tag) and `docs.yml` (build + deploy documentation).
**Public surface:** `__version__`.
**Validation:** `pip install -e .`; `import korchestrator`; CI green including the isolation gate and version-validate.
**Completion:** Package builds standalone; all §2.10 decisions ADR'd; CI + isolation gate active; version single-sourced.

### PHASE 1 — Public API & Interface Contracts (ARI + Protocols)
**Objective:** Design the public surface and contracts first (API-first).
**Build:** (1) ARI ports in `interfaces/`: `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway` (abc/Protocol + documented contract + declared default). (2) Supporting protocols: `IDurableRuntime`, `GraphRepository`/`TenantStore`, `BaseRouter` (`async select_model(task, models) -> RoutingResult`), `AUBConnector` (`async execute(tool, args, invocation) -> ToolResult`). (3) Façade signatures (`Korch`, `Swarm`, `Agent`) + `__init__.__all__` — types only; §8 examples as doctests (xfail until implemented). (4) Freeze the exception hierarchy (§9.3).
**Public surface:** interfaces + exceptions + façade type signatures.
**Validation:** `mypy --strict` on interfaces; façade imports; doctests collected.
**Completion:** Every port/protocol defined + documented; façade API frozen; exception hierarchy final. (Anti-rework crux — no contract change after this without an ADR.)

### PHASE 2 — Core Execution Kernel (Pregel, framework-free)
**Objective:** Build the deterministic BSP engine as the dependency-light heart (pydantic only).
**Build:** (1) `models/state.py` (`AgentState`, `StateUpdate`, `Message`, `Performative`, `RunStatus`), `core/reducers.py` (`reducer_append` / `reducer_merge_dict` / `reducer_last_value`), `core/pregel.py` (`PregelRunner.run_superstep` via `asyncio.gather` + `synchronize`), `core/graph.py` (`AgentGraph`, `Node`, `Edge`, topology builder). (2) The runner takes an injected `IModelGateway`/agent-callable (DIP) — it never constructs its own. (3) Activation rules: superstep 0 activates all nodes; later supersteps activate only nodes with inbox messages; halt on `max_supersteps` (default 10) or `halted=True`. (4) Reducers are associative and order-independent so the barrier merge is deterministic.
**Public surface:** `korchestrator.core`, `korchestrator.models`.
**Validation:** Kernel test suite runs with **only `pydantic`** installed and covers: activation per superstep, each reducer, message routing along edges, both halting conditions, and identical results across repeated runs of the same graph + seed.
**Completion:** Kernel runs a superstep with only pydantic installed; determinism and halting are test-locked.

### PHASE 3 — Runtime Adapters (Local + Durable behind IDurableRuntime)
**Objective:** Run locally with no infra AND durably on Temporal — selected by config.
**Build:** (1) `runtime/local_runtime.py` — in-process `IDurableRuntime` driving the Pregel loop (no Temporal import). Default for embed/dev/CI. (2) `runtime/temporal_runtime.py` — Temporal workflow/activity adapter behind `IDurableRuntime`, preserving determinism (`workflow.now()`, `patched()` gates), retry policy, HITL signals (pause/resume up to 24h), and the activity boundary. `temporalio` is imported **only** here (extra `[temporal]`). (3) Config selects the runtime (`KORCH_RUNTIME=local|temporal`).
**Public surface:** `Korch(runtime=...)`/Settings; `IDurableRuntime` for custom runtimes.
**Validation:** The same swarm completes on both runtimes with an equivalent `RunResult`; the Temporal replay test passes; a forced mid-run crash resumes from the last superstep with no duplicated work.
**Completion:** Local runtime works zero-infra; Temporal preserves durability/HITL/determinism; runtime swappable by config alone.

### PHASE 4 — Cognitive Layer (Agents, Compiled Signatures, Taxonomy, Model Gateway)
**Objective:** Build the reasoning layer (L2) — meta-agents, workers, compiled signatures, intent taxonomy, model providers.
**Build:** (1) `agents/worker.py` (`WorkerAgent`: `TypedPredictor` + ReAct loop ≤3, per-agent `dspy.context`), `agents/architect.py` (`ArchitectAgent` meta-agent: intent + difficulty → `ExecutionPlan`), `agents/signatures.py` (compiled signatures), `agents/base.py` (`think(state)->StateUpdate`, `is_complete`). Extra `[dspy]`, lazy-imported. (2) `taxonomy/` — intent/difficulty classification + agent descriptors. (3) `providers/`: `gateway_openai.py` (default `IModelGateway`), `mock_lm.py` (deterministic MockLM), `identity_local.py`, `sandbox_local.py`; `get_lm(model_name)` factory.
**Public surface:** `Agent`, `WorkerAgent`, `ArchitectAgent`, `Signature` base, taxonomy classifier, `IModelGateway` + providers.
**Validation:** A custom agent (new signature + `think`) runs end-to-end under MockLM with no network; heterogeneous per-agent models are honored within one superstep; the base install (no `[dspy]`) still imports cleanly.
**Completion:** Agents run under MockLM offline; real models work via the gateway; adding an agent requires no core edit.

### PHASE 5 — Model Routing Subsystem
**Objective:** Per-agent model selection as strategies behind one `BaseRouter`, with the simplest path as the default.
**Build:** `routing/` with models (`ModelCard`, `TaskSemantics`, `RoutingResult`, `RoutingContext`), a `get_router()` factory, and strategies Explicit / Semantic / Algorithmic / Composite / UserFunction plus a documented fallback. Semantic/embedding routing and the ModelCard DB are opt-in (extra `[routing]`); **Explicit + one fallback is the default**. Config: `ROUTING_STRATEGY`, `AGENT_MODEL_MAP`, `ROUTING_WEIGHTS`, `ROUTING_PRIORITY_ORDER`, `EMBEDDING_PROVIDER`, `MODELCARD_*`. Cache router/embedding singletons.
**Public surface:** `get_router()`, `BaseRouter`, routing models.
**Validation:** Explicit mapping picks the named model; a custom `BaseRouter` plugs in via config without editing the package; cost influences algorithmic ranking; the embedding cache expires as configured.
**Completion:** Routing works on the default (no-embedding) install; advanced strategies load only with the `[routing]` extra.

### PHASE 6 — Integration & Observability (AUB, MCP, A2A, Streaming, Context Compiler)
**Objective:** Build L4 tool integration, A2A messaging, real-time streaming, and the L3 context compiler/MVC.
**Build:** (1) `tools/` AUB — `bridge.py` (`invoke_tool`, schema validation, timeout, rate limiting, OTel spans, Shield gate), `registry.py` (`ConnectorRegistry` + plugin loading), `connectors/` (base + search + file_system, MockSearch fallback). Emit `TOOL_ACCESS_DENIED`/`TOOL_NOT_FOUND` per §9.3. (2) `mcp/` — MCP client + hierarchical tool registry. (3) `a2a/` — typed directed messages / `HandoffTransformer` (reads `messages`, passes structured findings). (4) `context/` — Context Compiler + **Minimum Viable Context** extraction + pruning/summarization (off the hot loop, degrades gracefully). (5) `events/` — streaming / AG-UI publisher, transport-agnostic and SSE-capable (the SDK emits events; it does not serve HTTP). (6) Extension framework: `middleware`/`events` registration (pre/post-superstep, pre/post-tool, on-message, on-governance-pause).
**Public surface:** `AUBConnector`, `register_tool`/`register_connector`, MCP client, `register_middleware`, `on(event, handler)`, streaming subscriber, context compiler.
**Validation:** A custom connector is invokable by an agent; an MCP tool loads; a middleware/hook fires in the documented order; MVC measurably reduces context size; Shield denies an over-privileged call.
**Completion:** Adding a tool/MCP server/hook needs no core edit; streaming + context compilation work.

### PHASE 7 — Governance, Security & Context Graph (Zero-Trust)
**Objective:** Build L5 governance + the bitemporal Context Graph (L3).
**Build:** (1) `governance/` — trust scoring (`ControlTowerTelemetry`), `check_governance`/intervention → runtime pause signal, HITL resume/modify/cancel, per-agent `hitl_threshold` with a global `GOVERNANCE_TRUST_THRESHOLD` fallback, policy engine + audit log. (2) `security/` Shield — the single consolidated PII redactor (PAN + Luhn, IBAN, international phone, SSN, secrets), fail-closed for high-sensitivity flows. (3) `persistence/` — `ContextGraphClient` (bitemporal `DecisionNode`/`EventNode`, valid-time/transaction-time, confidence, provenance, event sourcing) behind `GraphRepository`; backends in-memory (default), mock, Neo4j/Postgres (extras). `PERSISTENCE_BACKEND=none` runs fully standalone.
**Public surface:** governance config on `Korch`/`Swarm`, HITL controls (`pause`/`resume`/`cancel`/`edit_resume`), `ContextGraphClient`, `GraphRepository`.
**Validation:** A run auto-pauses below threshold and resumes on signal; PII redaction covers every required format and fails closed; context-graph queries are tenant-scoped and support time-travel; a fully standalone run (no external graph store) completes.
**Completion:** Governance/HITL, Shield, and Context Graph are usable from the SDK; the default install needs no external services.

### PHASE 8 — Config, Telemetry, Logging, Errors, Serialization, Validation
**Objective:** Finalize the §9 cross-cutting foundations as first-class, tested modules.
**Build:** `config/` (one typed `Settings`, precedence arg > env > file > default, every §13.5 variable, zero-config MockLM default); `logging/` (namespaced, disable-able); `telemetry/` (optional OTel, zero-cost when off, extra `[otel]`); `exceptions/` (finalized, wrapping all internal errors); `serializers/` (version-tagged round-trip); `validators/`; `security/` secret handling; `constants/` (error codes/defaults).
**Public surface:** `Settings`/`configure()`, `enable_logging()`, exceptions, `to_json`/`from_json`.
**Validation:** env is read only inside `config/` (test-enforced); logging is fully disable-able; every internal exception surfaces as a `KorchError` subclass; serialization round-trips stay stable across a version bump.
**Completion:** All §9 standards implemented + tested; no raw internal exception escapes; config single-sourced.

### PHASE 9 — Client SDKs (remote HTTP + TypeScript parity)
**Objective:** Ship the optional remote client as `korchestrator.remote`, plus the first-class TypeScript twin.
**Build:** (1) Implement the Python thin client under `clients/`, re-exported as `korchestrator.remote.KorchestratorClient` (extra `[remote]`, `httpx`-based, async + sync). Honor the §13 contract exactly: the single chosen auth scheme and scopes, run lifecycle, status normalization, and webhook semantics. Surface: run/launch, swarm run, raw-`AgentState` submit, `get_run`, `wait`/`run_and_wait`, `list_runs`, `get_run_summary`, `me`/`my_quota`/`my_runs`, `resume`, `cancel`, `edit_resume`, SSE `stream`, `tools`, `models`, `swarm_templates`, and key management (`create_key`/`list_keys`/`revoke_key`) where the contract authorizes it. (2) The TypeScript SDK: `KorchestratorClient` with `baseUrl`, `apiKey?`/`accessToken?` (mutually exclusive), `tenantId?`, `timeout` (30s), `retries` (3, exponential backoff; retry 429 + 503, never 4xx); `ApiError { status, message, code, traceId }`; the runs API (`get`/`list`/`cancel`/`resume`/`stream` as AsyncIterable/`waitForCompletion`); swarms/models/keys APIs; generated API types; JSDoc on every method; `msw` tests; dual CJS/ESM (`dist/cjs` + `dist/esm` with `package.json` `exports`); npm publish on a `v*` tag. (3) Maintain the Python/TypeScript **parity matrix** in the docs.
**Public surface:** `korchestrator.remote` (Python) + `@kendralabs/korchestrator-sdk` (TypeScript).
**Validation:** Every documented method exists and is tested against a mocked transport (`respx` / `msw`); the parity matrix is complete with intentional gaps labeled; the streaming example consumes SSE; the TS client works in Node **and** browser; CJS + ESM both resolve.
**Completion:** Remote client shipped behind its extra, TS twin published, docs match code exactly, and the local kernel remains usable with neither installed.

### PHASE 10 — Testing, Benchmarks & Quality Gates
**Objective:** Comprehensive, enforced coverage against the final shape.
**Build:** unit (every module), integration (runtime swap, routing, tools, MCP, governance), e2e (full swarm on local + Temporal), regression (a locked test per fixed bug), performance (`benchmarks/`: superstep parallelism scales ~1× not N×, import/startup time, memory), smoke (import + one-liner on a clean install). Enforce the coverage floor and ratchet it. Include the Temporal replay test and a live-mode smoke against a stub gateway.
**Validation:** Full CI matrix green across supported Python versions; benchmarks recorded as a baseline; no test depends on network, wall-clock sleeps, or shared developer state.
**Completion:** All test types present + green; coverage floor enforced; benchmark baseline committed.

### PHASE 11 — Documentation, Examples & DX
**Objective:** Ship docs as part of the product.
**Build:** Repository-owned documentation site (`docs/` + `mkdocs.yml`): Installation, Quick Start (§8 one-liner), Tutorials (swarm, custom agent, custom tool, MCP, custom router, HITL, streaming), auto-generated API Reference, Architecture Guide (ARI ports, BSP, FractalFlow, durability, context graph), Migration Guide (from driving a hosted engine over raw REST → using the SDK), FAQ, Troubleshooting, and the Versioning / Release / Deployment pages derived from §10. Every `examples/` script runs unmodified on a clean install.
**Validation:** Docs build in CI with no broken links; every example runs green; a new developer gets from install to first successful run using the Quick Start alone.
**Completion:** Full doc set published; examples executable; migration and deployment guidance present.

### PHASE 12 — CI/CD, Packaging, Versioning & Publishing
**Objective:** Automated, reproducible, one-tag GitHub Actions release.
**Build:** CI stages — lint, format, type-check, test + coverage, security scan (bandit/pip-audit/gitleaks), import-isolation gate, build (wheel + sdist / CJS + ESM), version-validate (single source per §10.7), clean-environment install smoke test of the built artifact, docs-build. `release.yml` publishes only after all of these pass on a `vX.Y.Z` tag (Python → configured registry/PyPI; TypeScript → npm), then generates SBOM + checksums, signs artifacts where supported, publishes release notes, and deploys the documentation. Enforce `CHANGELOG.md`, SemVer, and the deprecation policy.
**Validation:** A tagged release builds, tests, scans, verifies the version everywhere, installs from the built artifact in a clean environment, publishes immutably, and deploys docs — with **no backend or frontend job anywhere in the pipeline**.
**Completion:** One-tag release works end to end; artifact integrity metadata available; versioning enforced; publishing and docs deployment automated.

### PHASE 13 — External Backend Adapter — ⚠️ FUTURE / OUT OF SCOPE ⚠️
> **Do NOT execute during SDK creation.** This phase belongs to a separate backend repository and is not a dependency of this one. It requires explicit approval and its own implementation plan after the SDK is released.
**Objective (future):** Let an external service (e.g. FastAPI) consume the **published** SDK as a thin adapter that adds only transport, authentication, and tenancy. The SDK must never import, require, or be versioned against that service.
**Completion (future):** The external backend is a thin adapter; the SDK remains the source of truth for orchestration behavior; cross-repository contract tests pass against a published SDK version.

---

## 13. Remote API & Concepts Reference (the Phase-9 contract)

This section is the **authoritative contract** for the remote client surface. It describes the API a hosted Korchestrator engine is expected to expose; the SDK's job is to speak it correctly. It creates no dependency on any particular service existing — Tiers 1–3 (§8) are unaffected if no engine is deployed.

**13.1 Concepts** — `run_id` (UUID, stable), `objective` (natural-language goal, ≥10 chars), `swarm` (directed agent graph), `superstep` (one parallel round), `agent`, `message` (`type` ∈ thought/tool/answer/handoff), `final_answer` (concatenated `answer` messages), `governance_paused`, `trust_score` (0.0–1.0, persists across supersteps), `mock_mode`, `task_queue`.

**13.2 Auth** — **one** scheme, chosen and ADR'd in Phase 0 (§2.10), implemented identically in both clients: either `Authorization: Bearer <api-key | KIAM JWT>` or `X-API-Key: sk-...` (per-tenant, shown once). Scopes: `korchestrator:read` (GET), `korchestrator:write` (POST run/resume/cancel), `korchestrator:admin` (key management). Errors: 401 (bad credentials), 403 (insufficient scope), 402 (quota exceeded). Credentials are never logged and never written to disk by the SDK.

**13.3 Endpoints** — `POST /v1/run/auto` (plan), `POST /v1/run/swarm` (explicit graph), `POST /v1/run` (raw AgentState), `GET /v1/run/{id}`, `GET /v1/run/{id}/stream` (SSE), `POST /v1/run/{id}/{resume|cancel|edit-resume}`, `GET /v1/runs`, `GET /v1/runs/{id}/summary`, `GET /v1/me[/quota|/runs]`, `POST|GET /v1/keys`, `DELETE /v1/keys/{id}`, `GET /v1/tools`, `POST /v1/tools/register`, `GET /v1/models`, `GET /v1/swarm-templates`.

**13.4 Lifecycle & status** — `started → running → (governance_paused → resume | cancel | edit-resume) → completed | failed | cancelled | timed_out`. Normalize numeric Temporal statuses (`1→running, 2→completed, 3→failed, 4→cancelled, 6→timed_out`) into the string form above. Webhook: a single POST on terminal state (`run_id, status, superstep, completed_at, final_answer, message_count`), 10s timeout, **no retry** — consumers must handle it idempotently.

**13.5 Environment variables `Settings` must recognize** — `MOCK_LLM`, `KENDRA_AI_GATEWAY_URL`/`LLM_GATEWAY_URL`, `KENDRA_GATEWAY_API_KEY`, `GOVERNANCE_TRUST_THRESHOLD`, `PERSISTENCE_BACKEND` (`kcg`/`none`), `ROUTING_STRATEGY` (`explicit`/`semantic`/`algorithmic`/`composite`), `AGENT_MODEL_MAP`, `KORCH_RUNTIME` (`local`/`temporal`), `KORCH_ENGINE_*` (address/namespace/queue/api-key), and the embedding/ModelCard variables from §12 Phase 5. All are read **only** inside `config/` (§9.1).

---

## 14. Traceability & Production-Readiness Checklist

| Phase | Delivers | Key public surface |
|---|---|---|
| P0 Foundations | Self-contained scaffold, naming/version/license ADRs, CI + isolation gate, release + docs workflows | `__version__` |
| P1 Contracts | ARI ports + protocols + façade signatures + exceptions | `interfaces/`, `KorchError`, `Korch`/`Swarm`/`Agent` |
| P2 Kernel | Framework-free Pregel + state + reducers (pydantic only) | `korchestrator.core`, `korchestrator.models` |
| P3 Runtime | Local + Temporal behind `IDurableRuntime` | runtime selection |
| P4 Cognitive | DSPy agents, compiled signatures, taxonomy, gateway providers | `Agent`, `WorkerAgent`, `ArchitectAgent`, `IModelGateway` |
| P5 Routing | Strategies behind `BaseRouter` | `get_router`, `BaseRouter` |
| P6 Integration | AUB, MCP, A2A, streaming, context compiler/MVC, middleware | `AUBConnector`, MCP client, `register_*`, `on(...)` |
| P7 Governance | Trust/HITL/policy, Shield/PII, Context Graph | HITL controls, `ContextGraphClient` |
| P8 Cross-cutting | Config, logging, telemetry, errors, serde, validation | `Settings`, exceptions, `to/from_json` |
| P9 Clients | Remote client + TypeScript twin | `korchestrator.remote`, `@kendralabs/korchestrator-sdk` |
| P10 Testing | Full test matrix + benchmarks | — |
| P11 Docs | Documentation site + examples | — |
| P12 Release | GitHub Actions publish + docs deploy on tag | published artifacts |
| P13 External adapter | *(future, out of scope)* external service consumes the published SDK | thin service adapter |

**Final gate (all required):** §3 checklist satisfied; the SDK is self-contained (isolation gate green); the §8 one-liner runs zero-infra on a clean install; durable mode preserves crash-recovery/HITL/determinism; every §2.5 capability is reachable from the public API; docs, examples, tests, CI/CD, versioning, deployment guidance, and OSS files are complete; the package publishes on a tag.

---

## 15. Standard Validation Commands

```bash
# Quality
ruff check src/korchestrator tests
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing

# Isolation gate — MUST print OK
grep -RnE "from (backend|apps|services)\.|import (backend|apps|services)\." src/korchestrator \
  && echo "ISOLATION VIOLATION" || echo "OK"

# Zero-infra smoke (base install: pydantic only)
python -c "from korchestrator import Korch; print(Korch().run('Summarize durable agent execution').final_answer)"

# Durable path (extra)
pip install -e '.[temporal]' && pytest tests/e2e -k temporal

# Version must agree everywhere (version.py, package metadata, tag)
python -c "import korchestrator; print(korchestrator.__version__)"

# Build, then verify the ARTIFACT (not the source tree) installs clean
python -m build
pip install --force-reinstall dist/*.whl && python -c "import korchestrator; print(korchestrator.__version__)"

# Docs
mkdocs build --strict
```

---

## 16. Final Notes for the Executing Agent

- **Build only the SDK** in this repository (`src/korchestrator/`, plus `clients/typescript/` when the TS client is enabled). **Do not add a backend or a frontend.** The external backend adapter (Phase 13) is a future, separate effort in a different repository.
- **Keep the SDK self-contained** — no imports from application repositories; this repository owns its `pyproject.toml`, tests, docs, CI, versioning, release, and deployment configuration; it publishes via GitHub Actions on a version tag.
- **Be dynamic** — runtime, gateway, router, and persistence are config-selected behind interfaces; nothing hardcoded.
- **Execute phases in order.** The Phase 1 contract is frozen thereafter without an ADR.
- Keep `core` framework-free; keep heavy capabilities as optional extras; never leak an internal exception; never break the public API without a major bump + migration guide.
- **Deployment means publishing artifacts**, not running a service (§10.9). If a task asks you to deploy a server from this repository, it is out of scope — say so.
- **Don't over-engineer.** Deliver the §2.5 capability surface simply. The SDK is a product for developers — architecture, stability, docs, tests, versioning, and DX matter as much as the engine underneath.
