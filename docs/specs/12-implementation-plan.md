# 12 — Implementation Plan (task-level)

**Purpose:** Decompose every phase into individually-committable tasks with explicit deliverables,
dependencies, acceptance criteria, and commit messages. This is the working execution list.
**Status:** Authoritative execution order · **Companion to** [11-build-phase-plan.md](11-build-phase-plan.md)

**Read this when:** you are about to start work. Spec 11 tells you *what a phase is for and when it
is done*; this document tells you *what to do next, in what order, and how to know the task landed*.

---

## How to use this document

Each task is sized to be **one branch, one PR, one commit** — a few hours of work, independently
reviewable, leaving the package green. Work top to bottom. Do not start a task whose dependencies
are unmet.

**Status legend** — update the status column as work lands, and mirror it in
[`.claude/memory/PROJECT_STATE.md`](../../.claude/memory/PROJECT_STATE.md):
`☐ not started` · `◐ in progress` · `☑ done` · `⊘ skipped (with ADR)`

### The per-task loop

```
/phase P<n>.<m>          → restate objective, confirm scope, check dependencies
  design the surface     → signatures and names first (spec 04 §3.1)
  implement              → simplest correct version, correct layer
  test                   → must fail without the change
/verify                  → all gates green, honestly reported
/log                     → engineering log + PROJECT_STATE, before committing
  commit + PR            → branch off develop, conventional commit with [P<n>] tag
```

### Definition of done — every task, no exceptions

- [ ] Behaviour implemented in the correct layer with legal imports
- [ ] Tests that **fail without the change**; determinism tests where the rule requires them
- [ ] `ruff` + `ruff format` + `mypy --strict` clean
- [ ] Coverage floor held (global 80%, `core/`+`models/` 95%)
- [ ] Isolation gate prints `OK`
- [ ] Public surface change (if any) is deliberate: golden snapshot updated + CHANGELOG entry
- [ ] Docstrings with runnable offline examples on new public callables
- [ ] Engineering log entry written **before** the commit
- [ ] Conventional commit with phase tag; PR into `develop`

### Two sequencing corrections to spec 11

Resolved here rather than discovered during the build:

1. **Configuration is needed before Phase 8.** P3 selects the runtime by config and P5 selects the
   router by config, but `config/` is a P8 deliverable. Resolution: **P0.3 lands a minimal typed
   `Settings`** with only the fields each phase needs, growing as phases add them; **P8 finalizes**
   precedence, the full variable set, and `configure()`. The rule that env is read only in `config/`
   applies from P0.3 onward, not from P8.
2. **Models are contracts, so they start in P1.** P1 freezes the interfaces, and the interfaces
   reference `AgentState`/`StateUpdate`/`Message`. Resolution: **P1.2 defines the model classes and
   fields as the frozen contract**; **P2 completes their behaviour** (validation, reducer
   integration, serialization). P1.2 is a contract task, not an implementation task.

---

## Phase 0 — Foundations & scaffolding

**Branch prefix:** `chore/p0-*` · **Goal:** a self-contained repository that builds, installs, and
enforces its own rules before any behaviour exists.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P0.1 | Package skeleton | `src/korchestrator/` with every module directory from spec 05, each with `__init__.py`, a module docstring naming its layer and allowed imports, and an explicit `__all__`. `py.typed`. `version.py` = `0.1.0`. | — | ☐ |
| P0.2 | Authoritative manifest | `pyproject.toml`: name `korchestrator`, `hatchling` with `[tool.hatch.version] source = "code"`, `requires-python >=3.10`, core dep `pydantic` only, the full extras matrix, and ruff/mypy/pytest/coverage config per spec 02 §7 | P0.1 | ☐ |
| P0.3 | Minimal `Settings` | `config/settings.py` with `pydantic-settings`, only the fields P0–P3 need (`MOCK_LLM`, `KORCH_RUNTIME`, `PERSISTENCE_BACKEND`). The **only** place env is read. | P0.2 | ☐ |
| P0.4 | OSS-readiness files | `LICENSE` (Apache-2.0), `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md` (Keep a Changelog skeleton), `.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md`, `.editorconfig` | — | ☐ |
| P0.5 | Local quality net | `.pre-commit-config.yaml` per spec 02 §8; `scripts/check_isolation.sh`; `scripts/validate_version.py` | P0.2 | ☐ |
| P0.6 | Import-linter contracts | `.importlinter` with the four contracts from spec 03 §9 (kernel-framework-free, layers, feature-independence, no-cycles) | P0.1 | ☐ |
| P0.7 | CI pipeline | `.github/workflows/ci.yml`: matrix 3.10–3.13; ruff, ruff-format, `mypy --strict`, pytest+coverage, import-linter, isolation gate, version-validate, build, **base-install job** (pydantic only), bandit/pip-audit/gitleaks | P0.2, P0.5, P0.6 | ☐ |
| P0.8 | Release & docs workflow skeletons | `release.yml` (tag-triggered, no publish step wired yet), `docs.yml`, `mkdocs.yml` with `docs/background/` excluded | P0.7 | ☐ |

