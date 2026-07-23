# What Has Been Built

Every completed phase, in plain words. Each phase is a group of related features. "Green" means all
checks pass: linting (ruff), types (mypy --strict), tests (pytest + coverage), architecture rules
(import-linter), and the import-isolation gate.

---

## P0 — Foundations & scaffolding ✅

The skeleton and rules everything else is built on.

- Created the whole package layout (`src/korchestrator/…`) with one folder per concern; each folder
  states which layer it is and what it may import.
- Set up `pyproject.toml`: the base install needs **only `pydantic`**; heavy libraries live behind
  optional extras (`[dspy]`, `[temporal]`, `[routing]`, `[mcp]`, `[remote]`, `[otel]`).
- Pinned the version in one place (`version.py` = `0.1.0`).
- Added the guardrails: a pre-commit hook, the import-isolation gate, and machine-checked
  architecture contracts (import-linter).

## P1 — Public API & interface contracts ✅

The promises the SDK makes to its users, and the typed data it passes around.

- Defined the **error family**: every error the SDK raises on purpose is a `KorchError` subclass
  (e.g. `ValidationError`, `AuthError`, `ProviderError`, `ToolError`), each with a stable code.
- Defined the **data models** (all frozen/immutable): `AgentState`, `Message`, `StateUpdate`,
  `RunResult`, `AgentConfig`, `ExecutionPlan`, `ModelCard`, `ToolResult`, and more.
- Defined the **interfaces (ports)** that let parts be swapped: `IModelGateway`,
  `IIdentityProvider`, `IExecutionSandbox`, `IDurableRuntime`, `GraphRepository`, `BaseRouter`,
  `AUBConnector`.
- Froze the **public surface** (`korchestrator.__all__`) and guarded it with a golden-file test so
  it can only change on purpose.
- Added the fluent builders: `Agent(...)`, `Swarm(...)`, `Korch(...)` (build the shape of a job).

## P2 — Core execution kernel (Pregel) ✅

The deterministic engine that actually runs the agents.

- Built the **reducers** (`LastValue`, `Append`, `UniqueAppend`, `MergeDict`) that merge each agent's
  results, and proved with property-based tests that order never changes the outcome.
- Built the **graph** (`AgentGraph`) and checked its topology (valid nodes and edges).
- Built the **superstep runner** (`PregelRunner`): every round, the active agents think in parallel
  against a frozen snapshot, then a barrier merges their results, routes messages, and decides
  whether to stop.
- Locked **determinism**: same input → same output, every run, with no wall-clock or randomness in
  the engine.

## P3 — Runtime adapters (local + Temporal) ✅

Two ways to drive the engine, behind one interface.

- **Local runtime**: runs everything in-process — the zero-setup default for dev and CI.
- **Temporal runtime** (`[temporal]` extra): runs durably so a job survives crashes and can replay;
  supports human-in-the-loop pause/resume signals.
- One `resolve_runtime(settings)` picks the right one from config.
- Tested that local and Temporal produce the **same result**, and that Temporal **replays
  deterministically**.

## P4 — Cognitive layer (agents, taxonomy) ✅ — first end-to-end run

The reasoning parts, and the first time a full job runs start to finish.

- **Providers**: `MockLM` (offline, deterministic — the default), a local identity provider, a
  subprocess sandbox, and a real OpenAI-style gateway; `get_lm(...)` picks mock vs real.
- **Agents**: one unified `Agent` class (declarative *and* subclassable); `WorkerAgent` (does the
  reasoning via DSPy); `ArchitectAgent` (plans a team of agents for a goal).
- **Taxonomy**: `TaxonomyClassifier` reads a goal and labels its intent and difficulty (offline,
  deterministic).
- **Milestone**: `Korch().run("…")` and `Swarm(…).run()` now actually execute — classify → plan →
  run supersteps → return a `RunResult` with a `final_answer`.
- A custom agent runs the whole path on the base install; reasoning agents need the `[dspy]` extra.

## P5 — Model routing ✅ (merged & pushed)

Choosing which model each agent uses.

