# 05 — Modules and Data Models

**Purpose:** Define every module directory under `src/korchestrator/` — its single responsibility, layer, allowed imports, optional extra and build phase — and fix the authoritative Pydantic v2 domain models the whole SDK exchanges.
**Owner/status:** SDK maintainers · Normative · last reviewed 2026-07-20.

Read this when you are adding a file, deciding where behaviour belongs, or changing a shared model's shape.

## Contents

1. [Module catalogue](#1-module-catalogue)
2. [Module contract](#2-module-contract)
3. [Domain models](#3-domain-models)
4. [Compatibility surface](#4-compatibility-surface)
5. [Bitemporality and immutability](#5-bitemporality-and-immutability)

Repository layout and file-naming conventions live in [02-repository-structure.md](02-repository-structure.md). The layering rule and ARI ports are argued in [03-architecture.md](03-architecture.md). Phase numbering is defined in [11-build-phase-plan.md](11-build-phase-plan.md).

---

## 1. Module catalogue

One row per directory under `src/korchestrator/`. "Allowed imports" is exhaustive: anything not listed is a review-blocking violation. All modules may additionally import the Python standard library, `pydantic`, and their own submodules.

| Module | Responsibility (one sentence) | Layer | Allowed imports (beyond stdlib + pydantic) | Extra | Phase |
|---|---|---|---|---|---|
| `config/` | Own the single typed `Settings` object and be the only place in the package that reads environment variables or `.env` files. | Leaf utility | `pydantic-settings`, `exceptions` | — | P0, P8 |
| `interfaces/` | Declare the ARI ports and structural protocols that every replaceable collaborator implements. | Contract | `models` | — | P1 |
| `models/` | Define the Pydantic domain models exchanged across every boundary. | Contract | `types`, `constants` | — | P1, P2 |
| `core/` | Run the framework-free Pregel BSP kernel: graph, supersteps, reducers, activation and halting. | Kernel | `interfaces`, `models`, `exceptions`, `types`, `constants` | — | P2 |
| `agents/` | Provide the DSPy reasoning layer: agent base, worker, architect meta-agent, compiled signatures. | Cognitive | `core`, `interfaces`, `models`, `exceptions`, `logging`, `dspy` (lazy) | `[dspy]` | P4 |
| `taxonomy/` | Classify intent and difficulty and hold agent descriptors used for planning and routing. | Cognitive | `models`, `interfaces`, `exceptions` | — | P4 |
| `routing/` | Select a model per agent through strategies behind one `BaseRouter`. | Cognitive | `interfaces`, `models`, `config`, `exceptions`, `logging` | `[routing]` for semantic strategies | P5 |
| `runtime/` | Implement `IDurableRuntime` twice — in-process `local_runtime` and durable `temporal_runtime`. | Adapter | `core`, `interfaces`, `models`, `config`, `exceptions`, `logging`, `temporalio` (lazy, `temporal_runtime.py` only) | `[temporal]` | P3 |
| `context/` | Compile execution context and extract the Minimum Viable Context; prune and summarise off the hot loop. | Context | `interfaces`, `models`, `config`, `exceptions` | — | P6 |
| `persistence/` | Provide the bitemporal Context Graph client behind `GraphRepository`, with an in-memory default backend. | Context | `interfaces`, `models`, `config`, `exceptions`, `serializers` | backend drivers optional | P7 |
| `providers/` | Ship the default ARI implementations: local identity, local sandbox, OpenAI-compatible gateway, MockLM. | Adapter | `interfaces`, `models`, `config`, `exceptions`, `logging` | provider clients optional | P4 |
| `tools/` | Expose the Agent Utility Bridge: connector registry, schema validation, timeouts, rate limits, Shield gate. | Integration | `interfaces`, `models`, `config`, `exceptions`, `security`, `telemetry`, `logging` | — | P6 |
| `mcp/` | Speak MCP as a client and register discovered tools into the AUB registry. | Integration | `interfaces`, `models`, `config`, `exceptions`, `mcp` (lazy) | `[mcp]` | P6 |
| `a2a/` | Transform agent-to-agent handoffs into typed directed messages. | Integration | `models`, `exceptions` | — | P6 |
| `governance/` | Score trust, evaluate policy, and raise HITL pause/resume decisions. | Governance | `interfaces`, `models`, `config`, `exceptions`, `logging` | — | P7 |
| `security/` | Redact PII, handle secrets, and sanitise output; one consolidated Shield implementation. | Leaf utility | `config`, `exceptions`, `constants` | — | P7, P8 |
| `events/` | Publish transport-agnostic execution events and drive hook dispatch. | Integration | `models`, `exceptions`, `logging` | — | P6 |
| `clients/` | Implement the remote HTTP client re-exported as `korchestrator.remote`. | Client | `models`, `exceptions`, `config`, `httpx` (lazy) | `[remote]` | P9 |
| `services/` | Compose the object graph and expose the `Korch` / `Swarm` / `Agent` façade — the one wiring site. | Façade | every module | — | P2–P9 |
| `serializers/` | Round-trip domain models to and from JSON/dict/YAML deterministically and version-tagged. | Leaf utility | `models`, `exceptions`, `constants` | — | P8 |
| `validators/` | Validate parameters, config, graphs, tool schemas and responses at trust boundaries. | Leaf utility | `models`, `exceptions`, `constants` | — | P8 |
| `telemetry/` | Emit optional OpenTelemetry spans and metrics with zero cost when disabled. | Leaf utility | `config`, `models`, OTel packages (lazy) | `[otel]` | P8 |
| `logging/` | Own the namespaced `korchestrator` logger and `enable_logging()`. | Leaf utility | `config` | — | P8 |
| `exceptions/` | Define the whole `KorchError` tree. | Leaf utility | `constants` | — | P1 |
| `types/` | Hold shared type aliases, `TypedDict`s and non-ARI `Protocol`s. | Leaf utility | — | — | P1 |
| `constants/` | Hold default values, enums of error codes, and event names. | Leaf utility | — | — | P0 |

**Import rules that CI enforces** ([09-testing-and-quality.md](09-testing-and-quality.md)):

- `core/` MUST NOT import `agents`, `routing`, `runtime`, `tools`, `mcp`, `a2a`, `governance`, `persistence`, `context`, `events`, `clients`, `services`, `config`, `telemetry`, or any third-party package other than `pydantic`.
- No module except `services/` may import a sibling feature module. Feature folders communicate through `interfaces/` and `models/`.
- `temporalio` MUST appear only in `runtime/temporal_runtime.py`; `dspy` only under `agents/`; `httpx` only under `clients/`; OTel packages only under `telemetry/`. Each MUST be imported inside the function that needs it, never at module top level.
- No module may import `backend.*`, `apps.*`, `services.*` (external), or `frontend`.
- `os.environ` / `os.getenv` / `dotenv` MUST appear only under `config/`.

## 2. Module contract

Every module directory MUST satisfy all of the following. Each item is checkable by a reviewer or by a test in `tests/unit/test_module_contract.py`.

1. A package `__init__.py` with an explicit `__all__` listing only the names other modules may import.
2. A module docstring whose first paragraph names the layer and the allowed imports, e.g. `"""Kernel layer. Imports: interfaces, models, stdlib, pydantic only."""`.
3. No file exceeds ~500 lines; no function or method exceeds ~50 lines. A file that outgrows the limit is split by responsibility, never by line count.
4. One responsibility per module. A second implementation of an existing concern (a second router, redactor, error base, config source) is rejected in review; variation is a new strategy behind the existing interface.
5. Full type annotations. `mypy --strict` is clean with no `# type: ignore` lacking an inline justification comment.
6. Every public callable has a Google-style docstring with a runnable example that works offline under MockLM.
7. Public functions return typed Pydantic models, never bare `dict`.

---

## 3. Domain models

All models live under `models/` and are the authoritative definitions. `types.JSONValue` is the shared alias:

```python
from __future__ import annotations

from typing import TypeAlias

JSONValue: TypeAlias = (
    str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
)
```

### 3.1 Enumerations and messages — `models/state.py`

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from korchestrator.types import JSONValue


class MessageRole(str, Enum):
    """Origin of a message, mirroring chat-completion roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Performative(str, Enum):
    """FIPA-lite speech act carried by an inter-agent message."""

    INFORM = "inform"
    REQUEST = "request"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    QUERY = "query"
    FAILURE = "failure"


class RunStatus(str, Enum):
    """Lifecycle state of a run; the only status vocabulary in the SDK."""

    STARTED = "started"
    RUNNING = "running"
    GOVERNANCE_PAUSED = "governance_paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class Message(BaseModel):
    """One immutable message produced by an agent in a given superstep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: MessageRole = MessageRole.ASSISTANT
    performative: Performative = Performative.INFORM
    kind: Literal["thought", "tool", "answer", "handoff"] = "thought"
    sender: str
    recipient: str | None = None
    content: str
    superstep: int = Field(ge=0)
    valid_time: datetime
    metadata: Mapping[str, JSONValue] = Field(default_factory=dict)
```

`Message.id` MUST be assigned deterministically by the kernel as `f"{run_id}:{superstep}:{sender}:{index}"`. `valid_time` MUST come from the runtime's injected clock. Neither field may use a `default_factory` that calls `uuid4()` or `datetime.now()` — that would break replay ([06-execution-model.md](06-execution-model.md)).

```python
class StateUpdate(BaseModel):
    """The typed delta an agent emits instead of mutating shared state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    updates: Mapping[str, JSONValue] = Field(default_factory=dict)
    messages: tuple[Message, ...] = ()
    halt: bool = False
    trust_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    valid_time: datetime


class AgentState(BaseModel):
    """Global shared state threaded through every superstep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run_id: str
    tenant_id: str = "default"
    objective: str = Field(min_length=10)
    messages: tuple[Message, ...] = ()
    context: Mapping[str, JSONValue] = Field(default_factory=dict)
    inbox: Mapping[str, tuple[Message, ...]] = Field(default_factory=dict)
    superstep: int = Field(default=0, ge=0)
    halted: bool = False
    status: RunStatus = RunStatus.STARTED
    trust_score: float = Field(default=1.0, ge=0.0, le=1.0)
    transaction_time: datetime
```

### 3.2 Agent models — `models/agent.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class AgentPersona(BaseModel):
    """Static natural-language identity supplied to a compiled signature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1)
    goal: str = ""
    backstory: str = ""


class AgentConfig(BaseModel):
    """Declarative configuration of one vertex in an agent graph."""

    # `protected_namespaces=()` is required because the field is named `model`.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    persona: AgentPersona
    model: str | None = None
    tools: tuple[str, ...] = ()
    max_react_steps: int = Field(default=3, ge=0, le=10)
    hitl_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)


class AgentDescriptor(BaseModel):
    """Taxonomy entry describing what an agent kind is good at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    description: str
    capabilities: tuple[str, ...] = ()
    intents: tuple[str, ...] = ()
    preferred_models: tuple[str, ...] = ()
```

### 3.3 Plan models — `models/plan.py`

```python
class TaskDecomposition(BaseModel):
    """One unit of work the planner assigned to a named agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    description: str
    assigned_agent: str
    depends_on: tuple[str, ...] = ()
    expected_output: str = ""


class ExecutionPlan(BaseModel):
    """Output of the Architect meta-agent: the graph plus its rationale."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    objective: str = Field(min_length=10)
    intent: str
    difficulty: Literal["trivial", "moderate", "complex"]
    agents: tuple[AgentConfig, ...] = Field(min_length=1)
    edges: tuple[tuple[str, str], ...] = ()
    tasks: tuple[TaskDecomposition, ...] = ()
    max_supersteps: int = Field(default=10, ge=1, le=100)
    rationale: str = ""
```

### 3.4 Routing models — `models/routing.py`

```python
class ModelCard(BaseModel):
    """Externalised capability/cost/latency description of one model."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    name: str
    provider: str
    description: str
    capabilities: tuple[str, ...] = ()
    context_window: int = Field(gt=0)
    cost_per_1k_input_usd: float = Field(ge=0.0)
    cost_per_1k_output_usd: float = Field(ge=0.0)
    latency_p50_ms: int = Field(ge=0)
    quality_score: float = Field(ge=0.0, le=1.0)
    fallbacks: tuple[str, ...] = ()


class TaskSemantics(BaseModel):
    """What the router knows about the task it must place."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: str
    difficulty: Literal["trivial", "moderate", "complex"]
    required_capabilities: tuple[str, ...] = ()
    estimated_input_tokens: int = Field(default=0, ge=0)
    estimated_output_tokens: int = Field(default=0, ge=0)
    embedding: tuple[float, ...] | None = None


class RoutingContext(BaseModel):
    """Everything a `BaseRouter.select_model` call is allowed to consider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    task: TaskSemantics
    candidates: tuple[ModelCard, ...] = ()
    explicit_model: str | None = None
    tenant_id: str = "default"


class RoutingResult(BaseModel):
    """The router's decision, always explainable."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_name: str
    strategy: Literal[
        "explicit", "semantic", "algorithmic", "composite", "user_function", "fallback"
    ]
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    fallbacks: tuple[str, ...] = ()
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
```

### 3.5 Result models — `models/result.py` and `models/tool.py`

```python
class RunResult(BaseModel):
    """Terminal (or paused) outcome of a run, identical across runtimes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run_id: str
    status: RunStatus
    final_answer: str
    supersteps: int = Field(ge=0)
    messages: tuple[Message, ...] = ()
    state: AgentState
    trust_score: float = Field(ge=0.0, le=1.0)
    error_code: str | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ToolResult(BaseModel):
    """Normalised outcome of one AUB or MCP tool invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    ok: bool
    output: JSONValue = None
    error_code: str | None = None
    error: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    redacted: bool = False
```

`RunResult.final_answer` MUST be the concatenation, in message order, of the `content` of every message with `kind == "answer"`. It is derived, never independently authored.

---

## 4. Compatibility surface

Models in the compatibility surface follow the SemVer policy in [04-public-api.md](04-public-api.md): fields are never removed or narrowed within a major version; new fields MUST be optional with a default.

| Model | Compatibility surface | Notes |
|---|---|---|
| `AgentState` | Yes | Serialised into checkpoints; changes require a schema-version bump and a migration. |
| `Message`, `Performative`, `RunStatus` | Yes | `RunStatus` values are also the remote contract's status vocabulary. |
| `StateUpdate` | Yes | The agent extension contract; see [07-extensibility.md](07-extensibility.md). |
| `AgentConfig`, `AgentPersona` | Yes | Authored directly by users of the `Swarm` builder. |
| `ExecutionPlan`, `TaskDecomposition` | Yes | Serialised and replayable. |
| `ModelCard`, `TaskSemantics`, `RoutingContext`, `RoutingResult` | Yes | The custom-router contract. |
| `RunResult`, `ToolResult` | Yes | Returned by every public entry point. |
| `AgentDescriptor` | No (0.x) | Taxonomy shape may change until 1.0; document changes in the changelog. |
| Anything under `core/`, `services/`, `providers/` not listed above | No | Internal; may change in any release. |

## 5. Bitemporality and immutability

- **Valid time** — when a fact was true in the world — lives on `Message.valid_time` and `StateUpdate.valid_time`. It is set by the emitting agent's activity from the injected clock.
- **Transaction time** — when the kernel recorded the fact — lives on `AgentState.transaction_time`, stamped once per barrier by the runtime.
- Together they answer "what did the agent know at the moment it decided?" independently of later corrections. `persistence/` MUST preserve both on every node it writes.
- Every model above is `frozen=True`. Agents receive a frozen snapshot and return `StateUpdate` deltas; the barrier constructs the next `AgentState` with `model_copy(update=...)`. In-place mutation of shared state is a defect, not a style choice.
- Mutable-looking container fields use `tuple[...]` rather than `list[...]` so freezing is real and hashing is possible. `Mapping[str, JSONValue]` fields MUST be treated as read-only; reducers replace them rather than mutate them.
- `extra="forbid"` everywhere: an unrecognised field is a validation error, not silently dropped data.
