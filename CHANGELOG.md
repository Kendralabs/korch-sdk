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

### Changed

- **Breaking (0.x).** `IDurableRuntime` is reshaped from a single `run(state)` method to
  `now()` / `start(state)` / `wait(run_id)` / `signal(run_id, name, payload)` (spec 06 §6), so it can
  express durable start-then-rejoin and carry HITL control signals. The graph is injected into the
  concrete runtime at construction rather than passed to `start()`, keeping `interfaces/` dependent
  on `models/` only. This lands before any release and before any implementation existed, so no
  consumer is affected. See [ADR 0010](docs/adr/0010-idurableruntime-shape-now-start-wait-signal.md).

[0.1.0]: https://github.com/kendralabs/korch-sdk/releases/tag/v0.1.0
