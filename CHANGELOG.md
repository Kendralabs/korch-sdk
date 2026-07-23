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

- Remote client SSE streaming (Phase 9): `KorchestratorClient.stream(run_id)` (spec 04 §7.3/§7.5)
  — a native async iterator yielding `korchestrator.models.remote.RunEvent`, the only method on
  the client that isn't a sync wrapper. Reconnects automatically (full-jitter backoff, budget
  reset on each successful reconnect) on a dropped connection; note that reconnecting resumes from
  "now", not the last delivered event — the wire format carries no event id to resume from.
- Remote client control + identity (Phase 9): `KorchestratorClient` gains `resume`, `cancel`,
  `edit_resume` (mirrors the local kernel's own `edit_resume` signal shape), `me`, `my_quota`,
  `my_runs`, and key management (`create_key`, `list_keys`, `revoke_key`) — spec 04 §7.3. New
  `korchestrator.models.remote.CallerIdentity`/`Quota`/`ApiKey`/`ApiKeySummary`. `ApiKey.key` (the
  secret, returned once at creation) is a `pydantic.SecretStr`, never a bare `str` — an accidental
  `repr`/log can't leak it; call `.get_secret_value()` to use it. `list_keys` never returns the
  secret at all.
- Remote client run lifecycle (Phase 9): `KorchestratorClient` gains `run`, `run_swarm`,
  `run_and_wait`, `get_run`, `wait`, `list_runs`, `get_run_summary` (spec 04 §7.3). Every numeric
  run status the engine can return is normalized to the `RunStatus` string vocabulary before
  validation (spec 04 §7.4). New `korchestrator.models.remote.RemoteRunResult`/`RunSummary` —
  the client's own wire-facing result shapes, distinct from the local kernel's `RunResult` (no
  nested `AgentState`). `wait`/`run_and_wait` poll; real-time SSE streaming lands in the next
  Phase 9 task. The wire-format details (field names, list-response shape) are the SDK's own
  documented assumption pending a full engine schema — see the P9.3 engineering-log entry.
- Remote client credential safety (Phase 9): `KorchestratorClient.__repr__` shows `base_url` only,
  never headers or the credential. Test-locked (spec 04 §7.2): the client's `repr`/`str`, and
  every error `KorchestratorClient` can raise (`ApiError`, `NetworkError`, `TimeoutError`), never
  contain the API key — including when a (misbehaving) engine response tries to echo the
  `Authorization` header back. A static check asserts `clients/` performs no file I/O at all, so
  "credentials are never written to disk" can't regress silently.
- Remote client transport + auth (Phase 9): `korchestrator.remote.KorchestratorClient` (also
  `korchestrator.clients.KorchestratorClient`) — the Tier 4 client's authenticated, retrying HTTP
  transport, behind the `[remote]` extra (spec 04 §7). One `Authorization: Bearer` header for
  both a static API key and a Keycloak/KIAM JWT; a 30s default timeout, overridable per call; up
  to 3 retries with full-jitter exponential backoff on `429`/`502`/`503`/`504` and connection
  failures, never on any other `4xx`. New `korchestrator.exceptions.ApiError` (`status`, `code`,
  `trace_id`) is raised for a terminal non-2xx response. This first remote-client task ships the
  transport only — `run`/`get_run`/`resume`/`stream`/etc. land in the following Phase 9 tasks, so
  `KorchestratorClient` is not yet usable end-to-end.
- Optional OpenTelemetry telemetry (Phase 8, **closes Phase 8**): `korchestrator.telemetry` gains
  `start_span(name, *, settings=None, **attributes)` and `record_metric(name, value, *, settings=
  None, **attributes)`, behind `KORCH_TELEMETRY_ENABLED` (default off) and the `[otel]` extra.
  Disabled — the default — `start_span` returns the same module-level no-op singleton on every
  call (no context manager allocation, no OTel import); `record_metric` returns immediately. Both
  take an explicit `settings` so a run's actual, injected `Settings` decides — not the disconnected
  `configure()`/`get_settings()` process singleton. Enabled without the `[otel]` extra installed,
  both raise an actionable `MissingExtraError`. `services._composition.run_graph` wires the outer
  `agent.run` span (`run_id`, `tenant_id`, `max_supersteps`, `status`, `supersteps` attributes) and
  the `korch.run.duration`/`korch.run.status` metrics; the rest of the documented span tree
  (`agent.superstep`/`agent.plan`/`tool.call`/`gen_ai.call`) and the remaining four metrics
  (`korch.superstep.duration`, `korch.agents.active`, `korch.tool.calls`, `korch.model.tokens`) are
  defined (correct OTel instrument kind — histogram, up/down counter, or counter — per name) but not
  yet wired into the kernel/tool/gateway call sites; a `benchmarks/` regression proving the
  telemetry-off path is within noise of an `[otel]`-uninstalled build is P10's job. Neither
  `start_span` nor `record_metric` joins top-level `korchestrator.__all__` (submodule-only, like
  `ConfigurationError` — not part of the documented public surface).
- Deterministic, version-tagged serialization (Phase 8): new top-level `korchestrator.to_json(model)`/
  `from_json(payload, model_cls)` round-trip `AgentState`, `ExecutionPlan`, `ModelCard`, and
  `RunResult` byte-for-byte — sorted keys at every nesting level, fixed separators, UTF-8,
  ISO-8601 timestamps with an explicit UTC offset and microsecond precision. Every envelope
  carries `schema_version` and `korchestrator_version`; `from_json` applies registered migrations
  in sequence and raises `ValidationError` if the payload's `schema_version` is newer than the
  installed package supports. `AgentGraph` is deliberately not supported — its nodes carry live,
  non-serialisable compute callables (see
  [ADR 0017](docs/adr/0017-agentgraph-excluded-from-json-serialization.md)).
- Namespaced, disable-able logging (Phase 8): `korchestrator.logging` gains `enable_logging(level=
  "INFO", *, stream=None)` (attaches a single `StreamHandler` to the `korchestrator` logger,
  idempotent) and `disable_logging()`. Off by default — only a `NullHandler` is attached at import
  time, so the SDK never touches the root logger or calls `logging.basicConfig()`, and an embedding
  application's own logging configuration is untouched. `enable_logging` joins top-level
  `korchestrator.__all__`; `disable_logging` stays submodule-only, matching spec 04 §6 exactly.
- Settings finalized (Phase 8): the full spec 08 §1.3 variable table — 16 new fields covering the
  model gateway, kernel/runtime bounds, logging/telemetry toggles, the remote engine client, and
  the Temporal runtime (`TEMPORAL_ADDRESS`, `TEMPORAL_API_KEY`, etc.). Secret-bearing fields
  (`kendra_gateway_api_key`, `korch_engine_api_key`, `temporal_api_key`) use `pydantic.SecretStr`
  and never appear in `repr`/`str`. `Settings.from_env()` gains opt-in `.env` file support
  (`dotenv_path=`, `None` by default — no ambient developer `.env` affects an unrelated
  `from_env()` call). `mock_llm`, under `from_env()` only, now defaults to `False` when a gateway
  key resolved. New top-level `korchestrator.configure(**overrides)` builds, validates, and
  installs a process-wide `Settings` (reading `.env` from the CWD by default), raising
  `korchestrator.ValidationError` on an invalid value; `korchestrator.config.get_settings()`
  returns the installed instance, building the zero-config default lazily on first call. See
  [ADR 0016](docs/adr/0016-settings-finalization-no-pydantic-settings-error-split.md) for why this
  didn't require adopting `pydantic-settings`, and the `ConfigurationError`/`ValidationError` rule.
- Bitemporal Context Graph client (Phase 7, **closes Phase 7**): `korchestrator.persistence` gains
  `ContextGraphClient` — `record_decision()`/`record_event()` write immutable, tenant-scoped
  `DecisionNode`/`EventNode`s (each carrying `valid_time`, `transaction_time`, `confidence`, and
  `provenance`) through Shield redaction first; `query()` reads them back tenant-scoped, with
  `as_of`/`valid_at` time-travel and an optional `run_id` filter. A correction is always a new node
  with a later `transaction_time` — nodes are never mutated (event sourcing). `GraphRepository`
  (the P1 protocol) gains `record_node()`/`query_nodes()` — the extension its own docstring
  anticipated — and `InMemoryGraphRepository` implements both.
- Graph repository (Phase 7): `korchestrator.persistence` gains `InMemoryGraphRepository` (the
  `GraphRepository` protocol's default, zero-infrastructure implementation, tenant-scoped and
  concurrency-safe) and `resolve_repository()` (the one place `PERSISTENCE_BACKEND` becomes a
  concrete repository, or `None` for `PERSISTENCE_BACKEND=none`'s fully standalone run).
  `Korch`/`Swarm` now actually consult their `repository` — a `_PersistenceMiddleware` checkpoints
  `AgentState` after every superstep, giving the local runtime (which has no built-in durability) a
  best-effort recovery point. `PERSISTENCE_BACKEND=kcg` (an external backend) raises an actionable
  `ConfigurationError`; external backends are post-1.0.
- HITL controls (Phase 7): the Temporal runtime's `PregelMaster` workflow now **auto-pauses itself**
  when a superstep's `trust_score` breaches any active node's effective HITL threshold — the same
  `governance_paused` mechanism an operator's own `pause` signal uses. A new `edit_resume` signal
  applies an operator's context/trust edit (last-value merge + the same clamped fold the barrier
  uses) and resumes; a `status` query lets a caller check for `governance_paused` without blocking.
  `Korch`/`Swarm` gain `pause(run_id)`/`resume(run_id)`/`cancel(run_id)`/`edit_resume(run_id, ...)` —
  thin façade methods that deliver a durable control signal, raising `NotImplementedError` on the
  synchronous local runtime (durable HITL needs `KORCH_RUNTIME=temporal`). `TemporalRuntime` can now
  be constructed signal-only (`graph=None`) to deliver a control signal without rebuilding the graph.
- Policy engine + audit log (Phase 7): `korchestrator.governance` gains `evaluate_policy()` —
  compares a superstep's trust score against an agent's own `hitl_threshold` (falling back to the
  new `GOVERNANCE_TRUST_THRESHOLD` setting, default `0.5`) and returns a `GovernanceDecision`
  (`GovernanceAction.ALLOW`/`INTERVENE`) — plus `AuditLog`/`AuditEntry`, an append-only in-memory
  trail of decisions and the telemetry each was based on. Pure and config-free; the runtime pause
  signal that acts on an `INTERVENE` verdict lands in the next Phase 7 commit.
- Trust scoring (Phase 7): the kernel barrier now folds each active agent's
  `StateUpdate.trust_delta` into `AgentState.trust_score` every superstep, clamped to `[0.0, 1.0]`
  — pure and order-independent, so the score is deterministic and replay-safe. `korchestrator.
  governance` gains `ControlTowerTelemetry` (a per-superstep governance snapshot),
  `derive_telemetry()`, and `check_governance()` — the governance-facing read of the score plus its
  telemetry. Threshold comparison, `hitl_threshold`/`GOVERNANCE_TRUST_THRESHOLD`, the policy engine,
  and the audit log land in the next Phase 7 commit; the runtime pause signal after that.
- Shield redactor (Phase 7): `korchestrator.security.Shield` — the single consolidated PII/secret
  redactor. `redact(text)`/`redact_value(json)` mask emails, secrets (JWT, AWS/`sk-`/Slack tokens,
  Bearer), IBANs, SSNs, Luhn-validated card numbers (PAN), and E.164 phone numbers to
  `[MASKED_<TYPE>]`, returning what changed. A `high_sensitivity` mode fails toward masking.
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

### Fixed

- **Validation (Phase 8):** `Swarm.add()` now rejects a duplicate agent `id` with a
  `ValidationError` instead of silently overwriting the earlier agent (the dict-keyed-by-id
  storage previously discarded it with no warning). `Korch.run`/`Swarm.run` now validate
  `max_supersteps` is between 1 and 100 (spec 08 §7) — previously any integer, including 0 or
  negative, was accepted with no check. New `korchestrator.validators` module
  (`validate_objective`/`validate_max_supersteps`/`validate_unique_agent_id`) centralizes these
  domain rules; `services/_composition.py`'s objective-length check now delegates to it instead of
  a local copy.
- **Exception audit (Phase 8):** `TemporalRuntime.start`/`wait`/`signal` (and, through them,
  `Korch`/`Swarm.pause`/`resume`/`cancel`/`edit_resume`) no longer let a raw `temporalio` exception
  cross the façade boundary. A lost/refused connection now raises `NetworkError`, the run's own
  failure raises `RunFailedError`, and any other Temporal-reported error raises `ProviderError` —
  all with `__cause__` set to the original exception. Also: `Settings.from_env()`'s `.env` reader
  now wraps an unreadable file into `ConfigurationError` instead of letting a raw `OSError` escape.

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
