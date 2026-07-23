# ADR 0018 — `WorkerAgent` gets a bounded ReAct loop via a new `IToolInvoker` port

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** SDK maintainers
- **Phase:** P10.2 (retroactively completes P4.6 / P6)
- **Supersedes / Superseded by:** None. Extends the `IModelGateway` injection pattern (spec 03) and
  ADR 0015 (tool registration) to reasoning agents.

## Context

Writing P10.2's tool-calling integration suite surfaced that `WorkerAgent` never called
`invoke_tool`. `AgentConfig.tools` and `AgentConfig.max_react_steps` existed as typed fields with
zero runtime effect: `WorkerAgent._reason` always ran a single `WorkerSignature` predict and
returned one `answer` message, regardless of what `tools` held. No ReAct tool-calling loop existed,
despite spec 12's P4.6 task explicitly requiring "TypedPredictor + bounded ReAct loop (≤3)" and
despite both P4 and P6 being marked complete in `PROJECT_STATE.md`. This is a retroactive gap fix,
not new P10 scope — P10.2 just wrote the first test that exercised the path.

`agents/`'s allowed imports (spec 05) are `core`, `interfaces`, `models`, `exceptions`, `logging`,
`dspy` (lazy) — explicitly not `tools/`, even though `tools/` owns the real Agent Utility Bridge
(`invoke_tool`, `ConnectorRegistry`). A worker cannot import `tools/` directly without violating
architecture boundary B2/B3-equivalent layering (spec 05's per-module import table) and rule
`architecture-boundaries.md`'s dependency rule (`services → agents → core → interfaces/models`).

## Decision

Mirror the existing `IModelGateway` pattern exactly:

- A new ARI-style port, `IToolInvoker`, in `interfaces/tool_invoker.py` — `invoke_tool(tool, args,
  *, tenant_id, mounted) -> ToolResult` and a synchronous `describe_tool(tool) -> str`. This is the
  smallest surface a reasoning agent needs; it does not expose the registry, mounting, rate
  limiting, or redaction machinery.
- One implementation, `RegistryToolInvoker` in `tools/bridge.py`, binding a `ConnectorRegistry` and
  delegating to `invoke_tool` — the mount gate, schema validation, timeout, rate limiting, and
  redaction all still apply unchanged.
- `Agent.bind()` gains an optional `tool_invoker: IToolInvoker | None` parameter, stored alongside
  the existing `gateway`.
- `WorkerAgent._reason` branches: no `tools` configured runs the original single-predict path
  unchanged (`_reason_single`); `tools` non-empty runs a new bounded loop (`_reason_with_tools`)
  against a new `ReActWorkerSignature` (adds `available_tools` input and `thought`/`tool_name`/
  `tool_args` outputs alongside the existing `answer`/`is_final`). The loop runs up to
  `max_react_steps` times, feeding each tool's formatted result back into the next step's context,
  and raises `ConfigurationError` if `tools` is non-empty but no invoker was bound.
- `Korch`/`Swarm` gain a `connectors: Sequence[Connector] | ConnectorRegistry | None = None`
  constructor parameter (mirroring `model_gateway`). `services/_composition.py` resolves it to a
  `RegistryToolInvoker` (or `None` if `connectors` was never passed) and threads it through
  `graph_from_configs`/`graph_from_agents` into every agent's `bind()` call — the composition root
  is the only place a `ConnectorRegistry` is constructed, per ADR 0015.

### Kernel fix required alongside this

`PregelRunner._route_messages` previously accumulated only `kind == "answer"` messages into the
run's message log (`AgentState.messages` / `RunResult.messages`); every other `Message.kind` value
(`"thought"`, `"tool"`, `"handoff"`) was routed to inboxes but dropped from the log. This was
invisible before P10.2 because every existing `StateUpdate` carried exactly one message, always of
kind `"answer"`. A ReAct step now emits `"tool"` messages ahead of its final `"answer"` message in
the same `StateUpdate`, and `Message.kind`'s own type (`Literal["thought", "tool", "answer",
"handoff"]`) already anticipated a log holding more than answers. `_route_messages` now accumulates
every message into the log; `build_result`'s `final_answer` is unaffected — it already filters the
log down to `kind == "answer"` before joining.

## Alternatives considered

- **Let `agents/` import `tools/` directly.** Rejected: violates spec 05's per-module allowed-
  imports table and the inward-only dependency rule; would also make `agents/` depend on `dspy`-
  unrelated heavy machinery (rate limiters, redactors) it has no reason to construct.
- **Have the composition root pass a raw `ConnectorRegistry` into `WorkerAgent`.** Rejected: same
  boundary violation one layer later, and it would let a worker bypass `invoke_tool`'s mount gate
  and redaction by calling the registry's connectors directly.
- **Widen `state.messages` only for `kind == "tool"` instead of every kind.** Rejected: singles out
  one kind for no principled reason; `Message.kind` already models four kinds, and the log should
  hold the full record, not a second answer-only projection (that projection already exists, in
  `build_result.final_answer`).

## Consequences

- **Positive.** `AgentConfig.tools` and `max_react_steps` now do what spec 12 P4.6 always specified.
  The port mirrors `IModelGateway`, so the injection idiom stays uniform. `RunResult.messages` now
  carries the full reasoning trace (thought/tool/answer), which P10.2's integration and future E2E
  suites depend on to assert tool calls actually happened.
- **Negative.** `RunResult.messages` is larger for any run using tools — callers that assumed one
  message per agent per superstep must filter by `kind` (existing tests already did, via
  `m.kind == "answer"`, so no regression).
- **Rollback.** Additive and reversible: dropping `IToolInvoker`/`RegistryToolInvoker` and reverting
  `_route_messages` to filter on `kind == "answer"` would return to the P4-era single-shot-only
  behavior with no data migration involved (no persisted state format changed).
