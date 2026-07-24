# Installation

Korchestrator requires **Python 3.10 or newer**.

## Base install

```bash
pip install korchestrator
```

The base install depends on **`pydantic` alone** — no LLM SDK, no workflow engine, nothing heavy.
It imports cleanly and lets you construct configuration and typed models, but it cannot yet *run*
a swarm: reasoning is built on [DSPy](https://dspy.ai) and needs the `[dspy]` extra (see below).

## Install what you need

Everything beyond `pydantic` is an **optional extra** — install only what your use case needs.

| Extra | Adds | Needed for |
|---|---|---|
| `[dspy]` | `dspy` | Actually running a swarm — every reasoning agent is built on it. **Almost everyone needs this one.** |
| `[temporal]` | `temporalio` | The durable, replayable runtime (survives process crashes, supports pause/resume) |
| `[routing]` | `sentence-transformers`, `numpy` | Semantic model routing (routing by embedding similarity) |
| `[mcp]` | `mcp` | Connecting to Model Context Protocol tool servers |
| `[remote]` | `httpx` | `KorchestratorClient` — driving a remote, hosted Korchestrator engine |
| `[otel]` | `opentelemetry-api`, `opentelemetry-sdk` | Optional tracing/metrics export |
| `[all]` | every extra above | Development, or when you're not sure yet what you'll need |

Extras compose — request as many as you need in one install:

```bash
# The common case: run swarms locally, durably, with real tools.
pip install "korchestrator[dspy,temporal,mcp]"

# Everything.
pip install "korchestrator[all]"
```

## Verify the install

```bash
python -c "import korchestrator; print(korchestrator.__version__)"
```

This works on the base install — no extras, no network, no API key required.

## Next

Continue to the [Quick Start](quickstart.md) to run your first swarm.
