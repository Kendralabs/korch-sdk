# Building a swarm

This tutorial builds a three-agent code-review swarm with an explicit topology and per-agent
models, then reads the full reasoning trace — not just the final answer.

## The topology

```python
from korchestrator import Agent, Swarm
from korchestrator.providers import MockLM

gateway = MockLM(
    responses={
        "gpt-4o-mini": "No obvious security issues found.",
        "claude-3.5-haiku": "Performance looks acceptable; no hot loops detected.",
    }
)
swarm = (
    Swarm(objective="Review this change for security and performance", model_gateway=gateway)
    .add(Agent(id="security", role="security-reviewer", model="gpt-4o-mini"))
    .add(Agent(id="perf", role="performance-reviewer", model="claude-3.5-haiku"))
    .add(Agent(id="lead", role="review-lead"))
    .edges([("security", "lead"), ("perf", "lead")])
)
result = swarm.run(max_supersteps=5)
print(result.status, result.supersteps)
```

`MockLM(responses={...})` scripts a fixed completion **per model name** — every agent routed to
that model returns the same text, deterministically. `security` and `perf` are pinned to specific
models; `lead` has no `model=`, so routing decides for it (the default strategy falls back to a
configured default model).

## Reading the trace

`RunResult.messages` carries every message from every superstep, not just the final answer:

```python
for message in result.messages:
    print(message.superstep, message.sender, "->", message.kind, ":", message.content[:60])
```

```text
0 lead -> answer : No obvious security issues found.
0 perf -> answer : Performance looks acceptable; no hot loops detected.
0 security -> answer : No obvious security issues found.
1 lead -> answer : No obvious security issues found.
```

Two things worth noticing:

- **Every agent runs in superstep 0, including `lead`** — the kernel activates every node on the
  first superstep regardless of the declared edges (a node only waits for its inbox from superstep
  1 onward). `lead` produces an answer immediately, before `security`/`perf`'s messages have
  reached it.
- **`lead` runs again in superstep 1**, now with `security` and `perf`'s messages in its inbox
  (routed there by the `edges([...])` you declared), and produces another answer. With MockLM's
  scripted, model-keyed responses this happens to be identical text — a real reasoning model would
  use the received messages to produce a genuinely different, informed answer the second time.

`result.final_answer` joins every `kind="answer"` message in order — it's a convenience projection
over `result.messages`, not a separate value.

## Next

- [Writing a custom agent](custom-agent.md) if you want full control over one agent's reasoning
  instead of the default DSPy worker.
- [Writing a custom tool](custom-tool.md) to give an agent something to call, not just something to
  say.