**Acceptance for the phase**

```bash
pip install -e '.[dev]'
python -c "import korchestrator; print(korchestrator.__version__)"   # 0.1.0
python -m build && pip install --force-reinstall dist/*.whl          # artifact installs clean
bash scripts/check_isolation.sh                                      # OK
```

CI green on all jobs including base-install. ADRs 0001–0008 already landed.

**Commits:** `chore(sdk): scaffold korchestrator package skeleton [P0]` · `chore(sdk): add authoritative pyproject and extras matrix [P0]` · `feat(config): add minimal typed Settings [P0]` · `docs: add OSS-readiness files [P0]` · `ci: add quality net and pipeline [P0]`

---

## Phase 1 — Contracts (the anti-rework crux)

**Branch prefix:** `feat/p1-*` · **Goal:** freeze every contract before implementation exists.

> Nothing in this phase changes after P1 merges without an ADR. Spend the time here.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P1.1 | Exception hierarchy | `exceptions/`: `KorchError` root plus `AuthError`, `ValidationError`, `NetworkError`, `ProviderError`, `TimeoutError`, `RateLimitError`, `QuotaExceededError`, `RoutingError`, `GovernanceHaltError`, `RunFailedError`, `RunTimeoutError`, `ToolError`, `MissingExtraError`. Error codes in `constants/`. | P0.1 | ☐ |
| P1.2 | Model contracts | `models/state.py`, `agent.py`, `plan.py`, `routing.py` — classes and fields per spec 05, frozen where determinism requires. Fields are the contract; behaviour lands in P2. | P1.1 | ☐ |
| P1.3 | ARI ports | `interfaces/identity.py`, `sandbox.py`, `model_gateway.py` — Protocols with documented contracts, concurrency expectations, declared default implementation | P1.2 | ☐ |
| P1.4 | Supporting protocols | `interfaces/runtime.py` (`IDurableRuntime`), `repository.py` (`GraphRepository`, `TenantStore`), `router.py` (`BaseRouter`), `connector.py` (`AUBConnector`) | P1.2 | ☐ |
| P1.5 | Façade signatures | `services/` — `Korch`, `Swarm`, `Agent` type signatures only, raising `NotImplementedError`. `__init__.py` with the `__all__` from spec 04 §6. | P1.3, P1.4 | ☐ |
| P1.6 | Surface guard | `tests/unit/test_public_surface.py` + golden file; spec 04 examples as doctests marked `xfail(strict=True)` until implemented | P1.5 | ☐ |

**Acceptance:** `mypy --strict` clean on `interfaces/`; `from korchestrator import Korch, Swarm, Agent` works; doctests collected and xfailing; snapshot test passes.

**Commits:** `feat(exceptions): freeze KorchError hierarchy [P1]` · `feat(models): define model contracts [P1]` · `feat(interfaces): add ARI ports and protocols [P1]` · `feat(services): freeze public façade signatures [P1]`

---

## Phase 2 — Pregel kernel

