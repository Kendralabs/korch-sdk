# ADR 0017 — `AgentGraph` is excluded from `to_json`/`from_json`

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** SDK maintainers
- **Phase:** P8
- **Supersedes / Superseded by:** —

## Context

Spec 08 §6 names five models for deterministic, version-tagged JSON round-trip: `AgentState`,
`AgentGraph`, `ExecutionPlan`, `ModelCard`, and `RunResult`. Building P8.5's `to_json`/`from_json`
against that literal list runs into a structural fact about `AgentGraph` (`core/graph.py`): each
of its `Node`s carries a live Python callable (`Node.compute: AgentCallable`) — the agent's
compute function, injected by the composition root (spec 03 §5). A callable has no JSON
representation and no safe deserialization path (reconstructing it would mean either pickling
code, which is a security liability the SDK's security rules explicitly rule out ("Model and tool
output is untrusted input... never `eval`'d"), or requiring the caller to re-supply the callables
out of band, which is not a round trip in the sense the other four models support).

This is also why the Temporal runtime never serializes the graph across the workflow boundary
(spec 06 §6.2, `runtime/temporal_runtime.py`): only `node_ids: tuple[str, ...]` — the topology,
not the callables — crosses into `PregelRequest`. The precedent already exists; P8.5 makes it
explicit and permanent rather than silently diverging from the spec's literal list.

## Decision

`korchestrator.to_json`/`from_json` support exactly four models: `AgentState`, `ExecutionPlan`,
`ModelCard`, and `RunResult`. `AgentGraph` is not registered and `to_json(graph)` raises
`ValidationError` naming the supported set. Nothing in the SDK needs full `AgentGraph` round-trip
today — the Temporal runtime's own graph-boundary crossing already works via `node_ids` alone, not
a serialized graph.

If a genuine need for durable graph *topology* (node ids, `AgentConfig`s, edges — no callables)
arises later, it is a new, explicitly-scoped model (e.g. a `GraphTopology` shape) and a new ADR,
not a retrofit of this one.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Serialize only the topology (`node_ids`, `AgentConfig`s, `Edge`s), dropping `compute` | The closest fit to "AgentGraph round-trips," but no current caller needs it (Temporal already gets topology via `PregelRequest.node_ids` directly), and inventing a new partial-`AgentGraph` shape now, ungrounded in a real requirement, is exactly the speculative abstraction `.claude/rules/architecture.md` warns against ("a demonstrated variability point, not an imagined future"). |
| Pickle/dill the compute callables | A real security liability (arbitrary code execution on load) that spec 08 §5's "never `eval`'d" output-sanitization rule effectively forbids for anything crossing a trust boundary; a serialized graph is exactly such a boundary once it leaves the process that defined the callables. |
| Require the caller to re-attach callables after `from_json` (a "shell" round trip) | Technically works, but is not what "round trip" means anywhere else in this spec section (`to_json(x) == to_json(from_json(to_json(x)))` with no manual patching step), so it would document a promise the API doesn't keep. |

## Consequences

**Positive**

- `to_json`/`from_json` keep an honest contract: everything registered actually round-trips
  byte-for-byte, with no silently-lossy special case.
- No new abstraction (`GraphTopology` or similar) is introduced without a real consumer.

**Negative**

- A user attempting `to_json(my_graph)` gets a `ValidationError` rather than the spec's literal
  promise — documented here and in the module docstring so it reads as a deliberate decision, not
  a bug.

**Neutral**

- If P9's remote client or a future persistence need ever requires durable graph topology, this
  ADR is the natural pointer to revisit — the rejected "topology-only" alternative above is the
  starting design.

## Compliance

- `tests/unit/serializers/test_codec.py` asserts `to_json` raises `ValidationError` naming
  `AgentGraph` when attempted, and that the four supported types round-trip byte-for-byte.
- The `serializers/codec.py` module docstring states the four-type scope and links this ADR.

## Rollback

Reversible. Adding `AgentGraph` (or a `GraphTopology` shape) later is an additive change to the
serializer's registry — no compatibility break to undo, since nothing currently depends on
`AgentGraph` being absent from it.
