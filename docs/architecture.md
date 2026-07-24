# Architecture

How Korchestrator is put together, and why — for anyone embedding it, extending it, or just
wanting to understand what "durable, deterministic, multi-agent execution" actually means
mechanically.

## The execution model: Pregel BSP

A swarm run proceeds as a sequence of **supersteps**. In each superstep:

1. Every *active* agent computes against the same frozen snapshot of shared state, in parallel.
2. A barrier waits for all of them, then merges their results through order-independent reducers.
3. Messages route to their targets' inboxes for the next superstep.
4. The run halts once every agent has halted, or `max_supersteps` is reached.

This is the [Pregel](https://kowshik.github.io/JPregel/pregel_paper.pdf) model — the same one
large-scale graph-processing systems use — applied to agent reasoning instead of graph algorithms.
It buys two properties ad-hoc agent loops don't have:

- **Real parallelism.** N agents active in one superstep genuinely run concurrently, not
  round-robin. See `benchmarks/bench_superstep.py` in the repository for the measured proof.
- **Determinism.** No agent ever observes another's still-in-progress work — every agent computes
  against the *same, frozen* snapshot. Combined with reducers that are associative and
  order-independent (merging never depends on which agent happened to finish first), the same
  graph and the same inputs produce the same result, every time, including across a crash and
  replay.

## Two runtimes, one contract

The kernel that runs the supersteps (`PregelRunner`) is the same either way. What differs is what
drives it:

- **Local runtime** (the default) — in-process, synchronous from the caller's point of view. Zero
  infrastructure; the right choice for development, CI, and short-lived runs.
- **Temporal runtime** (`[temporal]` extra) — every superstep is checkpointed durably. A crash
  resumes from the last barrier instead of losing the run, and a run can be paused for human
  review and resumed later (see the [HITL tutorial](tutorials/hitl.md)).

Switching between them is one setting (`KORCH_RUNTIME=local` or `temporal`) — no code change,
because both implement the same `IDurableRuntime` port.

## The layers

Dependencies point **inward only** — never outward, never sideways:

```
services/    FAÇADE — Korch, Swarm, Agent. The only place collaborators are wired together.
   ↓
agents/      COGNITIVE — reasoning, DSPy-compiled signatures, the worker and architect agents.
   ↓
core/        KERNEL — the Pregel runner, the graph, the reducers. Framework-free: imports only
             interfaces/, models/, stdlib, and pydantic. No FastAPI, no Temporal, no DSPy.
   ↓
interfaces/  models/    THE CONTRACTS — ports, protocols, typed data. Depend on nothing but
                         pydantic and the standard library.
```

Alongside that stack, **feature modules** (`routing`, `tools`, `mcp`, `a2a`, `governance`,
`persistence`, `context`, `events`) each depend inward on `interfaces/`/`models/` only — never on
each other. If two features need to share something, it lives in `interfaces/` or `models/`, not
in one feature importing the other.

Why this matters as a user, not just as a contributor: it's what makes the kernel embeddable. The
deterministic core has exactly one runtime dependency (`pydantic`), so it can run inside a
Temporal workflow sandbox, a notebook, a Lambda, or your own framework's process without dragging
along DSPy, an HTTP stack, or anything else your application doesn't already need.

## The ARI ports

Three interfaces give the SDK a portable seam between "runs entirely locally" and "backed by
managed infrastructure" — without an agent's code ever needing to know which side it's on:

- **`IModelGateway`** — how a completion request reaches a model. `MockLM` (deterministic,
  offline) locally; a real gateway in production.
- **`IDurableRuntime`** — how a run executes. The local or Temporal runtime, as above.
- **`IExecutionSandbox`** — how a tool call actually runs. A local subprocess sandbox by default.

A fourth port, `IIdentityProvider`, resolves an agent's identity and tenant. All four are documented
in the [API reference](reference/interfaces.md).

## Frozen snapshots, not shared mutable state

An agent's `think(state)` receives an **immutable** `AgentState` and returns a `StateUpdate`
describing what changed — it never mutates shared state directly (the model is frozen; attempting
to raises). This is the mechanism, not just the policy, behind "concurrency cannot change the
result": there is no shared mutable object for two concurrently-running agents to race on.

## Bitemporality

Every message and state update carries two timestamps, not one:

- **Valid time** — when the fact was true in the world, set by the emitting agent from the
  injected, replay-safe clock.
- **Transaction time** — when the kernel actually recorded it, stamped once per barrier.

Together they answer "what did the agent know at the moment it decided?" independently of any
later correction — the basis for the SDK's audit trail.

## Next

- [API Reference — Interfaces](reference/interfaces.md) for the exact port signatures.
- [Versioning](versioning.md) for what's covered by the compatibility promise these boundaries
  protect.
