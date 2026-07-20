# 04 — Public API & Compatibility Contract

**Purpose:** Define the curated public surface, the four usage tiers, the API design rules every public callable obeys, the compatibility and deprecation policy, and the remote (Tier 4) contract.
**Status:** Authoritative · **Phase:** frozen at P1; changes require an ADR and a version decision

**Read this when:** you are adding, renaming, or removing anything a user can import — or deciding whether a change is breaking.

---

## 1. The principle

> Users interact with a **small, curated surface**. Everything else is internal and may change in any release.

`korchestrator/__init__.py` exports only public names via an explicit `__all__`. There is no implicit surface: if it is not in `__all__`, not an ARI port, not a documented model, and not the remote contract, it is internal — regardless of whether it happens to be importable.

## 2. The four tiers

Every tier is reached from `from korchestrator import ...`. Tiers 1–3 run entirely inside the installed package with no network and no service. Tier 4 is the only tier that talks to anything external, and it is optional.

### Tier 1 — one-liner (local, zero infrastructure)

```python
from korchestrator import Korch

result = Korch().run("Research durable agent execution and summarize the top 3")
print(result.final_answer)
```

Works on a base install with no configuration: MockLM by default, a real model when a key is present in the environment. This is the quickstart and the smoke test, and it must never regress.

### Tier 2 — typed swarm builder

```python
from korchestrator import Swarm, Agent

swarm = (
    Swarm(objective="Review this PR for security and performance")
    .add(Agent(id="security", role="security-reviewer", model="claude-3.5-sonnet"))
    .add(Agent(id="perf", role="performance-reviewer", model="gpt-4o-mini"))
    .add(Agent(id="lead", role="review-lead"))
    .edges([("security", "lead"), ("perf", "lead")])
)
result = swarm.run(max_supersteps=5)
```

Explicit topology, per-agent model isolation, fluent and fully typed. Builder methods return `Self` so chaining type-checks.

### Tier 3 — kernel direct (embed / advanced)

```python
from korchestrator.core import PregelRunner, AgentGraph
from korchestrator.models import AgentState

runner = PregelRunner(graph=my_graph, model_gateway=my_gateway)
state: AgentState = await runner.run_superstep(state)
```

For embedding the deterministic kernel into another system. Collaborators are injected; the runner constructs nothing.

### Tier 4 — remote (drive a hosted engine) — optional, `[remote]` extra

```python
from korchestrator.remote import KorchestratorClient

client = KorchestratorClient("https://engine.example.com", api_key="sk-...")
result = client.run_and_wait("Summarize Q3 incident reports")
```

Nothing in Tiers 1–3 depends on Tier 4. The contract is in §7.

## 3. API design rules

Every public callable obeys all of these. A PR that violates one does not merge.

| # | Rule | Rationale |
|---|---|---|
| A1 | **Fully type-hinted**, `mypy --strict` clean | Autocomplete and static safety are the product |
| A2 | **Returns a typed model**, never a bare `dict` | Callers get structure, not string keys |
| A3 | **Google-style docstring with a runnable example** using MockLM or offline data | Every public name is self-documenting and the example is testable |
| A4 | **Keyword-only for optional parameters** (`*` separator) | Adding a parameter later stays non-breaking |
| A5 | **Raises only `KorchError` subclasses** | No optional dependency's exception type leaks to callers |
| A6 | **No side effects at import time** | Importing is free and safe; config is read when used |
| A7 | **Consistent vocabulary** across the whole surface | One concept, one name — see §3.1 |
| A8 | **Async-first, with a sync wrapper where it helps DX** | The kernel is async; blocking users are not punished |

### 3.1 Naming vocabulary

One concept, one name, everywhere — code, docstrings, docs, examples, error messages.

| Concept | The name | Never |
|---|---|---|
| Start work and return a result | `run` | `execute`, `launch`, `invoke`, `start` |
| Start an explicitly-built swarm | `run_swarm` | `launchSwarm`, `execute_graph` |
| Start and block until terminal | `run_and_wait` | `run_sync`, `await_result` |
| The remote client class | `KorchestratorClient` | `KOrchestratorClient`, `KendraOrchestratorClient`, `Client` |
| A run's identifier | `run_id` | `id`, `runId` (in Python), `execution_id` |
| One parallel round | `superstep` | `step`, `iteration`, `round`, `tick` |
| The agent's emitted delta | `StateUpdate` | `Delta`, `Patch`, `Result` |
| Terminal output text | `final_answer` | `output`, `answer`, `result_text` |

Casing: Python is `snake_case`; a future TypeScript twin uses the camelCase equivalent of the *same* vocabulary (`run`, `runSwarm`, `runAndWait`) — same words, idiomatic casing. See [ADR 0001](../adr/0001-package-naming-and-client-class.md).

### 3.2 Error contract

Every public callable raises only from the `KorchError` tree. Internal exceptions are wrapped with `raise ... from exc` so the cause is preserved without the type leaking:

