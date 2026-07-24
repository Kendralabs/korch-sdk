# Quick Start

This page takes you from a fresh install to a completed run using nothing but the standard
library and Korchestrator itself — no API key, no network, no infrastructure.

## Install

```bash
pip install "korchestrator[dspy]"
```

`[dspy]` is required: every reasoning agent is built on [DSPy](https://dspy.ai), so it's needed to
actually *run* a swarm, not just import the package. See [Installation](installation.md) for the
full extras table — and, until the package is published, how to install from source instead.

## Run your first swarm

```python
from korchestrator import Korch

result = Korch().run("Summarize durable agent execution in two sentences")
print(result.status)
```

That's it — no configuration. With no API key and no `model_gateway=` argument, `Korch()` uses
**MockLM**, a deterministic, fully offline model gateway: the same prompt always produces the same
completion. That is what makes this runnable with zero setup, and it's also what the SDK's own test
suite runs on. Its default completion is a raw echo of the prompt it was given, not a "real"
answer — useful for proving the machinery works, not for reading.

To see clean, human-readable output from the same one-liner, script MockLM's response:

```python
from korchestrator import Korch
from korchestrator.providers import MockLM

gateway = MockLM(
    default_response=(
        "Durable agent execution means workflows survive crashes and replay "
        "deterministically. It combines a BSP-style kernel with a durable runtime "
        "like Temporal."
    )
)
result = Korch(model_gateway=gateway).run("Summarize durable agent execution in two sentences")
print(result.status)        # RunStatus.COMPLETED
print(result.final_answer)  # the scripted response above
```

## What just happened

`Korch().run(objective)`:

1. Classifies the objective (its intent and difficulty).
2. Plans a small team of agents for it (the Architect).
3. Drives that team through the deterministic execution kernel — one or more **supersteps**, each
   agent reasoning in parallel against a shared, frozen snapshot of state.
4. Returns a `RunResult`: `status`, `final_answer`, `messages` (the full reasoning trace), and more.

## Using a real model

Point at a real, OpenAI-compatible gateway with two environment variables:

```bash
export KENDRA_AI_GATEWAY_URL="https://your-gateway.example.com/v1"
export KENDRA_GATEWAY_API_KEY="sk-..."
```

```python
from korchestrator import Korch

# No code change — Korch() picks up a real gateway automatically once a key is configured.
result = Korch().run("Summarize durable agent execution in two sentences")
print(result.final_answer)  # a real model's answer, not an echo
```

## Building an explicit team

The one-liner plans agents for you. When you want to declare the team yourself — specific
roles, specific models, an explicit topology — use `Swarm`:

```python
from korchestrator import Agent, Swarm
from korchestrator.providers import MockLM

swarm = (
    Swarm(objective="Review this change for security and performance", model_gateway=MockLM())
    .add(Agent(id="security", role="security-reviewer"))
    .add(Agent(id="perf", role="performance-reviewer"))
    .add(Agent(id="lead", role="review-lead"))
    .edges([("security", "lead"), ("perf", "lead")])
)
result = swarm.run(max_supersteps=5)
print(result.status)
```

`security` and `perf` run concurrently in the first superstep; `lead` runs once both have reported,
having received their messages. `Agent`, `Swarm`, and `Korch` are all typed and `mypy --strict`
clean — your editor will autocomplete every field.

## Next steps

- **Installation** — the full extras table and what each one unlocks: [installation.md](installation.md)
- Explore `RunResult.messages` to see the full reasoning trace, not just `final_answer`.
- Pass `connectors=[...]` to `Korch`/`Swarm` to give agents real tools to call.
