# 03 — System Architecture

**Purpose:** Define the layering, the dependency rule, the ARI port boundary, the composition root, and the architectural constraints that CI and code review enforce.
**Status:** Authoritative · **Phase:** frozen at P1; changes require an ADR

**Read this when:** you are deciding where a new module goes, whether an import is legal, or how a component gets its collaborators.

---

## 1. Architectural goals

The architecture exists to buy five specific properties. Every constraint below traces to one of them.

| Goal | Constraint that buys it |
|---|---|
| **Embeddable** — importable into any Python process, fast | `core/` is framework-free; heavy deps are lazy and confined to extras |
| **Portable** — same agent logic local or enterprise | The three ARI ports; no concrete infrastructure in inner layers |
| **Deterministic** — identical across runs and replays | Frozen snapshots, order-independent reducers, no nondeterminism in workflow scope |
| **Testable offline** — full agent path in CI with no network | MockLM as the default gateway; in-memory persistence; injected clock |
| **Evolvable** — extend without editing core | Open/closed via ports and strategies; a single composition root |

## 2. The layer model

```
┌──────────────────────────────────────────────────────────────────┐
│  services/            FAÇADE — the composition root              │
│                       Korch · Swarm · Agent builders             │
│                       The ONLY place collaborators are wired.    │
└───────────────────────────┬──────────────────────────────────────┘
                            │ depends on
┌───────────────────────────▼──────────────────────────────────────┐
│  agents/              L2 COGNITIVE — reasoning, compiled          │
│                       signatures, worker + architect agents       │
└───────────────────────────┬──────────────────────────────────────┘
                            │ depends on
┌───────────────────────────▼──────────────────────────────────────┐
│  core/                L1 KERNEL — Pregel BSP, graph, reducers     │
│                       FRAMEWORK-FREE. pydantic + stdlib only.     │
└───────────────────────────┬──────────────────────────────────────┘
                            │ depends on
┌───────────────────────────▼──────────────────────────────────────┐
│  interfaces/  models/  THE CONTRACTS — ports, protocols, DTOs     │
│                        Depend on nothing but pydantic + stdlib.   │
└──────────────────────────────────────────────────────────────────┘

FEATURE MODULES  routing · tools · mcp · a2a · governance
                 persistence · context · events · runtime · taxonomy
                 → depend INWARD on interfaces/ + models/ only
                 → NEVER on each other

ADAPTERS         providers/ · runtime/temporal_runtime.py · clients/
                 → implement interfaces/, depend inward only

LEAF UTILITIES   config · exceptions · logging · telemetry · serializers
                 validators · security · types · constants
                 → no upward dependencies, importable from anywhere
```

## 3. The dependency rule

> **Dependencies point inward. Never outward, never sideways.**

Concretely, four rules that a reviewer can check mechanically:

| # | Rule | Enforcement |
|---|---|---|
| **D1** | `core/` imports only `interfaces/`, `models/`, stdlib, `pydantic`. Never FastAPI, HTTP, Temporal, DSPy, httpx. | Import-linter contract + review |
| **D2** | Feature modules never import sibling feature modules. They meet at `interfaces/` and `models/`. | Import-linter contract + review |
| **D3** | Nothing imports from `backend`/`apps`/`services`/`frontend` (external application packages). | Isolation gate in CI and the pre-commit hook |
| **D4** | No import cycles anywhere in the package. | Import-linter contract |

Note on D3: the `services/` **directory inside this package** is the façade and is legal. The prohibition is on importing an external application package named `services`. The isolation gate matches `from services.` / `import services.` at the top level of `src/`, not `korchestrator.services`.

### 3.1 Why `core/` is framework-free

This is the single most load-bearing constraint in the architecture, so it is worth stating the payoff explicitly:

- `import korchestrator` stays fast because the base install has one dependency.
- The kernel test suite runs with **only `pydantic` installed** — which means the deterministic heart of the system is verified without any optional machinery in the way.
- The kernel can be embedded in a Temporal workflow sandbox, a notebook, a Lambda, or another framework's process without dragging in a transport stack.
- A bug in the kernel is never a bug in an integration, because the kernel cannot reach an integration.

