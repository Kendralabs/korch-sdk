"""A fully custom agent — no DSPy, no model gateway required at all.

Run: python examples/03_custom_agent.py
Requires: pip install korchestrator   # base install is enough; no [dspy] needed
"""

from korchestrator import Agent, Swarm
from korchestrator.models.state import AgentState, Message, MessageRole, StateUpdate


class WordCountAgent(Agent):
    """Answers with the objective's word count — supplies its own reasoning."""

    async def think(self, state: AgentState) -> StateUpdate:
        total = len(state.objective.split())
        message = Message(
            id=f"{state.run_id}:{state.superstep}:{self.id}:0",
            role=MessageRole.ASSISTANT,
            kind="answer",
            sender=self.id,
            content=f"{total} words",
            superstep=state.superstep,
            valid_time=self.clock.now(),
        )
        return StateUpdate(
            agent_id=self.id, messages=(message,), halt=True, valid_time=message.valid_time
        )


swarm = Swarm(objective="Count the words in this objective").add(
    WordCountAgent(id="counter", role="counter")
)
result = swarm.run()

print("status:", result.status)
print("final_answer:", result.final_answer)
assert result.final_answer == "6 words"
