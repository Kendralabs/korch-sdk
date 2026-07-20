# 08 — Configuration and Cross-Cutting Concerns

**Purpose:** Specify the seven foundations every module depends on — configuration, errors, logging, telemetry, security, serialization, validation — as one coherent, testable contract.
**Owner/status:** SDK maintainers · Normative · last reviewed 2026-07-20.

Read this before adding a setting, an exception, a log line, a span, a serializer, or any validation.

## Contents

1. [Configuration](#1-configuration)
2. [Error handling](#2-error-handling)
3. [Logging](#3-logging)
4. [Telemetry](#4-telemetry)
5. [Security](#5-security)
6. [Serialization](#6-serialization)
7. [Validation](#7-validation)

Module boundaries are fixed in [05-modules-and-data-models.md](05-modules-and-data-models.md); the runtime behaviour these settings select is specified in [06-execution-model.md](06-execution-model.md).

---

## 1. Configuration

### 1.1 One `Settings`, one reader

There is exactly one configuration object, `korchestrator.config.Settings`, built on `pydantic-settings`. `config/` is the **only** package that may read `os.environ`, `os.getenv`, or a `.env` file. Every other module receives configuration by injection.

**Precedence, highest first:** explicit argument → environment variable → `.env` file → declared default.

Zero-config behaviour: with no environment at all, the SDK runs locally with `MockLM` as the gateway, `local` as the runtime, in-memory persistence, explicit routing, logging off and telemetry off. `pip install korchestrator` followed by the Tier-1 one-liner in [04-public-api.md](04-public-api.md) MUST work with no configuration.

### 1.2 `configure()`

```python
from korchestrator.config import configure, get_settings

configure(mock_llm=True, korch_runtime="local", governance_trust_threshold=0.7)
settings = get_settings()
```

Whether `configure` / `get_settings` are additionally re-exported at the top level is governed by `__all__` in [04-public-api.md](04-public-api.md); the submodule path above is always valid.

- `configure(**overrides)` builds a new `Settings`, validates it, and installs it as the process default. Invalid values raise `ValidationError` immediately — never at first use.
- `get_settings()` returns the installed instance, constructing the default one on first call. It is cached; `configure()` is the only way to replace it.
- `configure()` MUST NOT be called from inside a superstep. Tests use the `settings` fixture, which restores the previous instance on teardown so no test leaks state into another.

### 1.3 Environment variables

Every variable below is recognised by `Settings` and by nothing else.

| Variable | Type | Default | Consumed by |
|---|---|---|---|
| `MOCK_LLM` | `bool` | `true` when no gateway key is present, else `false` | `providers/`, `agents/` |
| `KENDRA_AI_GATEWAY_URL` | `str \| None` | `None` | `providers/` |
| `LLM_GATEWAY_URL` | `str \| None` | `None` (alias fallback for the above) | `providers/` |
| `KENDRA_GATEWAY_API_KEY` | `SecretStr \| None` | `None` | `providers/` |
| `GOVERNANCE_TRUST_THRESHOLD` | `float` (0.0–1.0) | `0.5` | `governance/` |
| `PERSISTENCE_BACKEND` | `Literal["none","memory","kcg"]` | `"memory"` | `persistence/` |
| `ROUTING_STRATEGY` | `Literal["explicit","semantic","algorithmic","composite"]` | `"explicit"` | `routing/` |
| `AGENT_MODEL_MAP` | `dict[str, str]` (JSON) | `{}` | `routing/` |
| `ROUTING_WEIGHTS` | `dict[str, float]` (JSON) | `{"quality": 0.5, "cost": 0.3, "latency": 0.2}` | `routing/` |
| `ROUTING_PRIORITY_ORDER` | `tuple[str, ...]` (CSV) | `("explicit","algorithmic","fallback")` | `routing/` |
| `EMBEDDING_PROVIDER` | `str \| None` | `None` | `routing/` (`[routing]` extra) |
| `MODELCARD_SOURCE` | `Literal["builtin","file","url"]` | `"builtin"` | `routing/` |
| `MODELCARD_PATH` | `str \| None` | `None` | `routing/` |
| `MODELCARD_URL` | `str \| None` | `None` | `routing/` |
| `MODELCARD_CACHE_TTL_SECONDS` | `int` | `900` | `routing/` |
| `KORCH_RUNTIME` | `Literal["local","temporal"]` | `"local"` | `runtime/` |
| `KORCH_MAX_SUPERSTEPS` | `int` (1–100) | `10` | `core/`, `runtime/` |
| `KORCH_PLUGINS_ENABLED` | `bool` | `false` | `services/` |
| `KORCH_LOG_LEVEL` | `str` | `"WARNING"` | `logging/` |
| `KORCH_TELEMETRY_ENABLED` | `bool` | `false` | `telemetry/` |
| `KORCH_ENGINE_URL` | `str \| None` | `None` | `clients/` |
| `KORCH_ENGINE_API_KEY` | `SecretStr \| None` | `None` | `clients/` |
| `KORCH_ENGINE_NAMESPACE` | `str` | `"default"` | `clients/` |
| `KORCH_ENGINE_TASK_QUEUE` | `str` | `"korchestrator"` | `clients/` |
| `TEMPORAL_ADDRESS` | `str` | `"localhost:7233"` | `runtime/temporal_runtime.py` |
| `TEMPORAL_NAMESPACE` | `str` | `"default"` | `runtime/temporal_runtime.py` |
| `TEMPORAL_TASK_QUEUE` | `str` | `"korchestrator"` | `runtime/temporal_runtime.py` |
| `TEMPORAL_API_KEY` | `SecretStr \| None` | `None` (set ⇒ TLS) | `runtime/temporal_runtime.py` |
| `TEMPORAL_HITL_TIMEOUT_SECONDS` | `int` | `86400` | `runtime/temporal_runtime.py` |

Every secret-bearing field MUST be typed `SecretStr`. `Settings.__repr__` and any serialization of `Settings` MUST render secrets as `**********`.

### 1.4 The enforcement test

`tests/unit/test_config_isolation.py` MUST fail the build when environment access escapes `config/`:

```python
import pathlib
import re

FORBIDDEN = re.compile(r"\b(os\.environ|os\.getenv|load_dotenv|dotenv_values)\b")


def test_environment_is_read_only_inside_config() -> None:
    package = pathlib.Path("src/korchestrator")
    offenders = [
        str(path)
        for path in package.rglob("*.py")
        if path.parts[2] != "config" and FORBIDDEN.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"environment read outside config/: {offenders}"
```

---

## 2. Error handling

### 2.1 The tree

Everything catchable descends from `KorchError`. There is exactly one error base in the package.

```text
KorchError
├── ConfigurationError          KORCH_CONFIG_INVALID
├── ValidationError             KORCH_VALIDATION_FAILED
├── AuthError                   KORCH_AUTH_FAILED / KORCH_AUTH_FORBIDDEN
├── NetworkError                KORCH_NETWORK_UNAVAILABLE
├── TimeoutError                KORCH_TIMEOUT
├── RateLimitError              KORCH_RATE_LIMITED
├── QuotaExceededError          KORCH_QUOTA_EXCEEDED
├── ProviderError               KORCH_PROVIDER_FAILED
├── RoutingError                KORCH_ROUTING_FAILED / ROUTING_NO_CANDIDATES
├── ToolError                   TOOL_NOT_FOUND / TOOL_ACCESS_DENIED / NOT_IMPLEMENTED
├── GovernanceHaltError         KORCH_GOVERNANCE_HALT
├── RunFailedError              KORCH_RUN_FAILED
└── RunTimeoutError             KORCH_RUN_TIMEOUT
```

`korchestrator.TimeoutError` deliberately shadows the builtin inside the package namespace; it MUST subclass `KorchError` only, and modules MUST import it explicitly (`from korchestrator.exceptions import TimeoutError`) so the shadowing is visible at the import site.

```python
class KorchError(Exception):
    """Base class for every error the SDK raises."""

    default_code: str = "KORCH_ERROR"

    def __init__(self, message: str, *, code: str | None = None, **context: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.context = context
```

`code` values live in `constants/error_codes.py`. They are part of the compatibility surface: a code is never renamed or reused within a major version.

### 2.2 The wrapping rule

No raw `temporalio`, `httpx`, `dspy`, database-driver, or MCP exception may cross a module boundary. Wrap at the layer that owns the dependency, always with `raise ... from exc`:

```python
async def complete(self, *, model: str, prompt: str, max_tokens: int = 1024) -> str:
    import httpx

    try:
        response = await self._client.post("/v1/completions", json={...})
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise TimeoutError(
            f"Gateway did not respond within {self._timeout}s for model {model!r}. "
            "Increase timeout_seconds or check gateway availability.",
            code="KORCH_TIMEOUT",
            model=model,
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(
            f"Gateway call failed for model {model!r}: {exc}. "
            "Verify KENDRA_AI_GATEWAY_URL and KENDRA_GATEWAY_API_KEY.",
            code="KORCH_PROVIDER_FAILED",
            model=model,
        ) from exc
    return str(response.json()["choices"][0]["text"])
```

`tests/unit/test_error_wrapping.py` MUST assert that every public entry point, when its dependency raises, surfaces a `KorchError` subclass with a non-empty `code` and a `__cause__`.

### 2.3 Actionable messages

A message states **what failed**, **which value was involved**, and **what to do**. It never includes a secret or a full prompt.

| Bad | Good |
|---|---|
| `"Invalid configuration"` | `"ROUTING_STRATEGY='sematic' is not recognised. Valid values: explicit, semantic, algorithmic, composite."` |
| `"Request failed"` | `"Gateway returned 429 for model 'gpt-4o-mini' after 3 attempts. Reduce concurrency or raise the tenant rate limit."` |
| `"Tool error"` | `"Tool 'crm.lookup' is not mounted on agent 'analyst'. Add it to AgentConfig.tools or register the connector."` |
| `"Auth failed: token=eyJhbGci…"` | `"Authentication failed (401). Check the API key passed to KorchestratorClient; keys are never read from disk."` |

---

## 3. Logging

- One logger: `logging.getLogger("korchestrator")`, configured once in `logging/` with a `NullHandler` attached. Submodules use `logging.getLogger("korchestrator.routing")` and similar children.
- **Off by default.** The SDK adds no handler beyond the `NullHandler`, sets no level on the root logger, and MUST NOT call `logging.basicConfig()`. An embedding application's logging configuration is never modified.
- `enable_logging(level: str = "INFO", *, stream: TextIO | None = None) -> None` attaches a single `StreamHandler` to the `korchestrator` logger, is idempotent, and is the only supported way the SDK writes logs. `disable_logging()` removes it.
- **No `print()` anywhere in `src/`.** Enforced by a ruff rule (`T20`).
- Structured fields go through `extra=`, never string interpolation of variable data: `run_id`, `tenant_id`, `superstep`, `agent_id`, `event`, `outcome`, `duration_ms`, `trace_id`.
- **Never logged:** API keys, JWTs, `SecretStr` values, raw prompts, raw model completions, tool arguments before redaction, or personal data. Log identifiers and lengths instead of content.
- Level guidance: `DEBUG` for kernel internals, `INFO` for superstep and run lifecycle, `WARNING` for degraded-but-continuing (skipped plugin, MCP server unreachable, hook raised), `ERROR` for a failed run.

---

## 4. Telemetry

- Optional, behind the `[otel]` extra and `KORCH_TELEMETRY_ENABLED` (default `false`). OTel packages are imported inside `telemetry/` functions only.
- **Zero overhead when off.** With telemetry disabled, `start_span()` returns a module-level no-op singleton; no context manager allocation, no attribute dictionary construction, no import of the OTel SDK. A benchmark in `benchmarks/` MUST record the delta between telemetry-on and telemetry-off for a fixed swarm and assert the off-path is within noise of a build with the extra uninstalled.
- Span tree, following the OpenTelemetry GenAI conventions:

```text
agent.run                (one per run; attributes: run_id, tenant_id, supersteps, status)
└── agent.superstep      (one per superstep; attributes: superstep, active_agents)
    └── agent.plan       (planning/reasoning for one agent; attributes: agent_id, intent)
        ├── tool.call    (attributes: tool.name, tool.ok, duration_ms)
        └── gen_ai.call  (attributes: gen_ai.request.model, token counts — never prompt text)
```

- Metrics: `korch.run.duration`, `korch.superstep.duration`, `korch.agents.active`, `korch.tool.calls`, `korch.model.tokens`, `korch.run.status` (counter by status). Metric attributes MUST be low-cardinality — never `run_id`.
- Span attributes MUST NOT carry prompts, completions, tool arguments or personal data. Telemetry is subject to the same redaction rules as logging.

---

## 5. Security

- **Secrets.** Read only through `Settings` as `SecretStr`. Never written to disk, never placed in a span or log record, never included in an exception message or `KorchError.context`. Only `.env.example` with inert placeholder values is tracked in git.
- **Redaction (Shield).** One consolidated redactor in `security/`. It masks detected entities to `[MASKED_<TYPE>]` — `[MASKED_PAN]`, `[MASKED_IBAN]`, `[MASKED_PHONE]`, `[MASKED_SSN]`, `[MASKED_EMAIL]`, `[MASKED_SECRET]`. Coverage MUST include card numbers validated by Luhn, IBAN, international phone formats, national identifiers, and common credential patterns. A second redactor anywhere in the package is a review rejection.
- **Where redaction applies.** On the ingest path before anything reaches persistence, telemetry, logs, or an event subscriber. `ToolResult.redacted` records that masking occurred.
- **Fail closed.** For flows marked high-sensitivity, if the redactor, policy engine, or identity provider is unavailable or times out, the operation is **denied** — never allowed through unredacted. `governance/` returns a pause or a `GovernanceHaltError`; it never degrades to permissive.
- **Development fallbacks are explicit and observable.** The local unsecured `IIdentityProvider` MUST log a `WARNING` on construction and MUST be rejected when `KORCH_RUNTIME=temporal` with a configured `TEMPORAL_API_KEY`, so an unsecured identity cannot silently reach a durable multi-tenant deployment.
- **Input validation.** Every identifier crossing a boundary is validated against an allowlist pattern before use — agent ids, tool names, tenant ids, run ids. No identifier is interpolated into a path, command, or query without validation; structured APIs are preferred to string building everywhere.
- **Output sanitization.** Model and tool output is untrusted input. It is validated against the expected schema, redacted, and never executed, `eval`'d, or used to construct a file path or command.
- **Tenancy.** `tenant_id` is mandatory data on state, checkpoints and repository calls. A repository method without a tenant scope is a defect.

---

## 6. Serialization

`serializers/` provides deterministic, version-tagged round-trip for `AgentState`, `AgentGraph`, `ExecutionPlan`, `ModelCard` and `RunResult`, across object ⇄ dict ⇄ JSON ⇄ YAML.

```python
from korchestrator import from_json, to_json
from korchestrator.models import RunResult

payload: str = to_json(result)
restored: RunResult = from_json(payload, RunResult)
assert to_json(restored) == payload  # byte-stable round trip
```

Requirements, each with a test:

1. **Deterministic output.** Keys sorted, separators fixed (`(",", ":")`), no trailing whitespace, `ensure_ascii=False`, UTF-8. Sets and unordered mappings are sorted before emission. Serialising the same object twice MUST produce identical bytes.
2. **Version tag.** Every serialised envelope carries `schema_version: int` and `korchestrator_version: str`. The schema version is what migrations key on; the package version is diagnostic only.
3. **Timestamps** are ISO-8601 with an explicit UTC offset, microsecond precision, never a bare epoch float.
4. **Floats** are emitted with `repr` round-trip fidelity; no locale-dependent formatting.
5. **Migration rule.** A change to a model's serialised shape that older payloads cannot satisfy REQUIRES a `schema_version` bump plus an upgrade function `migrate_<model>_v<n>_to_v<n+1>`. `from_json` applies migrations in sequence up to the current version. Loading a payload with a **higher** schema version than the installed package raises `ValidationError` with the two versions in the message — it never guesses.
6. **Additive changes** (a new optional field with a default) do not bump the schema version; a golden-file test MUST prove an old payload still loads.
7. Golden fixtures for each model live in `tests/fixtures/serde/` and are asserted byte-for-byte, so an accidental ordering or formatting change fails the build.

---

## 7. Validation

Validation is fail-fast: reject at the boundary with an actionable `ValidationError`, before any model call, tool call or checkpoint is written.

| Trust boundary | Validated | Enforced in |
|---|---|---|
| Public façade arguments | `objective` ≥ 10 characters; `max_supersteps` in 1–100; agent ids unique and pattern-matching | `services/`, `validators/` |
| Settings construction | Types, ranges, enum membership, mutually exclusive credentials | `config/` |
| Graph construction | ≥ 1 node; every edge endpoint resolvable; no duplicate node id; no self-edge unless permitted | `core/graph.py` |
| Agent output | `StateUpdate` is a valid model; `agent_id` matches the emitting node; message senders match | `core/pregel.py` |
| Routing | Selected model is resolvable in the candidate set or a declared fallback | `routing/` |
| Tool invocation | Arguments validated against the connector's JSON schema; tool mounted on the calling agent | `tools/bridge.py` |
| MCP responses | Tool descriptors conform to the expected schema; unknown fields rejected | `mcp/` |
| Remote responses | Deserialised into typed models with `extra="forbid"`; status normalised to `RunStatus` | `clients/` |
| Deserialization | Schema version supported; envelope well-formed | `serializers/` |

Rules:

- Validation happens **once**, at the boundary. Interior functions assume validated input and do not re-validate defensively.
- A validation failure raises `ValidationError` with the offending field name and the accepted values. It never returns `None`, a default, or a partially valid object.
- Pydantic does the structural work; `validators/` holds only the domain rules Pydantic cannot express (graph reachability, model resolvability, tool mounting).
- No validation is skipped in production based on a flag. A development-only relaxation MUST be impossible when `KORCH_RUNTIME=temporal`.