Any PR that adds a non-pydantic import to `core/` is rejected without discussion. If the kernel appears to need external behaviour, it needs a port instead — and that port needs the abstraction test in [01-scope-and-principles.md](01-scope-and-principles.md) §5.2.

## 4. The ARI port boundary

Three ports are the only sanctioned way the SDK reaches the outside world for identity, execution, and inference.

| Port | Contract | Local default | Enterprise implementation |
|---|---|---|---|
| `IIdentityProvider` | Authenticate an agent, resolve it to a DID, expose tenant scope | `identity_local` — unsecured, single-tenant | KIAM / KACP |
| `IExecutionSandbox` | Execute tool code in isolation with a resource and time bound | `sandbox_local` — subprocess | OpenSandbox |
| `IModelGateway` | Route a reasoning request to a model and return a typed completion | `gateway_openai` / `mock_lm` | Kendra AI Gateway |

```python
from typing import Protocol
from korchestrator.models.routing import ModelCard
from korchestrator.models.state import Message


class IModelGateway(Protocol):
    """Route a reasoning request to a model.

    Implementations MUST be safe to call concurrently from within a superstep
    and MUST NOT introduce nondeterminism into workflow scope: any retry,
    timing, or sampling decision belongs inside the implementation, which the
    runtime treats as an activity boundary.
    """

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int | None = None,
    ) -> Message: ...

    async def available_models(self) -> list[ModelCard]: ...
```

**A port exists only when there is more than one real implementation.** These three qualify: each has a local default *and* an enterprise implementation, and the whole portability promise depends on the seam. Adding a fourth port requires an ADR demonstrating the same.

### 4.1 Supporting protocols

Not every seam is an ARI port. These are internal protocols with the same inward-dependency discipline:

| Protocol | Purpose | Implementations |
|---|---|---|
| `IDurableRuntime` | Drive the superstep loop with a durability guarantee | `local_runtime`, `temporal_runtime` |
| `GraphRepository` | Read/write the context graph | in-memory (default), mock, external backends (post-1.0) |
| `TenantStore` | Resolve and scope tenant data | in-memory (default) |
| `BaseRouter` | Select a model for a task | explicit, semantic, algorithmic, composite, user-function |
| `AUBConnector` | Execute a tool invocation | filesystem, search, MCP-backed, user-defined |

## 5. The composition root

**All wiring happens in `services/`. Nothing below it constructs its own collaborators.**

```python
# services/korch.py — the composition root (illustrative)
class Korch:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        model_gateway: IModelGateway | None = None,
        runtime: IDurableRuntime | None = None,
        router: BaseRouter | None = None,
        repository: GraphRepository | None = None,
    ) -> None:
        self._settings = settings or Settings()
        # Each collaborator is resolved from config exactly once, here.
        self._gateway = model_gateway or resolve_gateway(self._settings)
        self._runtime = runtime or resolve_runtime(self._settings)
        self._router = router or resolve_router(self._settings)
        self._repo = repository or resolve_repository(self._settings)
```

Consequences that follow, and that review checks:

- **`PregelRunner` never constructs a gateway.** It receives one. The kernel is therefore trivially testable with a stub.
- **No import-time singletons.** A module-level `router = SemanticRouter()` is a defect: it fires at import, reads config too early, and cannot be overridden in a test.
- **Every default is overridable by argument.** Passing an explicit collaborator always wins over config, which always wins over the built-in default.
- **`resolve_*` functions live next to the composition root**, read only from `Settings`, and are the only place a config string becomes a concrete class.

## 6. Determinism architecture

Determinism is an architectural property, not a coding habit. Three mechanisms produce it; all three are structural.

1. **Frozen snapshot.** Agents compute against an immutable view of state and emit `StateUpdate` deltas. No agent can observe another agent's partial work within a superstep, so results cannot depend on scheduling order.
2. **Order-independent reducers.** The barrier merges deltas via reducers that are associative and order-independent. `asyncio.gather` completion order therefore cannot change the result.
3. **Nondeterminism confined to activities.** Wall-clock, randomness, network I/O, and model calls live on the activity side of the runtime boundary. Workflow-path code uses the injected clock. This is what makes Temporal replay exact.

