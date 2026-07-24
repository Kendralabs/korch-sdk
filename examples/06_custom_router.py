"""A custom router that reads the task's classified difficulty to pick a model.

Run: python examples/06_custom_router.py
Requires: pip install "korchestrator[dspy]"
"""

from korchestrator import Agent, Swarm
from korchestrator.models.routing import RoutingContext, RoutingResult
from korchestrator.providers import MockLM
from korchestrator.routing import UserFunctionRouter


def route_by_difficulty(context: RoutingContext) -> RoutingResult:
    model = "gpt-4o-mini" if context.task.difficulty == "trivial" else "gpt-4o"
    return RoutingResult(
        model_name=model,
        strategy="user_function",
        score=1.0,
        reason=f"{context.task.difficulty} task routed to {model}",
    )


gateway = MockLM()
swarm = Swarm(
    objective="Summarize the incident report clearly",
    model_gateway=gateway,
    router=UserFunctionRouter(route_by_difficulty),
).add(Agent(id="analyst", role="analyst"))

result = swarm.run()

print("status:", result.status)
print("models actually used:", {call.model for call in gateway.calls})
assert result.status.value == "completed"