**Branch prefix:** `feat/p2-*` · **Goal:** the deterministic BSP heart, running on `pydantic` alone.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P2.1 | Reducers | `core/reducers.py`: `LastValue`, `Append`, `UniqueAppend`, `MergeDict`. Associative, order-independent; `UniqueAppend`/`MergeDict` idempotent. | P1.2 | ☐ |
| P2.2 | Reducer laws | Property-based tests (Hypothesis) proving associativity, order-independence, totality, and idempotence where claimed | P2.1 | ☐ |
| P2.3 | State behaviour | Complete `AgentState`/`StateUpdate`/`Message`: validation, reducer channel binding, frozen-snapshot semantics, `transaction_time`/`valid_time` | P2.1 | ☐ |
| P2.4 | Graph | `core/graph.py`: `AgentGraph`, `Node`, `Edge`, topology builder, validation (unknown node in an edge, orphan, self-loop policy, cycle *allowed*) | P1.2 | ☐ |
| P2.5 | Superstep runner | `core/pregel.py`: `PregelRunner.run_superstep` (`asyncio.gather`) + `synchronize`. **Injected** gateway/agent-callable. Activation: superstep 0 = all nodes, later = inbox only. Halt on `max_supersteps` (default 10) or `halted`. | P2.3, P2.4 | ☐ |
| P2.6 | Message routing | Delivery along directed edges; inbox assembly; A2A message typing hooks | P2.5 | ☐ |
| P2.7 | Determinism suite | Repeatability (same graph+seed → identical result), both halting conditions, activation per superstep, no wall-clock/randomness grep test | P2.5, P2.6 | ☐ |

**Acceptance:** the kernel suite passes **with only `pydantic` installed**. `core/` coverage ≥95%.

```bash
python -m venv /tmp/base && /tmp/base/bin/pip install -e . && /tmp/base/bin/pytest tests/unit/core
```

**Commits:** `feat(core): implement reducers with algebraic laws [P2]` · `feat(core): implement AgentGraph and topology validation [P2]` · `feat(core): implement Pregel superstep runner [P2]` · `test(core): lock determinism and halting [P2]`

---

## Phase 3 — Runtime adapters

**Branch prefix:** `feat/p3-*` · **Goal:** zero-infra local execution and durable Temporal execution, swappable by config.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P3.1 | Local runtime | `runtime/local_runtime.py` — in-process `IDurableRuntime` driving the Pregel loop, injected clock. No Temporal import. | P2.5 | ☐ |
| P3.2 | Runtime selection | `resolve_runtime(settings)` at the composition root; `KORCH_RUNTIME=local\|temporal` | P3.1, P0.3 | ☐ |
| P3.3 | Temporal workflow | `runtime/temporal_runtime.py`: `PregelMaster` workflow + **one** `SuperstepActivity` per superstep. `workflow.now()`, `patched()` gates. `temporalio` lazy-imported here only. | P3.1 | ☐ |
| P3.4 | Durability semantics | Retry policy (exponential backoff + jitter), activity timeouts, continue-as-new roll-over before the 50k-event cap | P3.3 | ☐ |
| P3.5 | HITL signals | Pause/resume/cancel/edit-resume via durable signals, `wait_condition`, up to 24h idle | P3.3 | ☐ |
| P3.6 | Equivalence + replay | Same swarm on both runtimes → equivalent `RunResult`; Temporal replay test; forced mid-run crash resumes from the last superstep with no duplicated work | P3.4, P3.5 | ☐ |

**Acceptance:** both runtimes produce equivalent results; replay test green; base install still imports without `temporalio`.

**Commits:** `feat(runtime): add in-process local runtime [P3]` · `feat(runtime): add Temporal adapter behind IDurableRuntime [P3]` · `feat(runtime): add durable HITL signals [P3]` · `test(runtime): lock replay and crash recovery [P3]`

---

## Phase 4 — Cognitive layer

**Branch prefix:** `feat/p4-*` · **Goal:** reasoning agents, offline-testable.

> Build **MockLM first**. Everything downstream tests against it.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P4.1 | MockLM | `providers/mock_lm.py` — deterministic `IModelGateway`, seeded, no network. The default gateway. | P1.3 | ☐ |
| P4.2 | Local providers | `providers/identity_local.py`, `sandbox_local.py` | P1.3 | ☐ |
| P4.3 | Real gateway | `providers/gateway_openai.py` + `get_lm(model_name)` factory; provider errors wrapped as `ProviderError` | P4.1 | ☐ |
| P4.4 | Agent base | `agents/base.py` — `think(state) -> StateUpdate`, `is_complete`; the frozen-snapshot contract | P2.3 | ☐ |
| P4.5 | Compiled signatures | `agents/signatures.py` — DSPy signature definitions; `dspy` lazy-imported; `MissingExtraError` when absent | P4.4 | ☐ |
| P4.6 | Worker agent | `agents/worker.py` — `TypedPredictor` + bounded ReAct loop (≤3), per-agent `dspy.context`, blocking calls via `asyncio.to_thread` | P4.5 | ☐ |
| P4.7 | Architect agent | `agents/architect.py` — intent + difficulty → `ExecutionPlan`, mock-plan fallback on failure | P4.6 | ☐ |
| P4.8 | Taxonomy | `taxonomy/` — intent/difficulty classification, agent descriptors | P4.7 | ☐ |
| P4.9 | Tier 1+2 façade | Implement `Korch.run` and `Swarm` builder against the kernel; remove the P1 `NotImplementedError`s; un-xfail the doctests | P4.7, P3.2 | ☐ |

