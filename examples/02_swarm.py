"""An explicit multi-agent topology with per-agent models.

Run: python examples/02_swarm.py
Requires: pip install "korchestrator[dspy]"
"""

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

print("status:", result.status, "supersteps:", result.supersteps)
for message in result.messages:
    print(f"  [{message.superstep}] {message.sender} ({message.kind}): {message.content[:60]}")

assert result.status.value == "completed"
