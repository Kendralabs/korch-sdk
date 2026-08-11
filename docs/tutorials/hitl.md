# Human-in-the-loop

A durable run can pause for human review mid-execution and resume later — with or without an
operator's edits — without losing any state. This requires the **durable runtime**: the local
runtime is synchronous and has nothing to pause.

## Prerequisites

```bash
pip install "korchestrator[dspy,temporal]"
```

```bash
export KORCH_RUNTIME=temporal
export TEMPORAL_ADDRESS=localhost:7233   # your durable workflow engine server
```

A run started under `KORCH_RUNTIME=temporal` executes durably: it survives a worker crash, and it
can be paused, resumed, or cancelled from a completely separate process — an operator dashboard, an
API handler, a CLI — as long as that process also has a `Korch`/`Swarm` instance configured for the
same workflow-engine namespace and task queue.

## Two ways a run pauses

**1. Automatically, from low trust.** Governance monitors a run's `trust_score`; if it drops below
`GOVERNANCE_TRUST_THRESHOLD` (or an agent's own `hitl_threshold`), the run pauses itself — no
operator action needed to trigger it, only to resolve it.

**2. Manually, by an operator.** Call `pause` on any `run_id` you're aware of (typically obtained
from a "superstep" event — see [Streaming a run's events](streaming.md) — or logged/persisted when
the run started):

```python
from korchestrator import Korch

korch = Korch()  # KORCH_RUNTIME=temporal picked up from the environment
korch.pause(run_id)
```

## Resolving a pause

A paused run waits up to a 24-hour deadline for one of three signals. All three are synchronous
calls — they send a signal to the durable workflow and return immediately, they do not wait for the
run to finish:

```python
# Let it continue exactly as it was.
korch.resume(run_id)

# Cancel it outright — it terminates with RunStatus.CANCELLED.
korch.cancel(run_id)

# Apply an edit, then resume — e.g. raise trust back up after human review,
# or patch a context value the agents will see on their next superstep.
korch.edit_resume(run_id, updates={"reviewer_note": "approved, proceed"}, trust_delta=0.3)
```

`edit_resume`'s edit goes through the same reducer discipline the barrier itself uses — a
last-value merge for `updates`, a clamped fold for `trust_delta` — so an operator's edit is exactly
as replayable and auditable as anything an agent does.

## What happens if nobody resolves it

If no `resume`, `cancel`, or `edit_resume` arrives before the 24-hour deadline, the run times out on
its own: `RunResult.status` becomes `RunStatus.TIMED_OUT`. Build your operator tooling assuming
this is the failure mode to design around, not an edge case — a pause with no dashboard watching it
*will* time out.

## Verifying this yourself

A full pause → resume round trip needs a running workflow-engine server (or its test
environment), which isn't something a documentation page can execute inline. The SDK's own test
suite is the executable, CI-verified proof of every scenario above — pause-then-resume,
pause-with-no-resume-times-out, low-trust auto-pause, and `edit_resume` — in
`tests/integration/test_temporal_runtime.py`.

## Next

- [Streaming a run's events](streaming.md) — a `run_id` you can call `pause` on is easiest to get
  from a live event stream.