**Acceptance:** a custom agent runs end-to-end under MockLM with no network; heterogeneous per-agent models honoured in one superstep; base install imports cleanly and raises `MissingExtraError` on cognitive use.

**Commits:** `feat(providers): add deterministic MockLM gateway [P4]` · `feat(agents): add agent base and compiled signatures [P4]` · `feat(agents): implement worker and architect agents [P4]` · `feat(services): implement Korch and Swarm façade [P4]`

---

## Phase 5 — Model routing

**Branch prefix:** `feat/p5-*` · **Goal:** per-agent model selection, simplest strategy as the default.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P5.1 | Routing models | `ModelCard`, `TaskSemantics`, `RoutingResult`, `RoutingContext` behaviour | P1.2 | ☐ |
| P5.2 | Explicit router + factory | `AGENT_MODEL_MAP` strategy, `get_router()`, documented fallback chain. **This is the default** — works with no extra installed. | P5.1 | ☐ |
| P5.3 | Algorithmic router | Cost/latency/capability ranking with configurable `ROUTING_WEIGHTS`, `ROUTING_PRIORITY_ORDER` | P5.2 | ☐ |
| P5.4 | Semantic router | Embedding similarity vs ModelCard descriptions; `[routing]` extra; cached embedding singleton with configured expiry | P5.3 | ☐ |
| P5.5 | Composite + user function | Strategy composition and a user-supplied callable router | P5.4 | ☐ |
| P5.6 | Wiring + tests | `resolve_router(settings)`; a custom `BaseRouter` plugs in via config with no package edit | P5.5 | ☐ |

**Acceptance:** routing works on the default install with no embedding dependency; advanced strategies load only with `[routing]`.

**Commits:** `feat(routing): add routing models and explicit strategy [P5]` · `feat(routing): add algorithmic and semantic strategies [P5]` · `feat(routing): support custom routers via config [P5]`

---

## Phase 6 — Integration & observability

**Branch prefix:** `feat/p6-*` · **Goal:** tools, MCP, A2A, context compilation, streaming, extension points.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P6.1 | Connector base + registry | `tools/registry.py` — `ConnectorRegistry`, entry-point plugin discovery | P1.4 | ☐ |
| P6.2 | Tool bridge (AUB) | `tools/bridge.py` — `invoke_tool` with schema validation, timeout, rate limiting, spans, security gate. Emits `TOOL_NOT_FOUND` / `TOOL_ACCESS_DENIED`. | P6.1 | ☐ |
| P6.3 | Built-in connectors | `connectors/` — base, filesystem, search (with mock fallback) | P6.2 | ☐ |
| P6.4 | MCP client | `mcp/` — client, hierarchical tool registry, progressive disclosure, stdio + SSE transports. `[mcp]` extra. | P6.2 | ☐ |
| P6.5 | A2A messaging | `a2a/` — typed directed messages, `HandoffTransformer` | P2.6 | ☐ |
| P6.6 | Context compiler + MVC | `context/` — compiler, Minimum Viable Context extraction, pruning/summarization. Off the hot loop, degrades gracefully. | P2.3 | ☐ |
| P6.7 | Event streaming | `events/` — transport-agnostic publisher, SSE-capable, subscriber API. **Emits events; does not serve HTTP.** | P2.5 | ☐ |
| P6.8 | Middleware & hooks | `register_middleware`, `on(event, handler)`; documented ordering and error-isolation semantics per spec 07 | P6.2, P6.7 | ☐ |

**Acceptance:** a custom connector is invokable by an agent; an MCP tool loads; hooks fire in the documented order; MVC measurably reduces context size; an over-privileged call is denied.

