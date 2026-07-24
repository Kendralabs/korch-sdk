# Writing a custom agent

`Agent(id=..., role=...)` gives you the default DSPy-based reasoning agent. Subclass `Agent` and
override `think` when you want to supply your own logic instead — no DSPy, no model gateway, no
`[dspy]` extra required.

## The frozen-snapshot contract

`think(state)` receives an **immutable** snapshot of the run's state and must return a
`StateUpdate` describing what changed — it never mutates `state` directly (the model is frozen;
attempting to would raise). This is what keeps the kernel deterministic: every agent active in a
superstep computes against the exact same snapshot, in parallel, with no risk of one agent
observing another's still-in-progress work.

Three rules `think` must follow:

- **Never call `datetime.now()`** — use `self.clock.now()`, the run's injected, replay-safe clock.
- **Never read another agent's output from the same superstep** — only the previous superstep's
  messages are visible, via `state.messages` / `state.inbox`.
- **Return within `timeout_seconds`** (a constructor argument, default 120s).

## A worked example

A custom agent that answers with the objective's word count — no reasoning model needed at all:

```python
from korchestrator import Agent, Swarm
from korchestrator.models.state import AgentState, StateUpdate, Message, MessageRole


class WordCountAgent(Agent):
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
print(result.status, result.final_answer)
# RunStatus.COMPLETED 6 words
```

No `model_gateway=` is passed to `Swarm` — a custom agent that never calls `self._gateway` doesn't
need one. `Swarm(...)` still runs the full kernel path (supersteps, reducers, routing for any
*other* agent in the swarm that does need one) — only this one agent's reasoning is replaced.

## Key parts

- **`Message.kind="answer"`** marks a message as contributing to `RunResult.final_answer`. Use
  `"thought"` for scratch reasoning that shouldn't appear in the final answer, or `"tool"` for a
  tool call's observation.
- **`halt=True`** deactivates this agent's node permanently — it will not run again in a later
  superstep. Leave it `False` if the agent should keep participating (e.g. reacting to messages a
  later superstep delivers).
- **`StateUpdate.valid_time`** should come from `self.clock.now()` (directly, or via a message you
  already stamped with it) — never a fresh `datetime.now()` call.

## Mixing custom and default agents

A `Swarm` can combine custom agents with default ones freely — declare a topology exactly as you
would with only `Agent(...)` instances. Here `WordCountAgent`'s message uses `kind="thought"`
instead of `"answer"`, so it feeds context to `lead` without itself contributing text to
`final_answer` (`lead`'s own answer, the only `kind="answer"` message, becomes `final_answer`):

```python
from korchestrator import Agent, Swarm
from korchestrator.providers import MockLM
from korchestrator.models.state import AgentState, StateUpdate, Message, MessageRole


class WordCountAgent(Agent):
    async def think(self, state: AgentState) -> StateUpdate:
        total = len(state.objective.split())
        message = Message(
            id=f"{state.run_id}:{state.superstep}:{self.id}:0",
            role=MessageRole.ASSISTANT,
            kind="thought",
            sender=self.id,
            content=f"word count: {total}",
            superstep=state.superstep,
            valid_time=self.clock.now(),
        )
        return StateUpdate(
            agent_id=self.id, messages=(message,), halt=True, valid_time=message.valid_time
        )


swarm = (
    Swarm(objective="Count words, then have a lead review the count", model_gateway=MockLM())
    .add(WordCountAgent(id="counter", role="counter"))
    .add(Agent(id="lead", role="review-lead"))
    .edges([("counter", "lead")])
)
result = swarm.run()
print([message.kind for message in result.messages])
# ['thought', 'answer', 'answer']
```

`lead` is a default DSPy agent, so this variant needs the `[dspy]` extra; `WordCountAgent` alone,
as in the first example, does not.

## Next

- [Writing a custom tool](custom-tool.md) — give an agent something to *call*, not just reasoning
  logic.
- [Streaming a run's events](streaming.md) — observe a swarm's progress, custom or default agents
  alike.
