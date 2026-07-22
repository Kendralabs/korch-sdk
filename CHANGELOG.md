# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **0.x notice.** While the version is `0.x`, a MINOR release may contain breaking
> changes. PATCH releases are never breaking. See docs/versioning.md.

## [0.1.0] - Unreleased

The first development line. This version is being assembled phase by phase and has not
yet been published; the date is fixed when `0.1.0` is released (see the release runbook in
`docs/specs/10-release-versioning-and-cicd.md` §9).

### Added

- Extension framework (Phase 6): agent-to-agent messaging (`korchestrator.a2a` — `directed_message`,
  `HandoffTransformer`); transport-agnostic event streaming (`korchestrator.events` — `Event`,
  `EventPublisher`, `Subscription`, `format_sse`; the SDK emits, it does not serve HTTP); and
  middleware/hooks (`korchestrator.services.Middleware`/`HookRegistry`) with the spec 07 §9 ordering
  and error isolation — a hook can never fail a run. `Korch`/`Swarm` accept `middleware=…` and expose
  `.on(event, handler)`; hooks fire around each superstep on the local runtime via an injected
  `SuperstepObserver` (default off, so determinism is unaffected).
- Context compiler (Phase 6): `korchestrator.context` with `ContextCompiler.compile()` and
  `CompiledContext` — Minimum Viable Context extraction that keeps the objective and the substantive
  messages (answers/handoffs) first, packs the recent remainder under a character budget, and prunes
  the rest. An optional `Summarizer` seam folds the pruned tail; it degrades gracefully to a count.
  Runs off the hot loop and is deterministic without a summariser.
- MCP client (Phase 6): `korchestrator.mcp` with `MCPServerConfig` (stdio/sse descriptor) and
  `MCPClient.discover()`, which connects to an MCP server and returns its tools as `Connector`s for
  the shared AUB registry — so agents can't tell an MCP tool from a native one. Discovery failures
  are non-fatal; the real transport needs the `[mcp]` extra. The `Connector` contract moved to
  `korchestrator.interfaces` (added to its `__all__`) so `tools` and `mcp` share it without importing
  each other; the `korchestrator.tools` import path is unchanged.
- Agent Utility Bridge (Phase 6): `korchestrator.tools` with `ConnectorRegistry` (register a
  `Connector`, wrap a function via `register_tool`, entry-point `discover()`), the `Connector`
  contract, and `invoke_tool` — the single path enforcing the mount access gate, rate limiting,
  JSON-Schema argument validation, timeout, an optional redaction seam, and duration/telemetry.
  Built-in `FilesystemConnector` (root-confined, traversal-denied) and `MockSearchConnector`
  (deterministic offline). New `TOOL_EXECUTION_FAILED` error code. Registration is via the registry
  and `Korch(connectors=…)`, not a process global (ADR 0015).
- Model routing (Phase 5), wired into execution: `resolve_router(settings, router=…)` and a
  `UserFunctionRouter` that adapts a `(RoutingContext) -> RoutingResult` callable (sync or async).
  A custom `BaseRouter` plugs in by injection — `Korch(router=…)` / `Swarm(router=…)` — with no
  package edit (entry-point discovery deferred, see ADR 0014). `Korch.run`/`Swarm.run` now select a
  model per default-worker agent at composition time (deterministic, replay-safe), honouring a model
  pinned on the agent and `AGENT_MODEL_MAP`.
- Model routing (Phase 5), ranking strategies: `AlgorithmicRouter` (weighted quality/cost/latency
  ranking over `ROUTING_WEIGHTS`, with capability filtering and cost estimation) and `SemanticRouter`
  (embedding-similarity selection against `ModelCard` descriptions, with a TTL-cached embedding
  singleton). Semantic embeddings require the `[routing]` extra and are imported lazily; the strategy
  is testable offline via an injected `Embedder`. `get_router()` gained a keyword-only `embedder`.