**Commits:** `feat(tools): add AUB bridge and connector registry [P6]` · `feat(mcp): add MCP client and tool registry [P6]` · `feat(context): add context compiler and MVC extraction [P6]` · `feat(events): add streaming publisher and hook framework [P6]`

---

## Phase 7 — Governance, security & context graph

**Branch prefix:** `feat/p7-*` · **Goal:** zero-trust governance and bitemporal memory.

> Build **Shield first** — governance audit and trace ingestion depend on redaction existing.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P7.1 | Shield / PII redaction | `security/` — the single consolidated redactor: PAN (Luhn), IBAN, international phone, SSN, secrets → `[MASKED_<TYPE>]`. Fail-closed for high-sensitivity flows. | P1.1 | ☐ |
| P7.2 | Trust scoring | `governance/` — `ControlTowerTelemetry`, per-superstep `check_governance`, 0.0–1.0 score persisting across supersteps | P2.5 | ☐ |
| P7.3 | Policy + audit | Policy engine, audit log, per-agent `hitl_threshold` with `GOVERNANCE_TRUST_THRESHOLD` fallback | P7.2 | ☐ |
| P7.4 | HITL controls | Intervention → runtime pause signal; `pause`/`resume`/`cancel`/`edit_resume` on the façade | P7.3, P3.5 | ☐ |
| P7.5 | Graph repository | `persistence/` — in-memory `GraphRepository` (**default**), `PERSISTENCE_BACKEND=none` runs fully standalone | P1.4 | ☐ |
| P7.6 | Context graph client | `ContextGraphClient` — bitemporal decision/event nodes, valid+transaction time, confidence, provenance, event sourcing, tenant scoping, time-travel query | P7.5, P7.1 | ☐ |

**Acceptance:** a run auto-pauses below threshold and resumes on signal; redaction covers every required format and fails closed; graph queries are tenant-scoped; a fully standalone run completes with no external store.

**Commits:** `feat(security): add consolidated Shield PII redactor [P7]` · `feat(governance): add trust scoring and policy engine [P7]` · `feat(governance): add durable HITL controls [P7]` · `feat(persistence): add bitemporal context graph client [P7]`

---

## Phase 8 — Cross-cutting foundations

**Branch prefix:** `feat/p8-*` · **Goal:** finalize what P0.3 started, plus the remaining utilities.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P8.1 | Settings finalized | Full variable table from spec 08, precedence arg > env > `.env` > default, `configure()`, zero-config MockLM default | P0.3 | ☐ |
| P8.2 | Config isolation test | Test asserting no `os.getenv`/`os.environ` outside `config/` | P8.1 | ☐ |
| P8.3 | Logging | `logging/` — namespaced logger, `NullHandler`, `enable_logging()`, structured fields, secret-safe | P1.1 | ☐ |
| P8.4 | Exception audit | Every internal exception wrapped; boundary tests asserting only `KorchError` subclasses escape | P1.1 | ☐ |
| P8.5 | Serialization | `serializers/` — deterministic, version-tagged round-trip for `AgentState`/`AgentGraph`/`ExecutionPlan`/`ModelCard`/`RunResult`; stable key ordering; migration rule | P2.3 | ☐ |
| P8.6 | Validation | `validators/` — trust-boundary validation, fail-fast with actionable messages | P8.1 | ☐ |
| P8.7 | Telemetry | `telemetry/` — optional OTel spans/metrics, GenAI span tree `agent.run → agent.plan → tool.call → gen_ai.call`, zero overhead when off. `[otel]` extra. | P6.7 | ☐ |

**Acceptance:** env read only in `config/` (test-enforced); logging fully disable-able; no raw internal exception escapes; serde round-trips stable across a version bump.

**Commits:** `feat(config): finalize typed Settings and configure() [P8]` · `feat(logging): add namespaced disable-able logging [P8]` · `feat(serializers): add version-tagged deterministic serialization [P8]` · `feat(telemetry): add optional OTel instrumentation [P8]`

---

## Phase 9 — Remote client (Python only)

