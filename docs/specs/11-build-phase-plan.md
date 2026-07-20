# 11 — Build Phase Plan

**Purpose:** The ordered implementation plan. Each phase states its Objective, Build tasks, Public surface, Validation, and Definition of Done.
**Status:** Authoritative · **Execute strictly in order**

**Read this when:** starting any implementation task. Find the task here first, restate its Objective and Definition of Done, and confirm it is in scope before writing code.

---

## How to use this plan

1. **Locate the task.** Every implementation task belongs to exactly one phase. If it does not, it is either out of scope ([01-scope-and-principles.md](01-scope-and-principles.md) §3) or needs an ADR.
2. **Restate before building.** Objective, Build, Validation, Definition of Done — in your own words, in the PR description.
3. **Design the public surface first.** Check names against [04-public-api.md](04-public-api.md) §3.1 before implementing.
4. **Place code in the correct layer.** [03-architecture.md](03-architecture.md) §2.
5. **Land the tests that lock the behaviour.** A capability with no test is not delivered.
6. **Run the gates until green.** [09-testing-and-quality.md](09-testing-and-quality.md).
7. **Update the engineering log** (`.claude/memory/ENGINEERING_LOG.md`) — before committing, not after.
8. **Commit conventionally, PR into `develop`.**

**Phases do not overlap.** Phase N+1 does not start until Phase N's Definition of Done is met. The one exception is documentation, which is written continuously and consolidated in P11.

---

## Coverage contract

Every capability below must be reachable through the public API by the end of the build. This table maps capability → module → phase and is the checklist for "is the SDK feature-complete".

| Category | Capability | Module | Phase |
|---|---|---|---|
| Execution | Durable, parallel, recursive, event-driven execution; recovery; scheduling; barriers | `core/`, `runtime/` | P2, P3 |
| Agents | Multi-agent coordination, meta/architect/planner agents, per-agent model isolation | `agents/` | P4 |
| Context | Context compiler, MVC, layering, pruning/summarization, event sourcing | `context/`, `persistence/` | P6, P7 |
| Reasoning | Decomposition, planning, validation, routing, intent/difficulty taxonomy, compiled signatures | `agents/`, `routing/`, `taxonomy/` | P4, P5 |
| Integration | Unified tool layer (AUB), MCP, connectors, A2A messaging | `tools/`, `mcp/`, `a2a/` | P6 |
| Governance | Trust scoring, policy, RBAC, audit, HITL, PII redaction | `governance/`, `security/` | P7 |
| Observability | Execution/reasoning/context tracing, event logs, streaming, OTel | `events/`, `telemetry/` | P6, P8 |
| Scalability | Distributed execution, independent vertices, failure recovery | `core/`, `runtime/` | P2, P3 |
| Interface | One-liner, swarm builder, kernel embed, remote client | `services/`, `clients/` | P2–P9 |

---

## PHASE 0 — Foundations, Scope Freeze & Scaffolding

**Objective.** Stand up the self-contained repository skeleton, settle every deferred decision, and install the quality and isolation net *before* any behaviour exists.