- Model routing (Phase 5), explicit strategy: `korchestrator.routing` with `get_router()`, the
  `BaseRouter` supporting protocol (re-exported from `interfaces`), and the explicit + fallback
  strategies behind a `CompositeRouter` chain. The default (`ROUTING_STRATEGY="explicit"`) selects a
  per-agent model — a pinned model or an `AGENT_MODEL_MAP` entry — and always resolves via a
  never-declining fallback tail, on the base install with no extra. A built-in `ModelCard` catalogue
  (`builtin_model_cards()`) and a file/builtin loader (`load_model_cards()`). New `Settings` fields
  for routing (`routing_strategy`, `agent_model_map`, `routing_weights`, `routing_priority_order`,
  `embedding_provider`, `modelcard_*`), with `Settings.from_env` parsing their JSON/CSV forms.
- Self-contained `korchestrator` package skeleton: every module directory from the module
  catalogue, each with a layer-naming docstring and an explicit `__all__`; `py.typed`;
  and the single-source `version.py` pinned to `0.1.0`.
- Authoritative `pyproject.toml`: `hatchling` build backend with the version sourced
  dynamically from `version.py`, `requires-python >=3.10`, the `pydantic`-only core
  dependency, the full extras matrix, and the `ruff` / `mypy` / `pytest` / `coverage`
  configuration.
- Minimal typed `korchestrator.config.Settings` (`mock_llm`, `korch_runtime`,
  `persistence_backend`) with `Settings.from_env()`, the single place the package reads the
  environment. Built on `pydantic.BaseModel` to keep the base install `pydantic`-only
  (see ADR 0009).
- OSS-readiness files: Apache-2.0 `LICENSE`, `NOTICE`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue and pull-request templates, and
  `.editorconfig`.
- The `KorchError` exception hierarchy — `KorchError` and its subclasses (`ConfigurationError`,
  `ValidationError`, `AuthError`, `NetworkError`, `TimeoutError`, `RateLimitError`,
  `QuotaExceededError`, `ProviderError`, `RoutingError`, `ToolError`, `GovernanceHaltError`,
  `RunFailedError`, `RunTimeoutError`, `MissingExtraError`) — each carrying a stable error code.
  Everything the SDK raises deliberately is a `KorchError`.
- The frozen Pydantic domain models: `AgentState`, `Message`, `StateUpdate`, `MessageRole`,
  `Performative`, `RunStatus`, `AgentConfig`, `AgentPersona`, `AgentDescriptor`, `ExecutionPlan`,
  `TaskDecomposition`, `ModelCard`, `TaskSemantics`, `RoutingContext`, `RoutingResult`, `RunResult`,
  `ToolResult`. All are immutable and reject unknown fields.
- The ARI ports (`IIdentityProvider`, `IExecutionSandbox`, `IModelGateway`) and the supporting
  protocols (`IDurableRuntime`, `GraphRepository`, `TenantStore`, `BaseRouter`, `AUBConnector`),
  reachable via `korchestrator.interfaces`.
- The public façade — `Korch` (Tier-1 one-liner), `Swarm` (Tier-2 typed builder), and `Agent` —
  and the frozen, curated top-level public API (`korchestrator.__all__`, 27 names) guarded by a
  golden-file snapshot test. Execution (`Korch.run`/`Swarm.run`) is wired to the kernel in a later
  release; the builder surface is usable now.
- The framework-free Pregel kernel, embeddable directly via `korchestrator.core` (Tier 3): the four
  channel reducers (`LastValue`, `Append`, `UniqueAppend`, `MergeDict`) with proven algebraic laws;
  `AgentGraph`/`Node`/`Edge` with topology validation (cycles and orphans allowed); `ChannelSchema`
  for binding channels to reducers; and `PregelRunner`, which runs a graph as deterministic Bulk
  Synchronous Parallel supersteps (activation, barrier reduce, message routing, and halting) against
  an injected clock. Runs on a `pydantic`-only base install.
- `AgentState.halted_agents` — a new optional field (default empty) recording which nodes have
  individually halted, so a halted node is never reactivated. Additive and backward-compatible.