**Branch prefix:** `feat/p9-*` · **Goal:** the optional Tier 4 client. TypeScript is deferred per [ADR 0008](../adr/0008-typescript-client-deferred.md).

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P9.1 | Transport + auth | `clients/` — `httpx` async+sync base, `Authorization: Bearer`, timeout 30s, retries 3 with jittered backoff, retry 429/502/503/504 only | P8.4 | ☐ |
| P9.2 | Credential safety | Redaction from logs, exceptions, telemetry; test asserting credentials never appear in any output or on disk | P9.1 | ☐ |
| P9.3 | Run lifecycle | `run`, `run_swarm`, `run_and_wait`, `get_run`, `wait`, `list_runs`, `get_run_summary`; numeric→string status normalization | P9.1 | ☐ |
| P9.4 | Control + identity | `resume`, `cancel`, `edit_resume`, `me`, `my_quota`, `my_runs`, key management | P9.3 | ☐ |
| P9.5 | Streaming | SSE `stream` as an async iterator; reconnect semantics | P9.3 | ☐ |
| P9.6 | Discovery | `tools`, `models`, `swarm_templates` | P9.3 | ☐ |
| P9.7 | Errors + tests | `ApiError(status, message, code, trace_id)` as a `KorchError`; full `respx` suite against the spec 04 §7 contract | P9.4, P9.5 | ☐ |
| P9.8 | Parity matrix | `docs/parity-matrix.md` — every Python method marked `TS: planned` | P9.7 | ☐ |

**Acceptance:** every documented method exists and is tested against mocked transport; the local kernel remains fully usable with `[remote]` uninstalled.

**Commits:** `feat(clients): add remote transport with bearer auth [P9]` · `feat(clients): implement run lifecycle and control [P9]` · `feat(clients): add SSE streaming [P9]` · `docs: add Python/TypeScript parity matrix [P9]`

---

## Phase 10 — Testing, benchmarks & gates

**Branch prefix:** `test/p10-*` · **Goal:** close coverage gaps and establish the performance baseline.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P10.1 | Coverage sweep | Fill unit gaps to the floors; convert any incidental coverage into meaningful assertions | P9 | ☐ |
| P10.2 | Integration suite | Runtime swap, routing strategies, tools, MCP, governance pause/resume | P9 | ☐ |
| P10.3 | E2E suite | Full swarm on local **and** Temporal; HITL round trip; streaming consumption | P10.2 | ☐ |
| P10.4 | Regression harness | `tests/regression/` — one locked test per fixed bug, each naming the issue | P10.1 | ☐ |
| P10.5 | Benchmarks | `benchmarks/` — superstep parallelism scales ~1× not N×; import/startup time; memory per run; serde throughput. Commit `baseline.json`. | P10.3 | ☐ |
| P10.6 | Ratchet | Raise coverage floors to the achieved level; wire benchmark regression detection into CI | P10.5 | ☐ |

**Acceptance:** full matrix green across 3.10–3.13; baseline committed; no test touches network, sleeps, or shared state.

**Commits:** `test: complete integration and e2e suites [P10]` · `test: add benchmark baseline [P10]` · `ci: ratchet coverage floors [P10]`

---

## Phase 11 — Documentation, examples & DX

**Branch prefix:** `docs/p11-*` · **Goal:** ship docs as part of the product.

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P11.1 | Site scaffold | `mkdocs.yml` (Material), `docs/index.md`, nav, `docs/background/` excluded, strict build | P0.8 | ☐ |
| P11.2 | Getting started | `installation.md`, `quickstart.md` — install to first successful run using the quickstart alone | P11.1 | ☐ |
| P11.3 | Tutorials | Swarm, custom agent, custom tool, MCP, custom router, HITL, streaming | P11.2 | ☐ |
| P11.4 | API reference | Auto-generated from docstrings (`mkdocstrings`) into `docs/reference/` | P11.1 | ☐ |
| P11.5 | Guides | `architecture.md`, `versioning.md`, `releases.md`, `deployment.md`, `migration.md`, `faq.md`, `troubleshooting.md` — user-facing derivations of the specs | P11.3 | ☐ |
| P11.6 | Examples | `examples/` — every script runs unmodified on a clean install; CI executes them | P11.3 | ☐ |

**Acceptance:** `mkdocs build --strict` passes with no broken links; every example runs green in CI.

**Commits:** `docs: add documentation site and getting started [P11]` · `docs: add tutorials and API reference [P11]` · `docs: add executable examples [P11]`

---

## Phase 12 — Release automation

**Branch prefix:** `chore/p12-*` · **Goal:** a one-tag, fully automated, immutable release.