- One `BaseRouter` with several strategies:
  - **Explicit + fallback** (the default): use a pinned model or an `AGENT_MODEL_MAP` entry, else a
    safe default. Works with no extra installed.
  - **Algorithmic**: rank candidate models by a weighted mix of quality, cost, and latency.
  - **Semantic** (`[routing]` extra): pick the model whose description best matches the task.
  - **Composite** and **user-supplied function** routers.
- `get_router(settings)` / `resolve_router(...)` build the router; a custom router plugs in by
  injection (`Korch(router=…)`) with no package edit.
- A built-in **model-card catalogue** (cost/latency/quality per model).
- Routing runs once per agent at setup time, so it stays deterministic and replay-safe.

## P6 — Integration & observability ✅ (merged & pushed)

Tools, external tool servers, memory shaping, agent-to-agent messages, live events, and plug-in
points.

- **Tools (AUB)**: `invoke_tool(...)` is the single, safe path for every tool call — it checks the
  agent is allowed to use the tool, validates arguments, applies a timeout and rate limit, leaves a
  spot for redaction, and returns a normalized `ToolResult`. `ConnectorRegistry` holds the tools;
  built-in `FilesystemConnector` (blocks path traversal) and `MockSearchConnector` (offline).
- **MCP client** (`[mcp]` extra): connects to an external MCP tool server, discovers its tools, and
  exposes them as normal connectors — agents can't tell an MCP tool from a native one.
- **Context compiler**: builds a "Minimum Viable Context" — keeps the important messages, drops the
  rest to fit a budget, with optional summarization. Runs off the hot path.
- **A2A messaging**: `directed_message(...)` and a `HandoffTransformer` for one agent handing work to
  another.
- **Event streaming**: `EventPublisher` emits events a caller can subscribe to (and turn into
  Server-Sent Events); the SDK emits, it never serves HTTP itself.
- **Middleware & hooks**: `Middleware` and `HookRegistry` let you observe each superstep and events,
  in a documented order, and a failing hook can never crash a run. Wired into the local runtime via
  a `SuperstepObserver` seam (off by default, so determinism is untouched).

## P7 — Governance, security & context graph ✅

Zero-trust guardrails and long-term memory.

- ✅ **P7.1 — Shield (PII/secret redactor)**: one consolidated `Shield` that masks sensitive data to
  `[MASKED_<TYPE>]` — emails, secrets (JWTs, AWS/`sk-`/Slack/Bearer tokens), IBANs, SSNs, real card
  numbers (checked with the Luhn formula), and phone numbers. Walks JSON too. A "high sensitivity"
  mode masks anything that looks risky. This was built first because the rest of governance depends
  on it.
- ✅ **P7.2 — Trust scoring**: the kernel's barrier folds each agent's `trust_delta` into
  `AgentState.trust_score` every superstep, clamped to `[0, 1]`. `governance.check_governance` is
  the read-only, governance-facing view of the score plus its per-superstep telemetry.
- ✅ **P7.3 — Policy engine + audit log**: `evaluate_policy(...)` compares the trust score against an
  agent's own `hitl_threshold`, falling back to `GOVERNANCE_TRUST_THRESHOLD` (default `0.5`), and
  decides allow/intervene. `AuditLog` keeps an append-only record of decisions and their telemetry.
- ✅ **P7.4 — Human-in-the-loop controls**: the Temporal runtime now auto-pauses a run when trust
  drops below threshold — the same mechanism an operator's own `pause` signal uses. A new
  `edit_resume` signal lets an operator patch context/trust and resume; `Korch`/`Swarm` expose
  `pause`/`resume`/`cancel`/`edit_resume`, all backed by durable Temporal signals.
- ✅ **P7.5 — In-memory graph repository**: `InMemoryGraphRepository` is the default, zero-setup
  backend (`PERSISTENCE_BACKEND=memory`); `none` runs fully standalone. `Korch`/`Swarm` now actually
  checkpoint state to it after each superstep.
- ✅ **P7.6 — Bitemporal Context Graph client**: `ContextGraphClient` records decisions and events —
  each carrying valid-time, transaction-time, confidence, and provenance — through Shield redaction
  first, and queries them back tenant-scoped with time-travel (`as_of`/`valid_at`). Nodes are
  immutable and append-only: a correction is always a new node, never an edit.