- The in-process local runtime, `korchestrator.runtime.LocalRuntime` — an `IDurableRuntime` that
  runs a graph to completion with zero infrastructure (the `KORCH_RUNTIME=local` default) — and
  `resolve_runtime(settings, graph, *, clock, ...)`, which selects the runtime from config.
  Selecting `temporal` without the `[temporal]` extra raises an actionable `MissingExtraError`.
- The durable Temporal runtime (behind `[temporal]`): a single `PregelMaster` workflow driving the
  superstep loop in deterministic workflow scope, invoking one `SuperstepActivity` per superstep for
  agent compute, with a bounded jittered retry policy, activity timeouts, and `continue_as_new`
  roll-over before Temporal's 50k-event cap. `import korchestrator.runtime` pulls in no `temporalio`;
  it is loaded only when the Temporal runtime is selected. Produces a `RunResult` equivalent to the
  local runtime's.
- Durable HITL control signals on the Temporal runtime: `cancel` ends a run as `cancelled`; `pause`
  parks it (status `governance_paused`, no compute) until `resume` or `cancel`, bounded by a 24-hour
  deadline after which it is `timed_out`. Delivered via `IDurableRuntime.signal`. (`edit_resume`
  arrives with the HITL façade in a later phase; the local runtime is synchronous and has no HITL.)
- The deterministic offline `MockLM` gateway (`korchestrator.providers.MockLM`) — the default
  `IModelGateway`. The same messages always yield the same completion; it supports scripted
  per-model responses and records a call log. No network, no randomness, no credentials — it is what
  makes the full agent path testable in CI, and it is the zero-config default.
- The networked default `IModelGateway`, `korchestrator.providers.OpenAIGateway` — a thin client for
  any OpenAI-compatible chat-completions endpoint. All configuration (endpoint, credentials, timeout)
  is injected (the gateway reads no environment), `httpx` is lazily imported and lives behind the
  `[remote]` extra (the base install stays `pydantic`-only), and every vendor failure is wrapped as a
  `KorchError`: a timeout → `TimeoutError`, 401/403 → `AuthError`, 429 → `RateLimitError`, anything
  else → `ProviderError` — always preserving `__cause__`. Prompts and credentials are never logged.
- `korchestrator.providers.get_lm(model_name, *, settings=..., api_key=..., base_url=...)` — the
  gateway factory: returns the offline `MockLM` when `settings.mock_llm` (the zero-config default),
  otherwise a configured `OpenAIGateway`; a real gateway without injected credentials raises an
  actionable `ConfigurationError`.
- The default local ARI providers (`korchestrator.providers`): `LocalIdentityProvider` — an
  unsecured, single-tenant `IIdentityProvider` that resolves an agent to a deterministic synthetic
  DID and enforces its bound tenant; and `LocalSandbox` — a subprocess-isolating `IExecutionSandbox`
  that runs a registered tool command in a child process under a hard, kill-on-expiry timeout and
  returns a normalised `ToolResult`. Both are zero-infrastructure development fallbacks: each logs a
  warning on construction and is rejected by the production-boot gate under a durable deployment
  (spec 08 §5); enterprise deployments supply KIAM/KACP and OpenSandbox. The sandbox tool registry
  is empty until the Agent Utility Bridge (P6) populates it.

- **First end-to-end run.** `Korch.run(objective)` and `Swarm.run()` are wired to the kernel: the
  façade classifies the objective (taxonomy), has the Architect plan a team (Tier 1) or takes the
  declared topology (Tier 2), binds each agent's clock and gateway, builds a validated kernel graph,
  and drives it through the configured runtime to a `RunResult` with a populated `final_answer`. The
  Tier-1 one-liner and Tier-2 typed-swarm examples from the public API now run (their tests are no
  longer `xfail`). Reasoning agents require `[dspy]`; a custom agent (own `think`) runs the whole path
  on a pydantic-only base install. A worker's contribution is emitted as an `answer` message so it
  accumulates into `final_answer`.
