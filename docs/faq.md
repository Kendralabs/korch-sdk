# FAQ

## Why does `Korch().run(...)` need the `[dspy]` extra? I thought the base install was just `pydantic`.

Both are true. The base install (`pydantic` alone) *imports* cleanly and lets you build
configuration and typed models. But every reasoning agent is built on
[DSPy](https://dspy.ai) — there's deliberately one reasoning implementation, not a lighter
non-DSPy fallback that would double the surface and risk drifting out of behavioral parity. So
"works on a base install" means *no API key, no network* (MockLM handles that) — not *no
`[dspy]`*. See [Installation](installation.md).

If you want to run without `[dspy]` at all, write a fully custom agent instead of using the
default reasoning worker — see [Writing a custom agent](tutorials/custom-agent.md).

## What's the difference between `Korch` and `Swarm`?

`Korch().run(objective)` is the one-liner: it classifies your objective and plans a team of agents
for you (the Architect). `Swarm` is the typed builder: you declare the agents, their models, and
the topology (`edges`) explicitly. Reach for `Korch` when you want the framework to decide the
team; reach for `Swarm` when you already know it. Both drive the same kernel underneath.

## Does this need any infrastructure to try?

No. The zero-config default is: local (in-process) runtime, `MockLM` (deterministic, offline)
gateway, in-memory persistence. `pip install "korchestrator[dspy]"` and `Korch().run(...)` need no
API key, no network, and no service running. See the [Quick Start](quickstart.md).

## Is this production-ready?

Korchestrator is `0.x` and pre-first-release (see [Project status in the
README](https://github.com/kendralabs/korch-sdk#project-status)) — Phases 0–10 (the kernel,
runtimes, agents, routing, tools, governance, the remote client, and the full test/benchmark
suite) are complete and tested; Phase 11 (this documentation) is in progress, and Phase 12
(publishing) hasn't shipped. Judge readiness for your use case against that state directly rather
than a blanket label — see [`.claude/memory/PROJECT_STATE.md`](https://github.com/kendralabs/korch-sdk/blob/develop/.claude/memory/PROJECT_STATE.md)
in the repository for the current, detailed snapshot.

## How is this different from LangGraph / CrewAI / AutoGen?

The comparison that matters most is the execution model, not the feature list: Korchestrator runs
supersteps as a **Pregel-style Bulk Synchronous Parallel** computation — every active agent
computes against a frozen snapshot in parallel, and results merge through reducers that are
associative and order-independent, so concurrency can never change the outcome. Paired with the
Temporal runtime, a run is durable (survives a crash, resumes from its last checkpoint) and
replayable. See [Architecture](architecture.md) for the full mechanism. This project doesn't
maintain a feature-by-feature comparison table against other frameworks — architectures are worth
understanding on their own terms.

## Can I use a model provider other than through the Kendra gateway?

The built-in real gateway (`OpenAIGateway`) speaks the OpenAI-compatible chat completions shape
against a configured `base_url` — point `KENDRA_AI_GATEWAY_URL` at any OpenAI-API-compatible
endpoint, not necessarily Kendra's own. For a provider with an incompatible wire format, implement
`IModelGateway` yourself (`async complete(messages, *, model, max_tokens) -> Message`) and pass it
as `model_gateway=` to `Korch`/`Swarm` — it's an ARI port specifically so you can do this.

## Does state survive a restart?

Depends on the runtime and the persistence backend, independently:

- **Local runtime** is synchronous and in-process — nothing survives the process ending.
- **Temporal runtime** checkpoints every superstep durably regardless of persistence backend — a
  crash resumes from the last barrier.
- **`PERSISTENCE_BACKEND`** (in-memory by default) controls whether the bitemporal decision/event
  record itself is queryable after the fact, separately from run durability.

## What happens if an agent takes too long?

Each agent has its own `timeout_seconds` (default 120s); exceeding it fails that agent's turn. A
run overall is bounded by `max_supersteps` — reaching it without every agent halting ends the run
with an error rather than running forever.

## Where do I ask something this page doesn't answer?

Open an issue on the repository, or check
[Troubleshooting](troubleshooting.md) first — many concrete error messages are covered there.