Full detail, including the reducer laws and the Pregel-to-Temporal mapping, is in [06-execution-model.md](06-execution-model.md).

## 7. Optional-dependency architecture

The base install is `pydantic` only. Everything else is an extra, and the architecture — not documentation — is what keeps it that way.

| Rule | Detail |
|---|---|
| **Confinement** | Each heavy dependency has exactly one module allowed to import it: `dspy` → `agents/`, `temporalio` → `runtime/temporal_runtime.py`, `httpx` → `clients/`, OTel → `telemetry/`, embedding libs → `routing/` |
| **Lazy import** | The import happens **inside the function that needs it**, never at module top level |
| **Graceful degradation** | A missing extra raises a `KorchError` naming the extra and the install command — never a bare `ImportError` |
| **Base-install proof** | The kernel suite passes with only `pydantic` installed; CI runs this as a distinct job |

```python
def _load_dspy():  # inside agents/worker.py
    try:
        import dspy
    except ImportError as exc:
        raise MissingExtraError(
            "The cognitive layer requires the 'dspy' extra. "
            "Install it with: pip install 'korchestrator[dspy]'"
        ) from exc
    return dspy
```

## 8. Architectural decision points and their resolutions

| Question | Resolution | Recorded in |
|---|---|---|
| One package or several distributions? | One `korchestrator` distribution with extras | [ADR 0001](../adr/0001-package-naming-and-client-class.md), [ADR 0004](../adr/0004-dependency-extras-matrix.md) |
| Where does the version live? | `src/korchestrator/version.py`, single source | [ADR 0002](../adr/0002-single-authoritative-version.md) |
| Local-only, Temporal-only, or both? | Both, behind `IDurableRuntime` | [ADR 0006](../adr/0006-runtime-split-local-and-temporal.md) |
| One activity per superstep, or a child workflow per agent? | One activity per superstep | [ADR 0006](../adr/0006-runtime-split-local-and-temporal.md) |
| How does the SDK relate to a hosted backend? | One-way: the backend consumes the published SDK | [ADR 0007](../adr/0007-external-backend-boundary.md) |
| How is the remote client authenticated? | Bearer token, one scheme | [ADR 0005](../adr/0005-remote-auth-bearer-token.md) |

## 9. How the architecture is enforced

Architecture that is only written down erodes. Each rule has a mechanical check.

| Rule | Check | Blocking |
|---|---|---|
| No application-repo imports (D3) | Isolation gate: grep over `src/` in CI + `.claude/hooks/pre-commit-check.sh` | Yes — commit and build |
| `core/` framework-free (D1) | `import-linter` forbidden contract | Yes — CI |
| No sibling imports (D2) | `import-linter` layered contract | Yes — CI |
| No cycles (D4) | `import-linter` | Yes — CI |
| Env read only in `config/` | Unit test greps the package for `os.getenv`/`os.environ` outside `config/` | Yes — CI |
| Base install works | Dedicated CI job installing without extras and running the kernel suite | Yes — CI |
| No raw internal exceptions escape | Unit tests asserting `KorchError` at every public boundary | Yes — CI |
| Public API unchanged without intent | Public-surface snapshot test over `korchestrator.__all__` | Yes — CI |

A proposed `importlinter` contract set:

```ini
[importlinter]
root_package = korchestrator

[importlinter:contract:kernel-is-framework-free]
name = core must not import frameworks or optional extras
type = forbidden
source_modules = korchestrator.core
forbidden_modules = temporalio, dspy, httpx, fastapi, opentelemetry

[importlinter:contract:layers]
name = inward-only layering
type = layers
layers =
    korchestrator.services
    korchestrator.agents
    korchestrator.core
    korchestrator.models
    korchestrator.interfaces

[importlinter:contract:features-are-independent]
name = feature modules must not import each other
type = independence
modules =
    korchestrator.routing
    korchestrator.tools
    korchestrator.mcp
    korchestrator.a2a
    korchestrator.governance
    korchestrator.persistence
    korchestrator.context
    korchestrator.events
```

---

**Next:** [04-public-api.md](04-public-api.md) — the surface users touch · [05-modules-and-data-models.md](05-modules-and-data-models.md) — what lives in each module.
