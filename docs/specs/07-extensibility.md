# 07 — Extensibility

**Purpose:** Define every supported extension point, its contract, how an extension is registered, and how it is tested — so external developers extend the SDK without editing `core/`.
**Owner/status:** SDK maintainers · Normative · last reviewed 2026-07-20.

Read this when you are adding a provider, agent, router, tool, backend, middleware or hook — or when you are tempted to add a new interface.

## Contents

1. [When an extension point is justified](#1-when-an-extension-point-is-justified)
2. [Registration](#2-registration)
3. [ARI providers](#3-ari-providers)
4. [Custom agents](#4-custom-agents)
5. [Routers](#5-routers)
6. [Tools and connectors](#6-tools-and-connectors)
7. [MCP servers](#7-mcp-servers)
8. [Persistence backends](#8-persistence-backends)
9. [Middleware and event hooks](#9-middleware-and-event-hooks)
10. [Serializer and telemetry hooks](#10-serializer-and-telemetry-hooks)
11. [How NOT to extend](#11-how-not-to-extend)

Interfaces referenced here are declared in `interfaces/` and catalogued in [05-modules-and-data-models.md](05-modules-and-data-models.md); the layering they respect is argued in [03-architecture.md](03-architecture.md).

---

## 1. When an extension point is justified

An interface exists **only** when there is more than one real implementation in the SDK today, or a named third party already needs to substitute one. "We might want to swap this later" is not a justification.

| Port / protocol | Second implementation that justifies it |
|---|---|
| `IModelGateway` | `MockLM` (offline default) and the OpenAI-compatible gateway |
| `IExecutionSandbox` | Local subprocess and an external sandbox service |
| `IIdentityProvider` | Local unsecured identity and a JWT-based enterprise provider |
| `IDurableRuntime` | `local_runtime` and `temporal_runtime` |
| `BaseRouter` | Explicit, algorithmic and composite strategies |
| `AUBConnector` | File-system, search and MCP-backed connectors |
| `GraphRepository` | In-memory default and external graph/SQL backends |

Adding an eighth interface requires an ADR in `docs/adr/` naming the two implementations. Removing an implementation until only one remains is a signal to collapse the interface, not to keep it "for symmetry".

For backlog capabilities (Context Graph backends, speculative execution, FinOps quotas, the KL DSL) the rule is **interface now, implement minimally**: define the port with an in-memory or no-op default so the SDK runs standalone, and defer richer backends to post-1.0. Do not ship a partial implementation behind a flag.

## 2. Registration

There are exactly two registration mechanisms. Extensions are never discovered by scanning modules, by import side effects, or by monkey-patching.

**2.1 Explicit registration at the composition root.** `services/` is the only wiring site. Every collaborator is passed in:

```python
from korchestrator import Korch

korch = Korch(
    model_gateway=MyGateway(),
    router=MyRouter(),
    repository=MyRepository(),
    connectors=[MyConnector()],
    middleware=[MyMiddleware()],
)
```

This is the primary path, it is explicit, and it is what every example and test uses.

**2.2 Entry-point plugin discovery.** For distribution-installed extensions, the SDK reads `importlib.metadata.entry_points()` for these groups:

| Entry-point group | Expected object |
|---|---|
| `korchestrator.gateways` | zero-arg callable returning an `IModelGateway` |
| `korchestrator.routers` | zero-arg callable returning a `BaseRouter` |
| `korchestrator.connectors` | zero-arg callable returning an `AUBConnector` |
| `korchestrator.repositories` | zero-arg callable returning a `GraphRepository` |
| `korchestrator.middleware` | zero-arg callable returning a `Middleware` |

```toml
# a third-party package's pyproject.toml
[project.entry-points."korchestrator.connectors"]
acme_crm = "acme_korch.connectors:build_crm_connector"
```

Discovery rules, all testable:

- Discovery is **opt-in**: it runs only when `Settings.plugins_enabled` is true (`KORCH_PLUGINS_ENABLED`, default `false`). A default install loads no third-party code.
- Explicit registration always wins over a discovered plugin with the same name.
- A plugin whose factory raises is skipped with a `WARNING` on the `korchestrator` logger naming the entry point and the wrapped `ProviderError`; it never aborts startup.
- Discovery happens once, at composition-root construction, never inside the superstep loop.

## 3. ARI providers

The three ARI ports are the portability contract: the same agent logic runs against a local key or an enterprise control plane.

```python
from typing import Protocol, runtime_checkable

from korchestrator.models import ToolResult


@runtime_checkable
class IModelGateway(Protocol):
    """Routes a reasoning request to a model and returns its completion."""

    async def complete(
        self, *, model: str, prompt: str, max_tokens: int = 1024
    ) -> str:
        """Return the model's completion. MUST raise `ProviderError` on failure."""
        ...
```

Minimal working implementation:

```python
from korchestrator.exceptions import ProviderError


class EchoGateway:
    """Deterministic test gateway that echoes a fixed prefix."""

    def __init__(self, prefix: str = "echo:") -> None:
        self._prefix = prefix

    async def complete(self, *, model: str, prompt: str, max_tokens: int = 1024) -> str:
        if not prompt:
            raise ProviderError("Prompt must be non-empty.", code="PROVIDER_BAD_REQUEST")
        return f"{self._prefix}{prompt[:max_tokens]}"
```

Registered by `Korch(model_gateway=EchoGateway())` or the `korchestrator.gateways` entry point.

**Contract requirements.** A gateway MUST be safe to call concurrently from within one superstep, MUST wrap every vendor exception as `ProviderError` (`raise ... from exc`), MUST NOT read environment variables (its configuration is injected), and MUST NOT log prompts or credentials.

`IExecutionSandbox` (`async def run(self, *, code: str, timeout_seconds: float) -> ToolResult`) and `IIdentityProvider` (`async def identify(self, *, agent_id: str) -> AgentIdentity`) follow the same shape and the same rules.

**Testing.** `tests/contract/test_ari_ports.py` parametrises a shared conformance suite over every registered implementation: concurrency safety, error wrapping, and no-environment-read. A third-party provider imports the same suite via the `korchestrator.testing` helper.

## 4. Custom agents

An agent is anything that turns a frozen `AgentState` into a `StateUpdate`. Subclass the base and implement `think`.

```python
from korchestrator.agents import Agent
from korchestrator.models import AgentState, Message, MessageRole, StateUpdate


class WordCountAgent(Agent):
    """Counts words in the objective and answers with the total."""

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
            agent_id=self.id,
            messages=(message,),
            halt=True,
            valid_time=message.valid_time,
        )
```

**Contract requirements.** `think` MUST NOT mutate `state`, MUST NOT call `datetime.now()` (use the injected `self.clock`), MUST NOT read another agent's output from the same superstep, and MUST return within `AgentConfig.timeout_seconds`. Returning `halt=True` permanently deactivates the node ([06-execution-model.md](06-execution-model.md) §2).

**Registration.** `Swarm().add(WordCountAgent(id="counter", persona=...))`, or by naming the class in an `ExecutionPlan`. No core edit, no registry entry.

**Testing.** Instantiate the agent, call `think` with a hand-built `AgentState` and a frozen clock, assert the returned `StateUpdate`. No gateway is needed for agents that do not reason; agents that do use MockLM.

## 5. Routers

```python
from korchestrator.models import RoutingContext, RoutingResult
from korchestrator.routing import BaseRouter


class CheapestRouter(BaseRouter):
    """Always selects the lowest input-cost candidate."""

    async def select_model(self, context: RoutingContext) -> RoutingResult:
        if not context.candidates:
            raise RoutingError("No candidate models available.", code="ROUTING_NO_CANDIDATES")
        best = min(context.candidates, key=lambda card: card.cost_per_1k_input_usd)
        return RoutingResult(
            model_name=best.name,
            strategy="user_function",
            score=1.0,
            reason=f"lowest input cost among {len(context.candidates)} candidates",
            fallbacks=best.fallbacks,
        )
```

**Contract requirements.** `select_model` MUST be pure with respect to `RoutingContext` — same context, same result — because routing decisions are replayed. It MUST populate `reason` with something a human can act on, and MUST raise `RoutingError` rather than silently returning a default when no candidate fits.

**Registration.** `Korch(router=CheapestRouter())`, `ROUTING_STRATEGY` naming a discovered plugin, or the `korchestrator.routers` entry point.

**Testing.** Feed a fixed `RoutingContext` with two `ModelCard`s and assert both the selected model and the `reason`. Purity is asserted by calling twice and comparing.

## 6. Tools and connectors

```python
from korchestrator.models import ToolResult
from korchestrator.tools import AUBConnector


class UppercaseConnector(AUBConnector):
    """Single-tool connector that uppercases its `text` argument."""

    name = "uppercase"
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def execute(self, tool: str, args: dict[str, str]) -> ToolResult:
        return ToolResult(tool=tool, ok=True, output=args["text"].upper())
```

**Contract requirements.** `execute` MUST NOT raise for expected failures — it returns `ToolResult(ok=False, error_code=..., error=...)` using the codes in [08-configuration-and-cross-cutting.md](08-configuration-and-cross-cutting.md). Unexpected failures MUST surface as `ToolError`. Arguments are validated against `schema` by the bridge **before** `execute` is called, so a connector never validates its own inputs. Every invocation passes through the bridge's timeout, rate limit, Shield gate and telemetry span — a connector never bypasses `tools/bridge.py`.

**Registration.** `Korch(connectors=[UppercaseConnector()])`, `register_connector(...)` at the composition root, or the `korchestrator.connectors` entry point. Agents mount tools by name via `AgentConfig.tools`; a tool that is not mounted is not visible, and calling it yields `TOOL_ACCESS_DENIED`.

**Testing.** Call `execute` directly for the happy path, then drive it through `invoke_tool` to assert schema rejection, timeout, and the denied-access path.

## 7. MCP servers

An MCP server is registered by connection descriptor, not by code:

```python
from korchestrator.mcp import MCPServerConfig

korch = Korch(mcp_servers=[MCPServerConfig(name="fs", transport="stdio", command="mcp-fs")])
```

The MCP client discovers the server's tools at composition time and registers each as an `AUBConnector`-backed entry in the same registry, so agents cannot tell an MCP tool from a native one. Progressive disclosure applies: an agent mounts only the tools named in `AgentConfig.tools`.

**Contract requirements.** Discovery failures MUST NOT abort the run — the server is skipped, a `WARNING` is logged with the server name, and its tools resolve to `TOOL_NOT_FOUND`. Every MCP call carries the identity from `IIdentityProvider`.

**Testing.** A stdio stub server fixture under `tests/integration/mcp/`; no network, no external process image.

## 8. Persistence backends

```python
from typing import Protocol

from korchestrator.models import AgentState


class GraphRepository(Protocol):
    """Persists checkpoints and bitemporal decision/event nodes."""

    async def save_checkpoint(self, state: AgentState) -> None: ...

    async def load_checkpoint(self, run_id: str, *, superstep: int | None = None) -> AgentState | None: ...

    async def list_runs(self, *, tenant_id: str, limit: int = 50) -> tuple[str, ...]: ...
```

**Contract requirements.** Every method MUST be tenant-scoped — `tenant_id` is mandatory data, never optional metadata. Writes MUST preserve both `valid_time` and `transaction_time` so time-travel queries stay answerable. `save_checkpoint` MUST be idempotent for a given `(run_id, superstep)`: a retried activity must not duplicate a node. `PERSISTENCE_BACKEND=none` MUST leave the SDK fully functional with an in-memory repository.

**Registration.** `Korch(repository=MyRepository())` or the `korchestrator.repositories` entry point.

**Testing.** A shared `GraphRepository` conformance suite covering round-trip, idempotent re-save, tenant isolation (tenant A cannot read tenant B's run), and time-travel load at an earlier superstep.

## 9. Middleware and event hooks

**Middleware** wraps a phase and may observe or veto; **hooks** observe only.

```python
from korchestrator.services import Middleware
from korchestrator.models import AgentState


class SuperstepTimer(Middleware):
    """Records how long each superstep took."""

    async def before_superstep(self, state: AgentState) -> None:
        self._started = state.transaction_time

    async def after_superstep(self, state: AgentState) -> None:
        elapsed = (state.transaction_time - self._started).total_seconds()
        logger.info("superstep_complete", extra={"superstep": state.superstep, "seconds": elapsed})
```

Supported phases: `before_superstep` / `after_superstep`, `before_tool` / `after_tool`.

```python
korch.on("superstep", handler)          # fired after each barrier
korch.on("message", handler)            # fired per message routed
korch.on("governance_pause", handler)   # fired when a run pauses for HITL
```

**Ordering guarantees.**

- `before_*` hooks run in **registration order**; `after_*` hooks run in **reverse registration order**, so middleware nests like a stack.
- Middleware always runs before event hooks for the same phase.
- Event handlers for one event run in registration order.
- Middleware and hooks run in **activity scope**, never workflow scope, so a hook can do I/O without breaking determinism. A hook MUST NOT influence `S(t+1)`; the barrier result is computed before hooks fire.

**Error isolation.** Precisely:

| Failure | Behaviour |
|---|---|
| An event hook raises | Exception caught, logged at `ERROR` with the handler's qualified name, run continues unaffected. A hook can never fail a run. |
| `after_superstep` middleware raises | Same as an event hook: caught, logged, run continues. The superstep is already committed. |
| `before_superstep` middleware raises `GovernanceHaltError` | Deliberate veto: the run transitions to `governance_paused`. This is the only sanctioned way for middleware to stop a run. |
| `before_superstep` middleware raises anything else | Caught, logged at `ERROR`, run continues. A buggy middleware MUST NOT be able to halt production work. |
| `before_tool` middleware raises `ToolError` | The call is denied and the agent receives `ToolResult(ok=False, error_code="TOOL_ACCESS_DENIED")`. |

Under no failure mode may a hook or middleware mutate `AgentState`, corrupt a checkpoint, or change the superstep count. A test MUST register a hook that always raises and assert the run still completes with an unchanged `RunResult`.

## 10. Serializer and telemetry hooks

- **Serializers.** Register a codec for a custom `context` payload type with `register_codec(type_, encode, decode)`. A codec MUST be deterministic (stable key ordering, no set iteration) and version-tagged; a decode failure raises `ValidationError`, never a silent fallback.
- **Telemetry.** Provide a custom span exporter through the OTel SDK, not through a Korchestrator-specific interface — there is no second telemetry abstraction. When telemetry is disabled the hook is never constructed and costs nothing.

## 11. How NOT to extend

Each of these is a review-blocking rejection.

| Anti-pattern | Why it is rejected | Do this instead |
|---|---|---|
| Editing `core/` to add a feature | Breaks the framework-free kernel and the determinism guarantee | Add an agent, middleware, or reducer-compatible channel |
| Monkey-patching a Korchestrator symbol at import time | Invisible, order-dependent, unreplayable | Register explicitly at the composition root |
| Import-time side effects in a plugin module | Makes `import korchestrator` non-deterministic and slow | Expose a zero-arg factory in an entry point |
| Reading `os.environ` in a provider or connector | Breaks the single-config rule | Take configuration as constructor arguments |
| Introducing a second router, redactor, error base or config source | Two sources of truth for one concern | Add a strategy behind the existing interface |
| Wall-clock or `random` inside `think` or a reducer | Breaks replay | Use the injected clock; put entropy in an activity |
| A new interface with one implementation | Speculative abstraction | Write the concrete class; add the port at the second implementation |
| Mutating `AgentState` from a hook | Corrupts the barrier's pure merge | Emit a `StateUpdate` from an agent |
| Raising from a hook to abort a run | Hooks are observers | Raise `GovernanceHaltError` from `before_superstep` middleware |
| Subclassing `PregelRunner` | Not part of the compatibility surface | Compose it, or inject a different `IDurableRuntime` |
