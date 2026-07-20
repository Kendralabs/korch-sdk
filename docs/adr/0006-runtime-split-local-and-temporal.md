# ADR 0006 — Runtime split: local and Temporal behind `IDurableRuntime`

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

Durability is the product's central differentiator: a crash mid-run must not lose progress, and a
run must be replayable (spec §2.2, §2.6). Temporal provides that, and the Pregel BSP loop maps onto
it cleanly (platform reference §4.1).

It also imposes a cost that is fatal if made unconditional. Temporal requires a running server,
a worker process, and a database. A developer evaluating the SDK, a CI job, and an application
embedding the kernel in-process can supply none of those. An SDK that cannot execute anything until
infrastructure is provisioned is not a developer product — it is a service with a client library
attached.

Both properties are required. That forces two implementations, which forces the question of what
they implement — and, for the Temporal side, a second question that determines whether the system
scales at all: how agent parallelism inside a superstep maps onto Temporal primitives.

Spec §4 permits an interface only where more than one implementation genuinely exists. This is one
of the few places where it does.

## Decision

**One port, `IDurableRuntime` (in `interfaces/runtime.py`), with two adapters.**

**`runtime/local_runtime.py`** — in-process execution of the Pregel loop. Zero infrastructure, no
Temporal import at any level, available on the base install. It is the default, and it is what
examples, tutorials, the test suite, and embedded use run on.

**`runtime/temporal_runtime.py`** — the durable adapter, behind the `[temporal]` extra (ADR 0004).
Its shape is the important part of this decision:

> A single **`PregelMaster`** workflow drives the superstep loop. It invokes **one
> `SuperstepActivity` per superstep**, and that activity fans out across all active agents with
> `asyncio.gather`. It does **not** spawn a child workflow, or an activity, per agent.

**Why that shape, and what it costs.** Temporal records every workflow-level action in the workflow's
event history, which is persisted, replayed on recovery, and capped (Temporal terminates executions
that exceed ~50,000 events). A child workflow per agent means every agent in every superstep
contributes several events. At the target of 100+ concurrent agents over many supersteps, event
history grows multiplicatively, persistence load becomes the bottleneck, and long-running swarms hit
the cap and are terminated. Collapsing intra-superstep parallelism into a single activity keeps agent
fan-out entirely off the event-history hot path: one superstep costs a bounded, constant number of
events regardless of agent count.

The cost is real and must be stated plainly: **retry granularity is the superstep, not the agent.**
If one agent out of fifty fails inside a `SuperstepActivity`, Temporal retries the activity, and all
fifty agents run again. Agent work must therefore be idempotent or cheap to repeat, and per-agent
failure isolation — if it is ever needed — must be implemented *inside* the activity, not delegated
to Temporal's retry machinery. We accept this: superstep-level retry is the price of scaling past
the event-history wall, and the wall is not negotiable.

**Selection is configuration only:** `KORCH_RUNTIME=local|temporal`, read exclusively in `config/`
(spec §9.1). No user code changes when the runtime changes. The façade injects the selected runtime
at the composition root; nothing below constructs one.

**`temporalio` is imported only in `runtime/temporal_runtime.py`,** lazily, inside the function that
needs it. `core/` never sees it (spec §4).

**Equivalence is a test, not a claim.** The same swarm run on both runtimes must produce an
equivalent `RunResult` — same final answer, same superstep count, same terminal status, same message
sequence. This is asserted by a test, and it is the property that makes the local runtime a
trustworthy development target rather than an approximation.

Determinism constraints apply to the Temporal workflow path without exception: no wall clock, no
randomness, no I/O in workflow scope. Nondeterminism lives in activities.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Temporal-only — no local runtime** | One implementation, one code path, no equivalence obligation, and durability is never accidentally absent. This is the right architecture for a *service*. It is fatal for an SDK: nothing runs without a Temporal server plus a worker plus a database, so the quickstart requires infrastructure, CI requires infrastructure, and embedding the kernel in an application is impossible. It would also make the pydantic-only kernel guarantee (ADR 0004) unreachable. |
| **Local-only — no durable runtime** | Trivially simple and covers evaluation and development completely. Rejected because durable, replayable, crash-safe execution is the differentiator the entire product rests on (spec §2.6). Shipping without it means competing with LangGraph and CrewAI on their terms. |
| **Child workflow per agent** (Temporal adapter) | Genuinely attractive: per-agent retry, per-agent timeout, per-agent visibility in the Temporal UI, and each agent independently resumable. If swarms were small, this would be the better design. Rejected because it does not survive the target scale — event history and persistence load grow with agents × supersteps, and long-running swarms hit Temporal's per-execution event cap and are terminated. We trade retry granularity for the ability to run 100+ agents at all. |
| **Activity per agent** (rather than child workflow) | Cheaper than a child workflow and restores per-agent retry. Still rejected: each activity scheduled and completed is several workflow-history events, so the same multiplicative growth applies, merely with a smaller constant. It also serialises the scheduling of N activities through the workflow task, adding latency to a barrier budgeted at ~100 ms. |
| **A third "hybrid" runtime** (local execution with an external checkpoint store) | Would offer partial durability without Temporal. Rejected as speculative abstraction (spec §4): it is a third implementation of a port that only needs two, solving a problem no user has yet reported. Revisit only with a concrete requirement. |

