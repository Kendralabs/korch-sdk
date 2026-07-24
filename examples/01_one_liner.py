"""The Tier-1 one-liner: zero configuration, no API key, no infrastructure.

Run: python examples/01_one_liner.py
Requires: pip install "korchestrator[dspy]"
"""

from korchestrator import Korch
from korchestrator.providers import MockLM

# With no model_gateway=, this uses MockLM's default echo — deterministic and offline, but not a
# "real" answer. Scripting a response here keeps this example's output readable.
gateway = MockLM(
    default_response=(
        "Durable agent execution means workflows survive crashes and replay "
        "deterministically. It combines a BSP-style kernel with a durable runtime "
        "like Temporal."
    )
)

result = Korch(model_gateway=gateway).run("Summarize durable agent execution in two sentences")

print("status:", result.status)
print("final_answer:", result.final_answer)
assert result.status.value == "completed"
