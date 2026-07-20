# 06 — Execution Model

**Purpose:** Specify the Pregel BSP kernel — supersteps, activation, reducers, message routing, halting — and the durability layer that runs it locally or on Temporal with an equivalent result.
**Owner/status:** SDK maintainers · Normative · last reviewed 2026-07-20.

Read this when you touch `core/`, `runtime/`, or anything whose behaviour must survive a replay.

## Contents

1. [The superstep](#1-the-superstep)
2. [Activation and halting](#2-activation-and-halting)
3. [Reducers and the barrier](#3-reducers-and-the-barrier)
4. [Message routing](#4-message-routing)
5. [The determinism contract](#5-the-determinism-contract)
6. [`IDurableRuntime` and its two adapters](#6-idurableruntime-and-its-two-adapters)
7. [HITL, retries and roll-over](#7-hitl-retries-and-roll-over)
8. [Runtime equivalence](#8-runtime-equivalence)

Model definitions referenced here are authoritative in [05-modules-and-data-models.md](05-modules-and-data-models.md).

---

## 1. The superstep

A run is a sequence of **supersteps**. Each superstep has five phases in fixed order:

| # | Phase | What happens | Where it runs |
|---|---|---|---|
| 1 | **Plan** | The Architect agent (or a preset topology) produces the typed `AgentGraph`. Runs once at superstep 0 unless the plan is explicitly re-derived. | Activity |
| 2 | **Compute** | Every active node runs concurrently via `asyncio.gather` against a frozen `AgentState` snapshot and returns a `StateUpdate`. | Activity |
| 3 | **Synchronise** | The barrier waits for all compute tasks; no update is visible to any agent until all have completed. | Workflow |
| 4 | **Reduce** | Deltas are merged into the next `AgentState` by the channel reducers, in a deterministic order. | Workflow |
| 5 | **Checkpoint** | The new state is persisted durably so the run can resume after a crash. | Workflow / event history |

The state transition is:

```text
S(t+1) = f(S(t), M(t))
```

where `S(t)` is the frozen `AgentState` at superstep `t`, `M(t)` the set of `StateUpdate` deltas emitted during that superstep, and `f` the reducer-driven barrier merge. `f` MUST be a pure function of its two arguments: given the same `S(t)` and the same multiset `M(t)`, it MUST produce a byte-identical `S(t+1)`.

**Frozen-snapshot rule.** An agent receives an immutable `AgentState` and returns a `StateUpdate`. It MUST NOT mutate the state it was given, hold a reference to it past the compute phase, or observe another agent's output from the same superstep. This is what removes locks and races: within a superstep, agents are mutually invisible. A test MUST assert that mutating an agent's input state raises (`frozen=True`) and that no agent's `StateUpdate` can depend on a sibling's output within the same superstep.

## 2. Activation and halting

**Activation rules** (`core/pregel.py`):

- Superstep 0 activates **all** nodes in the graph.
- Superstep `n > 0` activates **only** nodes whose inbox is non-empty — that is, nodes that received at least one message routed along an inbound edge during superstep `n - 1`.
- A node that returned `halt=True` is never reactivated for the remainder of the run.
- Activation MUST be computed from state alone. It never consults wall-clock, ordering of `asyncio` completion, or external services.

**Halting conditions.** A run stops when the first of these holds, evaluated at the barrier:

| Condition | Resulting `RunStatus` |
|---|---|
| No node is active for the next superstep | `completed` |
| Every active node returned `halt=True`, so `AgentState.halted` is `True` | `completed` |
| `superstep + 1 > max_supersteps` (default `10`) | `completed`, with `error_code = "MAX_SUPERSTEPS_REACHED"` recorded in `RunResult.error` |
| Governance raised an intervention | `governance_paused` (resumable) |
| An activity exhausted its retry policy | `failed` |
| The run deadline elapsed | `timed_out` |
| A cancel signal was received | `cancelled` |

`max_supersteps` is a hard bound, not advice. It MUST be enforced by the kernel itself, so it holds identically on both runtimes and is not delegated to a timeout.

## 3. Reducers and the barrier

Shared state mutates **only** through typed reducer channels. A channel is a key in `AgentState.context` (or `messages`) bound to exactly one reducer. Four reducers are defined; there is no fifth without an ADR.

| Reducer | Behaviour | Associative | Commutative / order-independent | Idempotent |
|---|---|---|---|---|
| `LastValue` | Keep the value with the highest `(superstep, agent_id)` sort key | Yes | Yes — the key is a total order over the deltas, not arrival order | Yes |
| `Append` | Concatenate into a list channel in `agent_id` order | Yes | Yes — sorted by `agent_id`, not completion order | **No** (by design) |
| `UniqueAppend` | Append only values not already present, preserving first-seen position | Yes | Yes | Yes |
| `MergeDict` | Deep-merge mapping channels; conflicting leaves resolve by `LastValue` | Yes | Yes | Yes |

**Why the laws matter.** `asyncio.gather` does not guarantee completion order, and Temporal replays activity results from event history in a possibly different interleaving from the original execution. If a reducer were order-dependent, the same `M(t)` could produce two different `S(t+1)` — a replay would diverge from the original run and Temporal would raise a nondeterminism error. Associativity additionally lets the barrier fold deltas incrementally without changing the result.

The barrier MUST enforce the laws mechanically: it sorts deltas by `agent_id` (which is unique per node and validated against `^[a-z0-9][a-z0-9_-]{0,63}$`) before folding, so completion order can never leak into the result.

`tests/unit/test_reducers.py` MUST include property-based law checks: for each reducer, `fold(a, fold(b, c)) == fold(fold(a, b), c)`, `fold(perm(deltas)) == fold(deltas)` for every permutation of a small delta set, and `fold(d, d) == fold(d)` for the reducers marked idempotent. `Append` MUST have an explicit test asserting it is **not** idempotent, so nobody "fixes" it later.

```python
from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class Reducer(Protocol[T]):
    """Merges a channel's prior value with the deltas from one superstep."""

    def __call__(self, current: T, deltas: Sequence[T]) -> T:
        """Return the merged value. MUST be associative and order-independent."""
        ...
```

## 4. Message routing

- `AgentGraph` is a directed graph of `Node` (an `AgentConfig` plus its bound callable) and `Edge` (`(source_id, target_id)`). Cycles are legal and first-class — that is why the kernel is Pregel and not a DAG runner.
- A `StateUpdate.messages` entry with `recipient=None` is broadcast along **every** outbound edge of the emitting node. An entry with an explicit `recipient` is delivered only if `(sender, recipient)` is an edge in the graph; otherwise the barrier raises `ValidationError` with the offending pair in the message.
- Delivery is into `AgentState.inbox[target_id]`, appended in `(sender_id, message_index)` order. Inboxes are cleared at the start of each compute phase; a message is delivered exactly once, to the next superstep only.
- Messages with `kind == "answer"` additionally accumulate into `AgentState.messages` and form `RunResult.final_answer`.
- Graph validation happens once, before superstep 0: node ids unique, every edge endpoint resolvable, at least one node, no self-edge unless explicitly permitted by `AgentGraph(allow_self_edges=True)`.

## 5. The determinism contract

Workflow-path code is any code that executes inside the Temporal workflow sandbox: the barrier, reducers, activation, halting, checkpoint assembly, and the `PregelMaster` loop.

Workflow-path code MUST NOT:

- call `datetime.now()`, `datetime.utcnow()`, `time.time()`, or `time.monotonic()`;
- call `random`, `secrets`, `uuid.uuid4()`, or anything seeded from entropy;
- read environment variables, files, sockets, or any process-global mutable state;
- iterate an unordered collection (`set`, `dict` from an unstable source) in a way that affects the result;
- depend on `asyncio` task completion order.

Instead:

- Time comes from the runtime's injected clock — `IDurableRuntime.now()`, which is `workflow.now()` under Temporal and a monotone injected clock locally.
- Identifiers are derived: `Message.id` is `f"{run_id}:{superstep}:{sender}:{index}"`; run ids are supplied by the caller or generated **once**, in an activity, before the workflow starts.
- All nondeterminism — model calls, tool calls, HTTP, sandboxed code, embedding lookups — lives in **activities**, never in workflow scope.
- Behaviour changes to workflow-path code that would alter replay MUST be gated with Temporal's `patched()` / `deprecate_patch()` mechanism and recorded in an ADR.

A determinism test MUST assert that running the same graph, the same initial `AgentState`, and MockLM twice produces byte-identical serialised `RunResult`s.

## 6. `IDurableRuntime` and its two adapters

One port, two real implementations — which is exactly why the port exists ([07-extensibility.md](07-extensibility.md) §"when a port is justified").

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from korchestrator.core import AgentGraph
from korchestrator.models import AgentState, RunResult


@runtime_checkable
class IDurableRuntime(Protocol):
    """Executes a Pregel run and owns durability, timing and control signals."""

    def now(self) -> datetime:
        """Return the replay-safe current time. NEVER `datetime.now()`."""
        ...

    async def start(
        self, graph: AgentGraph, state: AgentState, *, max_supersteps: int = 10
    ) -> str:
        """Begin a run and return its stable `run_id` without waiting."""
        ...

    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult:
        """Block until the run reaches a terminal or paused state."""
        ...

    async def signal(self, run_id: str, name: str, payload: dict[str, str]) -> None:
        """Deliver a durable control signal (`resume`, `cancel`, `edit_resume`)."""
        ...
```

### 6.1 `runtime/local_runtime.py` — the default

- In-process, zero infrastructure, no `temporalio` import. This is the default (`KORCH_RUNTIME=local`) and what the Tier-1 one-liner in [04-public-api.md](04-public-api.md) uses.
- Drives the same `PregelRunner` loop; the "checkpoint" phase writes to the configured `GraphRepository`, whose default backend is in-memory.
- `now()` returns a monotone clock that is injectable in tests, so no test sleeps.
- Crash recovery is out of scope for this adapter: the process is the durability boundary. It MUST document that plainly rather than pretend otherwise.

### 6.2 `runtime/temporal_runtime.py` — the durable adapter

A single **`PregelMaster` workflow** drives the superstep loop and invokes **one `SuperstepActivity` per superstep**. That activity fans out to all active agents with `asyncio.gather`.

**It does NOT spawn a child workflow per agent.** The reasons are load-bearing:

1. Every child workflow adds its own event-history entries plus scheduling, start and completion events in the parent. At 100+ agents per superstep across many supersteps this multiplies the parent's event history and drives Temporal's persistence store into the failure mode the 50k-event cap exists to prevent.
2. Agent compute is short-lived and stateless within a superstep. It needs retry and timeout semantics — which an activity already gives — not independent durable lifetime, versioning, or signal handling.
3. One activity per superstep makes the barrier trivially exact: the barrier *is* the activity's completion. With N child workflows the workflow must additionally coordinate N futures, widening the nondeterminism surface for no benefit.
4. Fan-out inside one activity keeps the parallelism in `asyncio`, where it costs nothing, instead of in the Temporal task-queue hot path.

Child workflows remain the correct tool for a coarse-grained composition boundary (a versioned sub-swarm, a long human wait). That is a different granularity and does not contradict this rule.

**Pregel → Temporal mapping:**

| Pregel concept | Temporal primitive |
|---|---|
| Agent session / run | Workflow (`PregelMaster`, may sleep for months) |
| Plan phase | `plan_execution_activity` |
| Compute phase (all active agents) | one `SuperstepActivity`, auto-retried with backoff |
| Synchronise (barrier) | Activity completion inside workflow scope |
| Reduce | Pure workflow-scope code |
| Checkpoint | Workflow event history + `GraphRepository` write |
| Human-in-the-loop | Signal + `workflow.wait_condition` |
| Cancel / resume / edit-resume | Signals |
| Current time | `workflow.now()` |

`temporalio` MUST be imported inside the functions of this module, never at module top level, so the base install without the `[temporal]` extra still imports `korchestrator.runtime` cleanly. A `ProviderError` MUST be raised with an actionable message if the extra is missing when the adapter is selected.

## 7. HITL, retries and roll-over

**HITL pause/resume.** When `governance/` returns an intervention (an agent's trust score is below `hitl_threshold`, falling back to `GOVERNANCE_TRUST_THRESHOLD`), the barrier sets `status = governance_paused` and the workflow awaits a durable signal. The wait is bounded by a configurable deadline with a documented default of **24 hours**; on expiry the run transitions to `timed_out`. Accepted signals:

| Signal | Effect |
|---|---|
| `resume` | Continue from the checkpointed state unchanged |
| `edit_resume` | Apply an operator-supplied `StateUpdate` through the normal reducers, then continue |
| `cancel` | Terminate with `RunStatus.CANCELLED` |

A paused run consumes no compute. `edit_resume` MUST go through the reducers, not direct assignment, so an operator edit is as replayable and auditable as an agent's.

**Retry policy.** Activities retry with exponential backoff **and jitter** — jitter is mandatory to avoid a thundering herd when a whole worker fleet recovers at once. Defaults: initial interval 1s, backoff coefficient 2.0, maximum interval 60s, maximum attempts 3. `KorchError` subclasses that are definitionally non-retryable (`ValidationError`, `AuthError`, `QuotaExceededError`, `GovernanceHaltError`) MUST be registered as non-retryable so a bad request is not retried three times.

**Event-history roll-over.** Temporal caps an execution at **50,000 events**. `PregelMaster` MUST track its event count and call `continue_as_new` before the cap, carrying forward the checkpointed `AgentState`, the graph, the superstep counter and the run deadline. `run_id` is stable across roll-over; the workflow run id is not, and nothing in the SDK's public surface may depend on the workflow run id. A test MUST drive a run past a lowered roll-over threshold and assert `RunResult` is unaffected.

## 8. Runtime equivalence

The runtime is selected by configuration alone — `KORCH_RUNTIME=local|temporal` or `Korch(runtime=...)` — with no change to agent, graph, tool or routing code ([08-configuration-and-cross-cutting.md](08-configuration-and-cross-cutting.md)).

Both adapters MUST produce an **equivalent `RunResult`** for the same graph, initial state and MockLM gateway. Equivalent means: identical `status`, `final_answer`, `supersteps`, `trust_score`, and identical `messages` after excluding fields that are legitimately runtime-specific (timestamps drawn from the respective clocks). `tests/e2e/test_runtime_equivalence.py` MUST assert this with a shared fixture, and it is the test that fails if the two adapters ever drift.

Additionally required by [09-testing-and-quality.md](09-testing-and-quality.md):

- a Temporal replay test over recorded event history;
- a forced mid-run crash that resumes from the last checkpoint with no duplicated agent work;
- a repeatability test: the same run twice, byte-identical serialised results;
- reducer law tests (§3);
- a roll-over test (§7).