- The deterministic **taxonomy** (`korchestrator.taxonomy`): `TaxonomyClassifier.classify(objective)`
  maps an objective to a typed `TaskSemantics` (intent, difficulty, implied capability, token
  estimates) using keyword/length heuristics — no model call, no extra, fully reproducible. Plus the
  built-in agent-descriptor catalogue (`default_descriptors()`, `descriptors_for_intent(intent)`) that
  the Architect and router use to match intents to agents.
- `korchestrator.agents.ArchitectAgent` — the Architect meta-agent (requires `[dspy]`). Given an
  objective (and its classified intent/difficulty) it reasons a small team of agent roles and returns
  a validated `ExecutionPlan`. On any reasoning failure — a provider error, or a reply that yields no
  valid agent role (as a MockLM echo does) — it returns a deterministic single-agent **mock plan**, so
  a swarm always gets a runnable plan; `MissingExtraError` still propagates (it does not trigger the
  fallback). The DSPy↔gateway bridge is now shared by the worker and architect.
- `korchestrator.agents.WorkerAgent` — the default reasoning agent (requires the `[dspy]` extra;
  ADR 0013). It compiles its `Signature` into a `dspy.Predict` at call time and runs it under the
  **injected** `IModelGateway`: a `dspy.LM` subclass routes DSPy's model calls to
  `IModelGateway.complete` (so heterogeneous per-agent models and the offline MockLM both work), and a
  lenient chat adapter falls back to the first output field when a reply is not field-marked (so a
  deterministic MockLM echo still parses). The blocking DSPy call runs in a worker thread
  (`asyncio.to_thread`); a base install raises an actionable `MissingExtraError` when reasoning runs.
  `Agent.bind` now also accepts an optional `gateway` the composition root injects.
- Lazy DSPy **signatures** (`korchestrator.agents`): a `Signature` base with `InputField` /
  `OutputField` markers that declare a reasoning contract **without importing `dspy`**, plus the
  built-in `WorkerSignature` and `ArchitectSignature`. `Signature.to_dspy()` materialises a real
  `dspy.Signature` on demand — the only point that requires the `[dspy]` extra, raising an actionable
  `MissingExtraError` when it is absent. So `import korchestrator.agents` stays `pydantic`-only and
  the cognitive layer is authored offline; the worker compiles the signature at call time.
- The unified `Agent` base (`korchestrator.agents.Agent`, re-exported as `korchestrator.Agent` and
  `korchestrator.services.Agent`): one class that is both the declarative Tier-2 builder
  (`Agent(id="lead", role="review-lead")`, unchanged) and the subclassable Tier-3 base with the
  frozen-snapshot behavioural surface — `async think(state) -> StateUpdate`, `is_complete(state)`,
  `bind(clock=...)`, `clock` (`clock.now()`), and `to_node()`. `think` receives an immutable
  `AgentState` and returns a `StateUpdate` delta; the base implementation raises until a subclass
  overrides it or the façade supplies the default reasoning agent. See ADR 0012.

### Changed

- **`Agent` is now defined in `korchestrator.agents`** (its canonical home) and re-exported from
  `korchestrator.services` and the top level — all three import paths resolve to the same class
  (ADR 0012). The Tier-2 declarative constructor is unchanged, so this is additive and non-breaking;
  the new behavioural methods make custom agents (subclass + `think`) possible.
- **Breaking (0.x).** `IDurableRuntime` is reshaped from a single `run(state)` method to
  `now()` / `start(state)` / `wait(run_id)` / `signal(run_id, name, payload)` (spec 06 §6), so it can
  express durable start-then-rejoin and carry HITL control signals. The graph is injected into the
  concrete runtime at construction rather than passed to `start()`, keeping `interfaces/` dependent
  on `models/` only. This lands before any release and before any implementation existed, so no
  consumer is affected. See [ADR 0010](docs/adr/0010-idurableruntime-shape-now-start-wait-signal.md).

[0.1.0]: https://github.com/kendralabs/korch-sdk/releases/tag/v0.1.0
