# ADR 0010 — `IDurableRuntime` shape: `now`/`start`/`wait`/`signal`

- **Status:** Accepted
- **Date:** 2026-07-22
- **Deciders:** SDK maintainers
- **Phase:** P3
- **Supersedes / Superseded by:** Amends the `IDurableRuntime` protocol frozen in P1.4; realises the
  authoritative contract in spec 06 §6 while preserving the layering rule.

## Context

P1.4 froze `IDurableRuntime` with a single method, `async run(state) -> RunResult`. That was the
minimal shape the local runtime needs, and the P1.4 log flagged the minimal protocol shapes as the
ones most likely to be revisited with an ADR when their implementations land.

Phase 3 is that moment. The authoritative execution model (spec 06 §6) defines `IDurableRuntime`
with four methods — `now()`, `start()`, `wait()`, and `signal()` — and P3 needs all of them:

- **`now()`** gives the runtime's replay-safe clock (`workflow.now()` under Temporal), which the
  `PregelRunner` already consumes as an injected `Clock`.
- **`start()` + `wait()`** are the durable async pattern: `start` begins a run and returns its
  `run_id` without blocking; `wait` blocks until a terminal or paused state. A single blocking
  `run()` cannot express "begin a durable workflow, then rejoin it later", which is the whole point
  of the Temporal adapter (P3.3).
- **`signal()`** delivers the durable HITL control signals (`resume`, `cancel`, `edit_resume`) that
  P3.5 requires. There is nowhere to put them under a single `run()`.

Spec 06 §6 additionally writes `start(graph: AgentGraph, state, ...)`. Taken literally, that imports
`korchestrator.core.AgentGraph` into `korchestrator.interfaces`, which the import-linter `layers`
contract forbids (a lower layer importing a higher one — see ADR-adjacent note in the P1.3/P1.4 log
and `.importlinter`). The P1.4 protocol already resolved this by supplying the graph to the concrete
runtime **at construction**, so the method signature depends on `models` alone.

## Decision

**Amend `IDurableRuntime` to the four-method shape, with the graph injected at construction rather
than passed to `start()`:**

```python
class IDurableRuntime(Protocol):
    def now(self) -> datetime: ...
    async def start(self, state: AgentState, *, max_supersteps: int = 10) -> str: ...   # run_id
    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult: ...
    async def signal(self, run_id: str, name: str, payload: Mapping[str, str]) -> None: ...
```

- The concrete runtime is constructed with what it needs to run — the `AgentGraph` (or a
  `PregelRunner`), the clock, and the channel schema. `runtime/` is an adapter layer and **may**
  import `core`, so this keeps the graph out of `interfaces/` and the layers contract green.
- `start()` returns the `run_id` immediately (the local runtime runs to completion synchronously and
  stores the result; the Temporal runtime starts a workflow); `wait()` returns the `RunResult`.
- `signal()` carries the HITL control signals. The local runtime implements it in P3.5; until then it
  raises an actionable error.
- The façade's `Korch.run()` composes `start()` + `wait()`.

This is the two-method-becomes-four amendment the P1.4 log anticipated, driven by the authoritative
spec 06 §6, not by churn.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Keep P1.4 `run(state)`; bolt signals on elsewhere | `run()` cannot express start-then-rejoin (durable workflows) or carry HITL signals. Would force a second, separate control interface — two protocols for one seam, and a worse fit for Temporal. |
| Follow spec 06 §6 literally with `start(graph, state)` | Imports `core.AgentGraph` into `interfaces/`, breaking the import-linter `layers` contract (a hard, enforced rule). The graph-at-construction form is the same contract with the layering preserved. |
| Add `run()` as a convenience alongside `start`/`wait` | Redundant surface; the façade composes `start`+`wait` in one place. Keeping the protocol minimal (spec 06 §6 has no `run()`) is the better contract. |

## Consequences

**Positive**
- The runtime contract matches the authoritative execution model and supports durable execution and
  HITL without a second interface.
- Layering stays clean: `interfaces/` depends on `models/` only; the graph lives in `runtime/`
  constructors, which legally import `core/`.

**Negative**
- This is a change to a documented protocol (compatibility surface). It is a **breaking change**, but
  it lands during `0.x` **before any release and before any implementation existed**, so no consumer
  is affected. It ships with a CHANGELOG note under `### Changed`.
- `signal()` is part of the surface from P3.1 but only fully implemented in P3.5; the local runtime
  raises an actionable error for it until then.

**Neutral**
- The `interfaces/test_protocols.py` conformance fake is updated to the new shape; the top-level
  `__all__` is unaffected (`IDurableRuntime` is exported via `korchestrator.interfaces`, not the
  top-level surface).

## Rollback

Reversible while `0.x`. If the four-method shape proves wrong, a superseding ADR reverts it; because
no release shipped the P1.4 shape, there is no external contract to honour. Concrete runtimes and the
façade composition are the only in-repo consumers and move together.