**Build.**
1. Create the [02-repository-structure.md](02-repository-structure.md) layout: `src/korchestrator/` with stub modules and explicit `__all__`.
2. The authoritative `pyproject.toml`: name `korchestrator`, `hatchling`, `requires-python >=3.10`, core dependency `pydantic` only, the extras matrix.
3. `version.py` (`0.1.0`) and `py.typed`.
4. OSS-readiness files: `LICENSE` (Apache-2.0), `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, issue/PR templates.
5. `.pre-commit-config.yaml`, `.editorconfig`, `.gitignore`.
6. ADRs 0001–0008 for every settled decision.
7. `ci.yml`: ruff, `mypy --strict`, pytest + coverage floor, build check, version-validate, import-isolation gate, import-linter contracts.
8. `release.yml` skeleton (publish on `v*` tag) and `docs.yml`.

**Public surface.** `__version__`.

**Validation.** `pip install -e .` succeeds; `import korchestrator` works; CI is green including the isolation gate and version-validate; `python -m build` produces a wheel that installs in a clean environment.

**Definition of Done.** Package builds standalone. Every decision in ADRs 0001–0008 is recorded and Accepted. CI and the isolation gate are active and blocking. The version is single-sourced.

---

## PHASE 1 — Public API & Interface Contracts

**Objective.** Design the public surface and the contracts first. This is the anti-rework crux of the entire build.

**Build.**
1. ARI ports in `interfaces/`: `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway` — each a Protocol with a documented contract, concurrency expectations, and a declared default implementation.
2. Supporting protocols: `IDurableRuntime`, `GraphRepository`, `TenantStore`, `BaseRouter` (`async select_model(task, models) -> RoutingResult`), `AUBConnector` (`async execute(tool, args, invocation) -> ToolResult`).
3. Façade type signatures for `Korch`, `Swarm`, `Agent`, plus `__init__.__all__` — **types only, no implementation**. The [04-public-api.md](04-public-api.md) examples land as doctests, xfail-strict until implemented.
4. Freeze the exception hierarchy.
5. Land the public-surface snapshot test with its golden file.

**Public surface.** Interfaces, exceptions, and façade type signatures.

**Validation.** `mypy --strict` clean on `interfaces/`; the façade imports; doctests are collected and marked xfail-strict; the snapshot test passes.

**Definition of Done.** Every port and protocol is defined and documented. The façade API is frozen. The exception hierarchy is final. **No contract changes after this point without an ADR.**

---

## PHASE 2 — Core Execution Kernel (Pregel, framework-free)

**Objective.** Build the deterministic BSP engine as the dependency-light heart of the SDK.

**Build.**
1. `models/state.py` — `AgentState`, `StateUpdate`, `Message`, `Performative`, `RunStatus`.
2. `core/reducers.py` — `LastValue`, `Append`, `UniqueAppend`, `MergeDict`, each associative and order-independent.
3. `core/pregel.py` — `PregelRunner.run_superstep` via `asyncio.gather`, plus `synchronize`.
4. `core/graph.py` — `AgentGraph`, `Node`, `Edge`, topology builder and validation.
5. The runner takes an **injected** gateway/agent-callable. It never constructs its own collaborators.
6. Activation rules: superstep 0 activates all nodes; later supersteps activate only nodes with inbox messages. Halt on `max_supersteps` (default 10) or `halted=True`.

**Public surface.** `korchestrator.core`, `korchestrator.models`.

**Validation.** The kernel suite runs with **only `pydantic` installed** and covers: activation per superstep, each reducer, reducer algebraic laws (property-based), message routing along edges, both halting conditions, and identical results across repeated runs of the same graph and seed.

**Definition of Done.** The kernel runs a superstep with only pydantic installed. Determinism and halting are test-locked. `core/` coverage ≥95%.

---

## PHASE 3 — Runtime Adapters (Local + Durable)

**Objective.** Run locally with zero infrastructure *and* durably on Temporal, selected by config alone.

**Build.**
1. `runtime/local_runtime.py` — in-process `IDurableRuntime` driving the Pregel loop. No Temporal import. The default for dev, CI, and embedding.
2. `runtime/temporal_runtime.py` — the Temporal adapter: a single `PregelMaster` workflow invoking one `SuperstepActivity` per superstep, preserving determinism (`workflow.now()`, `patched()` gates), retry policy with backoff and jitter, HITL signals, and the activity boundary. `temporalio` is imported **only** here.
3. Config selection: `KORCH_RUNTIME=local|temporal`.
4. Continue-as-new roll-over before the Temporal 50k-event limit.

**Public surface.** `Korch(runtime=...)` and `Settings`; `IDurableRuntime` for custom runtimes.

**Validation.** The same swarm completes on both runtimes with an equivalent `RunResult`. The Temporal replay test passes. A forced mid-run crash resumes from the last superstep with no duplicated work.

**Definition of Done.** Local runtime works with zero infrastructure. Temporal preserves durability, HITL, and determinism. The runtime is swappable by config alone.

---

## PHASE 4 — Cognitive Layer

**Objective.** Build the reasoning layer — meta-agents, workers, compiled signatures, intent taxonomy, model providers.

**Build.**
1. `agents/base.py` — the `think(state) -> StateUpdate` contract and `is_complete`.
2. `agents/worker.py` — `WorkerAgent`: `TypedPredictor` plus a bounded ReAct loop (≤3 iterations), per-agent `dspy.context`.
3. `agents/architect.py` — `ArchitectAgent`: intent and difficulty → `ExecutionPlan`, with mock-plan fallback on failure.
4. `agents/signatures.py` — the compiled signatures.
5. `taxonomy/` — intent and difficulty classification, agent descriptors.
6. `providers/` — `gateway_openai.py` (default `IModelGateway`), `mock_lm.py` (deterministic MockLM), `identity_local.py`, `sandbox_local.py`, and a `get_lm(model_name)` factory.
7. `dspy` is an extra and is lazy-imported.

**Public surface.** `Agent`, `WorkerAgent`, `ArchitectAgent`, the `Signature` base, the taxonomy classifier, `IModelGateway` and providers.

**Validation.** A custom agent (new signature + `think`) runs end-to-end under MockLM with no network. Heterogeneous per-agent models are honoured within one superstep. The base install (no `[dspy]`) still imports cleanly and raises an actionable `MissingExtraError` when the cognitive layer is used.

**Definition of Done.** Agents run under MockLM offline. Real models work via the gateway. Adding an agent requires no core edit.

---

## PHASE 5 — Model Routing

**Objective.** Per-agent model selection as strategies behind one `BaseRouter`, with the simplest path as the default.

**Build.**
1. `routing/` models: `ModelCard`, `TaskSemantics`, `RoutingResult`, `RoutingContext`.
2. A `get_router()` factory and the strategies: Explicit, Semantic, Algorithmic, Composite, UserFunction — plus a documented fallback chain.
3. Semantic/embedding routing and the ModelCard database are opt-in behind `[routing]`. **Explicit plus one fallback is the default.**
4. Config: `ROUTING_STRATEGY`, `AGENT_MODEL_MAP`, `ROUTING_WEIGHTS`, `ROUTING_PRIORITY_ORDER`, `EMBEDDING_PROVIDER`, `MODELCARD_*`.
5. Cache router and embedding singletons behind the composition root.

**Public surface.** `get_router()`, `BaseRouter`, the routing models.

**Validation.** Explicit mapping picks the named model. A custom `BaseRouter` plugs in via config without editing the package. Cost influences algorithmic ranking. The embedding cache expires as configured.

**Definition of Done.** Routing works on the default install with no embedding dependency. Advanced strategies load only with `[routing]`.

---

## PHASE 6 — Integration & Observability

**Objective.** Build the tool layer, A2A messaging, streaming, the context compiler, and the extension framework.

**Build.**
1. `tools/` (AUB) — `bridge.py` (`invoke_tool` with schema validation, timeout, rate limiting, spans, and the security gate), `registry.py` (`ConnectorRegistry` + plugin loading), `connectors/` (base, search, filesystem, with a mock search fallback). Emits `TOOL_NOT_FOUND` / `TOOL_ACCESS_DENIED`.
2. `mcp/` — MCP client and hierarchical tool registry with progressive disclosure.
3. `a2a/` — typed directed messages and the handoff transformer.
4. `context/` — the Context Compiler, Minimum Viable Context extraction, pruning and summarization. Runs off the hot loop and degrades gracefully.
5. `events/` — the streaming publisher, transport-agnostic and SSE-capable. **The SDK emits events; it does not serve HTTP.**
6. The extension framework: middleware and event registration (pre/post-superstep, pre/post-tool, on-message, on-governance-pause).

**Public surface.** `AUBConnector`, `register_tool`/`register_connector`, the MCP client, `register_middleware`, `on(event, handler)`, the streaming subscriber, the context compiler.

**Validation.** A custom connector is invokable by an agent. An MCP tool loads. A middleware/hook fires in the documented order. MVC measurably reduces context size. An over-privileged tool call is denied.

**Definition of Done.** Adding a tool, MCP server, or hook needs no core edit. Streaming and context compilation work.

---

## PHASE 7 — Governance, Security & Context Graph

**Objective.** Zero-trust governance plus the bitemporal Context Graph.

**Build.**
1. `governance/` — trust scoring, `check_governance` and intervention → runtime pause signal, HITL resume/modify/cancel, per-agent `hitl_threshold` with a global `GOVERNANCE_TRUST_THRESHOLD` fallback, policy engine and audit log.
2. `security/` — the single consolidated PII redactor (PAN with Luhn check, IBAN, international phone, SSN, secrets), masking to `[MASKED_<TYPE>]`, failing closed for high-sensitivity flows.
3. `persistence/` — `ContextGraphClient` (bitemporal decision and event nodes, valid-time and transaction-time, confidence, provenance, event sourcing) behind `GraphRepository`. In-memory backend is the default; external backends are post-1.0. `PERSISTENCE_BACKEND=none` runs fully standalone.

**Public surface.** Governance config on `Korch`/`Swarm`, HITL controls (`pause`/`resume`/`cancel`/`edit_resume`), `ContextGraphClient`, `GraphRepository`.

**Validation.** A run auto-pauses below threshold and resumes on signal. PII redaction covers every required format and fails closed. Context-graph queries are tenant-scoped and support time-travel. A fully standalone run with no external store completes.

**Definition of Done.** Governance, HITL, redaction, and the Context Graph are usable from the SDK. The default install needs no external services.

---

## PHASE 8 — Cross-Cutting Foundations

**Objective.** Finalize configuration, logging, telemetry, errors, serialization, and validation as first-class, tested modules.

**Build.** `config/` (one typed `Settings`, precedence arg > env > file > default, every documented variable, zero-config MockLM default); `logging/` (namespaced, disable-able); `telemetry/` (optional OTel, zero cost when off); `exceptions/` (finalized, wrapping every internal error); `serializers/` (version-tagged round-trip); `validators/`; secret handling; `constants/`.

**Public surface.** `Settings`/`configure()`, `enable_logging()`, the exceptions, `to_json`/`from_json`.

**Validation.** A test enforces that env is read only inside `config/`. Logging is fully disable-able. Every internal exception surfaces as a `KorchError` subclass. Serialization round-trips remain stable across a version bump.

**Definition of Done.** All cross-cutting standards implemented and tested. No raw internal exception escapes. Config is single-sourced.

---

## PHASE 9 — Remote Client

**Objective.** Ship the optional remote client as `korchestrator.remote`.

> **TypeScript is deferred.** Per [ADR 0008](../adr/0008-typescript-client-deferred.md) this phase builds the **Python client only**. The parity matrix ships as documentation with every method marked `TS: planned`. There is no `clients/typescript/` directory and no npm job in CI.

**Build.**
1. The Python thin client under `clients/`, re-exported as `korchestrator.remote.KorchestratorClient`. `httpx`-based, async and sync, behind `[remote]`.
2. Honour the [04-public-api.md](04-public-api.md) §7 contract exactly: Bearer auth and scopes, run lifecycle, status normalization, webhook semantics, retry policy.
3. Surface: `run`, `run_swarm`, `run_and_wait`, `get_run`, `wait`, `list_runs`, `get_run_summary`, `me`, `my_quota`, `my_runs`, `resume`, `cancel`, `edit_resume`, `stream`, `tools`, `models`, `swarm_templates`, and key management where authorized.
4. The parity matrix document.

**Public surface.** `korchestrator.remote`.

**Validation.** Every documented method exists and is tested against a mocked transport (`respx`). Credentials never appear in logs, exceptions, or telemetry — asserted by test. The streaming example consumes SSE. The parity matrix is complete with planned gaps labelled.

**Definition of Done.** The remote client ships behind its extra, docs match code exactly, and the local kernel remains fully usable without it installed.

---

## PHASE 10 — Testing, Benchmarks & Quality Gates

**Objective.** Comprehensive, enforced coverage against the final shape.

**Build.** Unit tests for every module; integration (runtime swap, routing, tools, MCP, governance); e2e (full swarm on local and Temporal); regression (a locked test per fixed bug); performance (`benchmarks/`: superstep parallelism scales ~1× not N×, import and startup time, memory per run); smoke (import plus the one-liner on a clean install). Enforce and ratchet the coverage floor. Include the Temporal replay test and a live-mode smoke against a stub gateway.

**Validation.** The full CI matrix is green across supported Python versions. Benchmarks are recorded as a committed baseline. No test depends on the network, wall-clock sleeps, or shared developer state.

**Definition of Done.** All six test types present and green. Coverage floor enforced. Benchmark baseline committed.

---

## PHASE 11 — Documentation, Examples & DX

**Objective.** Ship documentation as part of the product.

**Build.** The repository-owned docs site (`docs/` + `mkdocs.yml`): Installation, Quick Start, Tutorials (swarm, custom agent, custom tool, MCP, custom router, HITL, streaming), auto-generated API reference, Architecture guide, Migration guide, FAQ, Troubleshooting, and the Versioning/Release/Deployment pages. Every `examples/` script runs unmodified on a clean install.

**Validation.** Docs build in CI with no broken links. Every example runs green in CI. A new developer gets from install to first successful run using the Quick Start alone.

**Definition of Done.** Full doc set published. Examples executable. Migration and deployment guidance present.

---

## PHASE 12 — CI/CD, Packaging & Publishing

**Objective.** An automated, reproducible, one-tag release.

**Build.** CI stages: lint, format, type-check, test + coverage, security scan (bandit, pip-audit, gitleaks), import-isolation gate, import-linter, build (wheel + sdist), version-validate, clean-environment install smoke test **of the built artifact**, docs-build. `release.yml` publishes only after all of these pass on a `vX.Y.Z` tag, then generates SBOM and checksums, signs artifacts where supported, publishes release notes, and deploys the documentation. Enforce CHANGELOG, SemVer, and the deprecation policy.

**Validation.** A tagged release builds, tests, scans, verifies the version everywhere, installs from the built artifact in a clean environment, publishes immutably, and deploys docs — with **no backend or frontend job anywhere in the pipeline**.

**Definition of Done.** One-tag release works end to end. Artifact integrity metadata is available. Versioning is enforced. Publishing and docs deployment are automated.

---

## PHASE 13 — External Backend Adapter — OUT OF SCOPE

> **Do not execute.** This phase belongs to a separate repository, requires explicit approval and its own plan, and is not a dependency of this one. See [ADR 0007](../adr/0007-external-backend-boundary.md).

**Objective (future).** Let an external service consume the **published** SDK as a thin adapter adding only transport, authentication, and tenancy. The SDK must never import, require, or be versioned against that service.

---

## Final gate

The SDK is complete when all of the following hold:

- [ ] The production-grade checklist in [01-scope-and-principles.md](01-scope-and-principles.md) §7 is satisfied
- [ ] The isolation gate is green — the SDK is self-contained
- [ ] The Tier 1 one-liner runs with zero infrastructure on a clean install
- [ ] Durable mode preserves crash recovery, HITL, and determinism
- [ ] Every capability in the coverage contract is reachable from the public API
- [ ] Docs, examples, tests, CI/CD, versioning, deployment guidance, and OSS files are complete
- [ ] The package publishes on a tag