## P8 — Cross-cutting foundations ✅

Finalized the seven foundations every module depends on (spec 08).

- ✅ **P8.1 — Settings finalized**: the full spec 08 §1.3 variable table (28 fields), secret fields
  as `pydantic.SecretStr`. New `korchestrator.configure(**overrides)` builds, validates, and installs
  a process-wide `Settings` (reads `.env` from the CWD by default); `get_settings()` returns it,
  building the zero-config default lazily. Resolved the long-flagged `ConfigurationError` vs
  `ValidationError` overlap (ADR 0016): `ValidationError` is structural (what `configure()` raises
  on a bad value), `ConfigurationError` is a resolution/support failure, and it stays submodule-only.
- ✅ **P8.2 — Config isolation test**: a test that fails the build if `os.environ`/`os.getenv`/
  `.env` reading ever escapes `config/`.
- ✅ **P8.3 — Logging**: `logging/` — one namespaced `korchestrator` logger, a `NullHandler` by
  default (never touches the root logger, never calls `basicConfig()`), `enable_logging(level=
  "INFO", stream=None)` / `disable_logging()`.
- ✅ **P8.4 — Exception audit**: swept every third-party/I/O boundary; found and fixed the one real
  gap — the Temporal client boundary (`start`/`wait`/`signal`) could leak a raw `temporalio`
  exception — now wrapped into `RunFailedError`/`NetworkError`/`ProviderError`.
- ✅ **P8.5 — Serialization**: `serializers/` — `to_json`/`from_json` round-trip `AgentState`,
  `ExecutionPlan`, `ModelCard`, `RunResult` byte-for-byte (sorted keys, fixed separators, UTF-8),
  every envelope version-tagged with a migration mechanism. `AgentGraph` is deliberately excluded —
  its nodes carry live, non-serializable compute callables (ADR 0017).
- ✅ **P8.6 — Validation**: `validators/` — the trust-boundary rules Pydantic can't express
  (`validate_objective`, `validate_max_supersteps`, `validate_unique_agent_id`). Auditing spec 08
  §7's full boundary table surfaced two real, previously-silent gaps, both fixed: `max_supersteps`
  was never checked against its documented 1–100 bound, and adding a duplicate agent id to a
  `Swarm` silently overwrote the earlier one instead of raising.
- ✅ **P8.7 — Telemetry**: `telemetry/` — optional OpenTelemetry `start_span`/`record_metric`,
  behind `KORCH_TELEMETRY_ENABLED` (default off) and the `[otel]` extra. Disabled, `start_span`
  returns the same no-op singleton every call — no allocation, no OTel import. Wired the outer
  `agent.run` span and the `korch.run.duration`/`korch.run.status` metrics into the composition
  root; the rest of the documented span tree and the remaining four metrics are defined (correct
  OTel instrument kind per name) but not yet wired into the kernel/tool/gateway call sites.

---

## Decisions recorded along the way (ADRs)

Short "why we chose this" notes live in `docs/adr/`. The most recent:

- **0011** — `httpx` is confined to the HTTP-facing modules only (machine-enforced).
- **0012** — one unified `Agent` class (declarative and subclassable).
- **0013** — reasoning needs the `[dspy]` extra; target DSPy 3.x.
- **0014** — custom routers plug in by injection; no global registry.
- **0015** — tools/connectors register on a registry + `Korch(connectors=…)`; no global.
- **0016** — no `pydantic-settings`; `configure()` raises `ValidationError`, `ConfigurationError`
  covers resolution failures and stays submodule-only.
- **0017** — `AgentGraph` is excluded from `to_json`/`from_json` (live compute callables).

## How to verify everything is green

```bash
ruff check src/korchestrator tests
ruff format --check src/korchestrator tests
mypy --strict src/korchestrator
pytest tests -m "not temporal" --cov=korchestrator --cov-report=term-missing
lint-imports        # architecture contracts (4 kept, 0 broken)
```

Note: `temporal`-marked tests need a running Temporal server, so they are excluded from the normal
run. Everything else passes with the base install plus dev extras.
