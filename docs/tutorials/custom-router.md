# Writing a custom router

Routing decides which model each agent uses when `model=` isn't pinned explicitly. The SDK ships
several built-in strategies; this tutorial writes your own.

## The built-in strategies

- **`ExplicitFallbackRouter`** (the default) — uses an agent's explicit `model=` if set, otherwise
  a configured fallback.
- **`AlgorithmicRouter`** — ranks candidate models by a weighted blend of quality, cost, and
  latency.
- **`SemanticRouter`** *(`[routing]` extra)* — routes by embedding similarity between the task and
  each model's description.
- **`CompositeRouter`** — chains strategies, falling through to the next on failure.
- **`UserFunctionRouter`** — wraps a plain function. This is what you reach for first.

## The router contract

Every router implements one method:

```python
async def select_model(self, context: RoutingContext) -> RoutingResult: ...
```

`RoutingContext` carries the agent id, the task's classified semantics (intent, difficulty,
required capabilities), and the candidate `ModelCard`s to choose from. `RoutingResult` names the
chosen `model_name`, the `strategy` that picked it, a `score`, and a human-readable `reason`.

## The quick path: `UserFunctionRouter`

Wrap a plain function — no class to write:

```python
from korchestrator import Agent, Swarm
from korchestrator.models.routing import RoutingContext, RoutingResult
from korchestrator.providers import MockLM
from korchestrator.routing import UserFunctionRouter


def pin_to_cheapest(context: RoutingContext) -> RoutingResult:
    return RoutingResult(
        model_name="gpt-4o-mini",
        strategy="user_function",
        score=1.0,
        reason="pinned to the cheapest available model for every agent",
    )


gateway = MockLM()
swarm = Swarm(
    objective="Summarize the incident report clearly",
    model_gateway=gateway,
    router=UserFunctionRouter(pin_to_cheapest),
).add(Agent(id="analyst", role="analyst"))

result = swarm.run()
print(result.status, {call.model for call in gateway.calls})
# RunStatus.COMPLETED {'gpt-4o-mini'}
```

`gateway.calls` (a `MockLM`-only convenience for tests and demos) confirms which model actually
reached the gateway — proof the router's choice was honoured, not just requested.

## A real decision, not just a pin

`pin_to_cheapest` above ignores `context` entirely. A real router reads it — here's one that
routes by the task's classified difficulty:

```python
def route_by_difficulty(context: RoutingContext) -> RoutingResult:
    if context.task.difficulty == "trivial":
        model = "gpt-4o-mini"
    else:
        model = "gpt-4o"
    return RoutingResult(
        model_name=model,
        strategy="user_function",
        score=1.0,
        reason=f"{context.task.difficulty} task routed to {model}",
    )
```

## Writing a full `BaseRouter`

For a strategy with its own state (a cache, a client, configuration beyond one closure), implement
`BaseRouter` directly instead of wrapping a function — the shape is the same one method:

```python
from korchestrator.interfaces import BaseRouter
from korchestrator.models.routing import RoutingContext, RoutingResult


class MyRouter(BaseRouter):
    def __init__(self, default_model: str) -> None:
        self._default_model = default_model

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        return RoutingResult(
            model_name=self._default_model,
            strategy="user_function",  # RoutingResult.strategy is a fixed vocabulary; this is
            score=1.0,                 # the closest fit for any custom, non-built-in strategy
            reason="always routes to the configured default",
        )
```

Pass an instance the same way: `Swarm(..., router=MyRouter("gpt-4o-mini"))`.

## Next

- [Building a swarm](swarm.md) — per-agent explicit `model=` still takes priority over any router
  for `ExplicitFallbackRouter`, the default.
- [Writing a custom tool](custom-tool.md) — the other major point of agent customization.