```python
try:
    response = await self._client.post(url, json=payload)
except httpx.TimeoutException as exc:
    raise NetworkError(
        f"Request to {url} timed out after {self._timeout}s. "
        f"Increase timeout= or check that the engine is reachable."
    ) from exc
```

The full hierarchy and the actionable-message standard are in [08-configuration-and-cross-cutting.md](08-configuration-and-cross-cutting.md).

## 4. The compatibility surface

**Exactly these four things are the public API.** Everything else is internal.

1. `korchestrator.__all__` — the exported names
2. The ARI ports — `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway`, and the documented supporting protocols
3. The documented models — those marked public in [05-modules-and-data-models.md](05-modules-and-data-models.md)
4. The remote contract in §7

What is explicitly **not** public, and may change in any release: private names (`_`-prefixed), module paths not re-exported from `__init__`, the internal structure of any module, and any behaviour not covered by a test.

### 4.1 What counts as a breaking change

| Breaking (MAJOR) | Not breaking (MINOR/PATCH) |
|---|---|
| Removing or renaming a name in `__all__` | Adding a new name to `__all__` |
| Removing or renaming a public model field | Adding an optional field with a default |
| Adding a required parameter | Adding a keyword-only parameter with a default |
| Narrowing an accepted input type | Widening an accepted input type |
| Widening a returned type (callers must handle more) | Narrowing a returned type |
| Changing an exception type raised at a boundary | Adding a new subclass of an already-raised type |
| Changing a default that alters results | Changing a default that only affects performance |
| Changing the serialized schema without a version tag | Adding a version-tagged schema migration |
| Removing a supported Python version | Adding a supported Python version |

While `0.x`, a **MINOR** release may contain breaking changes — stated plainly in the README and CHANGELOG. From `1.0.0` the policy applies without exception. See [10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md).

### 4.2 The public-surface snapshot test

The compatibility surface is guarded by a test, not by vigilance:

```python
def test_public_surface_is_unchanged() -> None:
    """Fails when __all__ changes. Update the golden file DELIBERATELY,
    with a CHANGELOG entry and a version decision in the same PR.
    """
    assert sorted(korchestrator.__all__) == json.loads(
        GOLDEN.read_text()
    )["all"]
```

Changing the golden file is the moment a maintainer consciously decides "this is a MINOR addition" or "this is a MAJOR removal". That decision belongs in the PR description.

## 5. Deprecation policy

A public name is never removed without notice.

1. Emit a `DeprecationWarning` naming the replacement and the removal version.
2. Keep it working for **at least one minor release**.
3. Document the replacement, migration path, and removal version in the CHANGELOG and the migration guide.
4. Remove only in a MAJOR release (or, while `0.x`, a MINOR that says so loudly).

```python
def launch(self, objective: str) -> RunResult:
    """Deprecated alias for :meth:`run`.

    .. deprecated:: 0.4.0
        Use :meth:`run` instead. Removed in 1.0.0.
    """
    warnings.warn(
        "Korch.launch() is deprecated and will be removed in 1.0.0; use Korch.run().",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.run(objective)
```

Deprecations are tested: a test asserts the warning fires and that the old path still returns the same result as the new one.

## 6. The exported surface

`__init__.py` is a curated re-export list, not a wildcard. It contains no logic beyond imports and `__all__`.

```python
"""Korchestrator — durable multi-agent execution kernel."""

from korchestrator.config import Settings, configure
from korchestrator.exceptions import (
    AuthError, GovernanceHaltError, KorchError, MissingExtraError, NetworkError,
    ProviderError, QuotaExceededError, RateLimitError, RoutingError,
    RunFailedError, RunTimeoutError, ToolError, ValidationError,
)
from korchestrator.interfaces import (
    IDurableRuntime, IExecutionSandbox, IIdentityProvider, IModelGateway,
)
from korchestrator.logging import enable_logging
from korchestrator.models import AgentState, Message, RunResult, RunStatus, StateUpdate
from korchestrator.serializers import from_json, to_json
from korchestrator.services import Agent, Korch, Swarm
from korchestrator.version import __version__

__all__ = [
    "Agent", "AgentState", "AuthError", "GovernanceHaltError",
    "IDurableRuntime", "IExecutionSandbox", "IIdentityProvider", "IModelGateway",
    "Korch", "KorchError", "Message", "MissingExtraError", "NetworkError",
    "ProviderError", "QuotaExceededError", "RateLimitError", "RoutingError",
    "RunFailedError", "RunResult", "RunStatus", "RunTimeoutError", "Settings",
    "StateUpdate", "Swarm", "ToolError", "ValidationError", "__version__",
    "configure", "enable_logging", "from_json", "to_json",
]
```

Three notes on this list:

