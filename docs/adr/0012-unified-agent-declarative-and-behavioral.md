# ADR 0012 — One unified `Agent`: declarative and subclassable

- **Status:** Accepted
- **Date:** 2026-07-22
- **Deciders:** SDK maintainers (with product owner)
- **Phase:** P4
- **Supersedes / Superseded by:** Supersedes the provisional `korchestrator.services.Agent` frozen in
  P1.5; realises the behavioural agent of spec 07 §4. Preserves the public import path in spec 04 §7.

## Context

Two specs describe an `Agent` at two tiers:

- **Spec 04 (public API), Tier 2** — a *declarative* builder: `Agent(id="security",
  role="security-reviewer", model="gpt-4o")`, exported as `korchestrator.Agent` and (spec 04 §7's
  `__init__` listing) sourced `from korchestrator.services import Agent`. P1.5 built exactly this: a
  thin wrapper that validates into an `AgentConfig`, with no behaviour.
- **Spec 07 (extensibility), Tier 3** — a *behavioural* base you subclass and give a `think`:
  `from korchestrator.agents import Agent` … `class WordCountAgent(Agent): async def think(...)`.

Read literally, that is **two different classes both named `Agent`** — one in `services/`, one in
`agents/`. `from korchestrator import Agent` and `from korchestrator.agents import Agent` would then
bind different objects: a genuine footgun for users and maintainers, and a violation of "one concept,
one name" (spec 04 §3.1).

## Decision

**There is exactly one `Agent` class.** Its canonical home is `korchestrator/agents/base.py` (the
cognitive layer, where behaviour belongs). It is re-exported unchanged from `korchestrator.services`
and at the top level, so all three documented import paths resolve to the *same object*:

```python
from korchestrator import Agent            # top level (spec 04)
from korchestrator.services import Agent   # spec 04 §7 __init__ path (re-export)
from korchestrator.agents import Agent     # spec 07 §4 path (canonical)
# all three are the identical class
```

The one class is **both**:

- **Declarative** — the P1.5 constructor is preserved verbatim (`id`, `role`, `model`, `tools`,
  `goal`, `backstory`, `max_react_steps`, `hitl_threshold`, `timeout_seconds`), still wrapping any
  pydantic error as `korchestrator.ValidationError`. So Tier-2 usage is unchanged and non-breaking.
- **Behavioural** — it adds the frozen-snapshot surface: `async think(state) -> StateUpdate`
  (override in a subclass), `is_complete(state) -> bool`, `bind(*, clock)` (the composition root
  injects the replay-safe clock), `clock` (exposes `clock.now()`), and `to_node()` (materialise as a
  kernel `Node`). The base `think` raises `NotImplementedError`: a subclass overrides it, and a
  declaratively-constructed agent gets the framework's default reasoning agent when the façade wires
  execution (P4.9).

`services/agent.py` becomes a one-line re-export; `services/swarm.py` imports `Agent` from
`korchestrator.agents`. `korchestrator.services` (layer above `agents`) importing it is legal
inward-pointing layering.

## Alternatives considered

- **Two classes, spec-literal** (declarative `services.Agent` + behavioural `agents.Agent`).
  Rejected: ships two different classes named `Agent`, the exact footgun above.
- **Rename the behavioural base** (e.g. `BaseAgent`). Rejected: deviates from spec 07 §4's published
  `from korchestrator.agents import Agent`, and splits one concept into two names.

## Consequences

- The public surface is **unchanged**: `korchestrator.__all__` still lists `Agent`; the golden
  snapshot does not move. This is additive (new methods on an existing class) — non-breaking.
- Spec 04 §7 shows `Agent` sourced from `services`; it is now *defined* in `agents` and re-exported
  from `services`. The user-visible import paths are identical, so no consumer is affected; this ADR
  records the internal move.
- `korchestrator.agents.Agent` is the class users subclass for custom agents (spec 07 §4).
- The declarative agent is not runnable on its own until P4.9 supplies the default reasoning agent;
  until then its base `think` raises with an actionable message. Custom (overridden) agents run now.

## Rollback

Re-introduce a separate declarative class in `services/` and revert the re-export if the unified
constructor ever needs to diverge between tiers. No serialized data or wire contract depends on this,
so rollback is a code move; update this ADR to *Superseded*.