## Consequences

**Positive**

- `pip install korchestrator` and run — no infrastructure. Quickstart, examples, and the whole test
  suite execute offline, which is what makes the SDK a developer product.
- Durability is a configuration change, not a rewrite. The migration from evaluation to production
  costs one environment variable.
- The single-activity fan-out keeps event history bounded per superstep, so agent count scales
  without a corresponding persistence blow-up.
- `core/` stays framework-free and the base install stays `pydantic`-only.

**Negative**

- Two implementations must be kept behaviourally equivalent forever. Every kernel change carries an
  equivalence-testing obligation, and divergence is a silent, high-severity bug class.
- Retry granularity is the superstep. One failing agent re-runs its whole superstep; agent work must
  be idempotent or cheaply repeatable. Per-agent failure handling is our problem, inside the
  activity.
- The local runtime offers no durability at all. A crash loses the run. This must be stated
  prominently in the docs, because the default being non-durable in a product that sells durability
  is exactly the kind of thing users discover in production.

**Neutral**

- Per-agent spans in the Temporal UI are not available; observability for individual agents comes
  from OpenTelemetry spans emitted inside the activity (spec §9.5), not from Temporal's own view.
- The `IDurableRuntime` port is public, so a third-party runtime is possible. That is a side effect
  of the split, not a goal of it.

## Compliance

- **Equivalence test** — the load-bearing check. `tests/e2e/test_runtime_equivalence.py` runs an
  identical swarm under `KORCH_RUNTIME=local` and `KORCH_RUNTIME=temporal` (against the Temporal test
  environment) and asserts the two `RunResult` objects are equivalent on final answer, terminal
  status, superstep count, and message sequence. A kernel change that diverges the runtimes fails
  here.
- **Import confinement** — `tests/unit/test_import_purity.py` (ADR 0004) asserts `temporalio` is
  absent from `sys.modules` after `import korchestrator`, even when `[temporal]` is installed. A
  static check additionally asserts that `temporalio` appears in no file under `src/korchestrator/`
  other than `runtime/temporal_runtime.py`.
- **Fan-out shape** — `tests/integration/test_temporal_event_history.py` asserts that running a
  swarm of N agents for K supersteps produces a workflow event history whose size is a function of K
  and not of N, and that no child workflow is started. This is what prevents a well-meaning refactor
  from silently reintroducing per-agent workflows.
- **Determinism** — the Temporal replay test (spec §12 Phase 3) replays a recorded history against
  current workflow code and fails on nondeterminism. `core/` and the workflow path are additionally
  checked for `datetime.now`, `time.time`, and `random` usage.
- **Config-only selection** — `tests/integration/test_runtime_selection.py` asserts the runtime is
  chosen solely from `KORCH_RUNTIME` via `Settings`, and that no user-facing API requires a change
  between the two.

## Rollback

Removing the Temporal adapter is straightforward — it is one module behind one extra, and its
absence degrades to local-only. Removing the *local* adapter is not: it is the default, the test
substrate, and the documented quickstart path.

Changing the Temporal adapter's internal shape — from single-activity fan-out to per-agent workflows
or back — is not a public API break, but it is a **durability-semantics** break for in-flight runs.
Workflow histories recorded under one shape cannot be replayed against code implementing the other,
so the change requires a Temporal versioning gate (`workflow.patched()`) and a documented drain of
in-flight runs before the gate is removed.

**Point of no return:** the first production deployment with in-flight durable runs. Before that, the
adapter's shape is an implementation detail. After it, every change to workflow-path code is
constrained by replay compatibility with histories already on disk.