- `korchestrator.remote` is **not** imported here. It lives behind the `[remote]` extra, and importing it eagerly would pull `httpx` into the base install.
- The `KorchError` tree also contains `TimeoutError`, which is **deliberately not re-exported at top level** because it would shadow the builtin in any module doing `from korchestrator import *`. It is reachable as `korchestrator.exceptions.TimeoutError` and is still part of the compatibility surface. `RunTimeoutError` — the one users actually catch — is exported.
- This list grows in P8 (config, logging, serialization) and P9 (nothing — the remote client stays behind its extra). Each addition is a MINOR and updates the golden snapshot file.

## 7. Tier 4 — the remote contract

This section is the authoritative contract for the remote client. It describes the API a hosted Korchestrator engine is expected to expose; the SDK's job is to speak it correctly. It creates **no dependency on any service existing** — Tiers 1–3 are unaffected if no engine is ever deployed.

### 7.1 Concepts

| Term | Definition |
|---|---|
| `run_id` | UUID, stable for the life of the run |
| `objective` | Natural-language goal, minimum 10 characters |
| `swarm` | A directed agent graph |
| `superstep` | One parallel round |
| `message` | `type` ∈ `thought` \| `tool` \| `answer` \| `handoff` |
| `final_answer` | Concatenation of `answer` messages |
| `governance_paused` | The run is halted awaiting human input |
| `trust_score` | 0.0–1.0, persists across supersteps |
| `mock_mode` | Run with a deterministic mock model |

### 7.2 Authentication

**One scheme:** `Authorization: Bearer <api-key | KIAM JWT>`. One header carries both a static per-tenant key and a Keycloak/KIAM-issued JWT, so no second code path is needed when a tenant migrates to SSO. See [ADR 0005](../adr/0005-remote-auth-bearer-token.md).

| Scope | Grants |
|---|---|
| `korchestrator:read` | GET endpoints |
| `korchestrator:write` | POST run / resume / cancel |
| `korchestrator:admin` | Key management |

| Status | Meaning |
|---|---|
| 401 | Bad or missing credentials |
| 403 | Insufficient scope |
| 402 | Quota exceeded |

Credentials MUST never be logged, never written to disk by the SDK, and MUST be redacted from exception messages and telemetry. Tenant is derived server-side from the token and is never trusted from a client-supplied field.

### 7.3 Endpoints

| Method & path | Scope | Purpose |
|---|---|---|
| `POST /v1/run/auto` | write | Start a run; the engine plans the graph |
| `POST /v1/run/swarm` | write | Start a run with an explicit graph |
| `POST /v1/run` | write | Start a run from a raw `AgentState` |
| `GET /v1/run/{id}` | read | Full live state |
| `GET /v1/run/{id}/stream` | read | SSE event stream |
| `POST /v1/run/{id}/resume` | write | Resume a governance-paused run |
| `POST /v1/run/{id}/cancel` | write | Cancel a run |
| `POST /v1/run/{id}/edit-resume` | write | Modify state and resume |
| `GET /v1/runs` | read | List runs |
| `GET /v1/runs/{id}/summary` | read | Run summary |
| `GET /v1/me`, `/v1/me/quota`, `/v1/me/runs` | read | Caller identity and usage |
| `POST /v1/keys`, `GET /v1/keys`, `DELETE /v1/keys/{id}` | admin | Key management |
| `GET /v1/tools`, `POST /v1/tools/register` | read/write | Tool registry |
| `GET /v1/models` | read | Available models |
| `GET /v1/swarm-templates` | read | Topology presets |

### 7.4 Lifecycle and status normalization

```
started → running → (governance_paused → resume | cancel | edit-resume)
        → completed | failed | cancelled | timed_out
```

The client normalizes numeric engine statuses into the string form above: `1→running`, `2→completed`, `3→failed`, `4→cancelled`, `6→timed_out`. Callers only ever see the strings.

**Webhooks:** a single POST on terminal state carrying `run_id`, `status`, `superstep`, `completed_at`, `final_answer`, `message_count`, with a 10s timeout and **no retry**. Consumers must handle it idempotently — the SDK documents this explicitly because a missed webhook is a normal condition, not an error.

### 7.5 Client behaviour requirements

| Requirement | Value |
|---|---|
| Default timeout | 30s, overridable per call |
| Retries | 3, exponential backoff with jitter |
| Retry on | 429, 502, 503, 504, and connection errors |
| Never retry | Any other 4xx — retrying a client error is a defect |
| Streaming | SSE, exposed as an async iterator |
| Error type | `ApiError` carrying `status`, `message`, `code`, `trace_id`, as a `KorchError` subclass |
| Transport | `httpx`, both async and sync surfaces |

### 7.6 TypeScript parity

The TypeScript twin `@kendralabs/korchestrator-sdk` is **specified but deferred** — see [ADR 0008](../adr/0008-typescript-client-deferred.md). The parity matrix ships as documentation with every Python method marked `TS: planned`, so that when the client is built the contract is already settled rather than negotiated.

---

**Next:** [05-modules-and-data-models.md](05-modules-and-data-models.md) — the models this surface returns · [07-extensibility.md](07-extensibility.md) — extending without touching this surface.