> **ADR 0021 (2026-08-25) supersedes ADR 0020.** The repository is now public and releases
> publish to PyPI via Trusted Publishing, as originally specified below — ADR 0020's private-only
> narrowing (2026-08-12–2026-08-25) is no longer in effect. See
> [ADR 0021](../adr/0021-repository-goes-public-pypi-trusted-publishing.md).

| # | Task | Deliverables | Depends on | Status |
|---|---|---|---|---|
| P12.1 | Version validation | `version-validate` job asserting `version.py` == package metadata == tag | P0.5 | ☑ |
| P12.2 | Artifact verification | Build wheel+sdist; install and import **the built artifact** in a clean environment outside the source tree | P12.1 | ☑ |
| P12.3 | Supply chain | `SHA256SUMS` checksums, SBOM (CycloneDX), and build-provenance attestation over the built wheel+sdist. License allowlist scan not yet implemented | P12.2 | ☑ |
| P12.4 | Publish | `publish` job uploads to PyPI via Trusted Publishing (OIDC, no stored token); `github-release` job publishes a GitHub Release with the wheel, sdist, SBOM, and checksums attached, gated on P12.2/P12.3 | P12.3 | ☑ |
| P12.5 | Release notes + docs deploy | Notes extracted from the tagged `CHANGELOG.md` section, attached to the GitHub Release. `deploy-docs` job redeploys documentation on every release | P12.4 | ☑ |
| P12.6 | Dry run | `verify-published` job: installs via `pip install korchestrator==X.Y.Z` from the real public PyPI index, no credential, with a short retry loop for index-propagation lag | P12.5 | ☑ |
| P12.7 | Release automation script | `scripts/cut_release.py` — automates the version bump, CHANGELOG dating, release-branch/PR creation (`prepare`), and tag creation/push (`tag`) described in spec 10 §9 | P12.1 | ☑ |

**Acceptance:** a tagged release builds, checksums, verifies version everywhere, installs from the artifact in a clean environment, publishes to PyPI and as an immutable GitHub Release, and is installable via a bare `pip install korchestrator` with no credential — with no backend, frontend, container, or npm job anywhere.

**Commits:** `ci: add version validation and artifact verification [P12]` · `ci: add checksums and private GitHub Release publishing [P12]` · `feat(scripts): add release-cutting automation [P12]` · `chore(release): cut v0.1.0 [P12]`

---

## Critical path

Tasks on this path block everything downstream. Protect their schedule; do not let them slip for parallelizable work.

```
P0.1 → P0.2 → P1.1 → P1.2 → P1.3/P1.4 → P1.5
     → P2.1 → P2.3 → P2.5 → P3.1 → P3.2
     → P4.1 → P4.4 → P4.6 → P4.9  ← first end-to-end run
     → P10 → P11 → P12
```

**P4.9 is the milestone that matters most.** It is the first point where the Tier 1 one-liner
actually runs, which means every claim in the README becomes testable rather than aspirational.
Phases 5–9 add capability around a system that already works end to end.

## What can run in parallel

| Independent tracks | After |
|---|---|
| P5 (routing) and P6 (tools/MCP/context) | P4.9 |
| P7 (governance) and P8 (cross-cutting) | P6 |
| P9 (remote client) | P8.4 — depends only on the contract and error handling, not on the kernel |
| P11 docs authoring | Continuously; consolidate in P11 |

## Risk register

| Risk | Signal | Mitigation |
|---|---|---|
| Contract churn after P1 | Repeated ADRs amending interfaces | Spend more time in P1; treat an amendment as a review failure, not routine |
| Temporal determinism bugs | Replay test failing intermittently | The determinism grep runs on every kernel commit; replay test is blocking, never quarantined |
| `core/` acquiring a dependency | import-linter contract failure | Treat as a design signal: it means a port is missing, not that the contract is wrong |
| Coverage theatre | Coverage rises while bugs escape | Review asserts on behaviour, not line counts; regression test required per bug |
| Scope creep from the backlog | Speculative execution, DSL, FinOps appearing in a PR | Out of scope per spec 01 §3; needs an ADR and a phase, not a commit |
| Optional extra leaking into base | Base-install CI job failing | The job is blocking; never make it non-required to unblock a merge |

---

**Next:** start at **P0.1** with `/phase P0.1`.
