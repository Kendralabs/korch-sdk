# Parity Matrix — Python ↔ TypeScript Remote Client

**Purpose:** Settle the TypeScript client's contract now, from the Python reference
implementation, so that when it is built (per ADR 0008's re-entry condition, `docs/adr/0008-
typescript-client-deferred.md` in the repository — excluded from the published site alongside the
rest of `docs/adr/`) the work is translation, not negotiation.
**Status:** Every TypeScript entry is **`TS: planned`** — none of it exists in this repository.
There is no `clients/typescript/` directory and no npm package.
**Owner/status:** SDK maintainers · Normative for the TS client's eventual shape · last reviewed
2026-07-23 (P9.8, alongside `korchestrator.remote`'s Python implementation completing in P9.1–P9.7).

## How to read this

- **Python** is the actual, shipped signature (`korchestrator.remote.KorchestratorClient`,
  `[remote]` extra).
- **TypeScript (planned)** is the settled intended name/signature — camelCase per ADR 0008,
  otherwise identical semantics unless a **Note** says otherwise.
- Every row is `TS: planned`. There are no partial or in-progress rows in this matrix — the
  TypeScript client has not been started.
- Where the original TS-facing design sketch (spec 04 §7, as summarized in ADR 0008's context)
  disagreed with what the Python reference implementation actually does, **the Python
  implementation wins** — ADR 0008 states this reconciliation rule explicitly ("Where the spec and
  the Python client disagree, the discrepancy is resolved and the spec updated"). Each such case is
  called out in a Note.

## Constructor

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `KorchestratorClient(base_url, *, api_key=None, timeout=30.0, max_retries=3)` | `new KorchestratorClient(baseUrl, { apiKey?, timeout?, maxRetries? })` | `TS: planned` | One `apiKey` option covers both a static key and a Keycloak/KIAM JWT (spec 04 §7.2 — one `Authorization: Bearer` header, one code path). An earlier TS-facing sketch split this into mutually exclusive `apiKey`/`accessToken` options; the Python implementation's single-parameter shape is authoritative per ADR 0008's reconciliation rule, and the TS options object should follow it. |
| `client.close()` / `await client.aclose()` | `client.close()` (sync) / `await client.close()` (async overload), or a single `async dispose()` under `Symbol.asyncDispose` | `TS: planned` | Python offers both a sync and an async close because Python has no native async-dispose protocol convention as ubiquitous as JS's; TS should prefer `await using client = new KorchestratorClient(...)` (`Symbol.asyncDispose`) as the idiomatic equivalent of Python's `async with`. |
| `async with KorchestratorClient(...) as client:` | `await using client = new KorchestratorClient(...)` | `TS: planned` | |

## Run lifecycle (spec 04 §7.3/§7.4)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `run(objective, *, max_supersteps=10, mock_mode=False, tenant_id=None, timeout=None) -> RemoteRunResult` | `run(objective, options?) -> Promise<RemoteRunResult>` | `TS: planned` | Python's keyword-only optional args become one `options` object, per the naming vocabulary's `run` (never `execute`/`launch`/`invoke`/`start`). |
| `run_swarm(agents, edges=(), *, objective, max_supersteps=10, tenant_id=None, timeout=None) -> RemoteRunResult` | `runSwarm(agents, edges, options?) -> Promise<RemoteRunResult>` | `TS: planned` | `agents: AgentConfig[]`; `edges: [string, string][]`. |
| `get_run(run_id, *, timeout=None) -> RemoteRunResult` | `getRun(runId, options?) -> Promise<RemoteRunResult>` | `TS: planned` | |
| `wait(run_id, *, poll_interval=2.0, timeout=None) -> RemoteRunResult` | `wait(runId, options?) -> Promise<RemoteRunResult>` | `TS: planned` | Polls `getRun` until terminal, same as Python; does not return early on `governance_paused`. |
| `run_and_wait(objective, *, max_supersteps=10, mock_mode=False, tenant_id=None, poll_interval=2.0, timeout=None) -> RemoteRunResult` | `runAndWait(objective, options?) -> Promise<RemoteRunResult>` | `TS: planned` | Naming vocabulary: `run_and_wait`, never `run_sync`/`await_result`. |
| `list_runs(*, tenant_id=None, timeout=None) -> tuple[RunSummary, ...]` | `listRuns(options?) -> Promise<RunSummary[]>` | `TS: planned` | |
| `get_run_summary(run_id, *, timeout=None) -> RunSummary` | `getRunSummary(runId, options?) -> Promise<RunSummary>` | `TS: planned` | |

## Control (spec 04 §7.3)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `resume(run_id, *, timeout=None) -> RemoteRunResult` | `resume(runId, options?) -> Promise<RemoteRunResult>` | `TS: planned` | |
| `cancel(run_id, *, timeout=None) -> RemoteRunResult` | `cancel(runId, options?) -> Promise<RemoteRunResult>` | `TS: planned` | |
| `edit_resume(run_id, *, updates=None, trust_delta=0.0, timeout=None) -> RemoteRunResult` | `editResume(runId, options?) -> Promise<RemoteRunResult>` | `TS: planned` | `updates?: Record<string, JSONValue>`. |

## Identity and usage (spec 04 §7.3)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `me(*, timeout=None) -> CallerIdentity` | `me(options?) -> Promise<CallerIdentity>` | `TS: planned` | |
| `my_quota(*, timeout=None) -> Quota` | `myQuota(options?) -> Promise<Quota>` | `TS: planned` | |
| `my_runs(*, timeout=None) -> tuple[RunSummary, ...]` | `myRuns(options?) -> Promise<RunSummary[]>` | `TS: planned` | |

## Key management (spec 04 §7.3, `korchestrator:admin` scope)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `create_key(*, scopes=(), timeout=None) -> ApiKey` | `createKey(options?) -> Promise<ApiKey>` | `TS: planned` | `ApiKey.key` is a `SecretStr` in Python (never logged/printed by default); the TS `ApiKey.key` is a plain `string` since JS has no comparable wrapper type in common use — callers must be told explicitly (JSDoc) not to log it. |
| `list_keys(*, timeout=None) -> tuple[ApiKeySummary, ...]` | `listKeys(options?) -> Promise<ApiKeySummary[]>` | `TS: planned` | Never carries the secret, in either language. |
| `revoke_key(key_id, *, timeout=None) -> None` | `revokeKey(keyId, options?) -> Promise<void>` | `TS: planned` | |

## Discovery (spec 04 §7.3)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `tools(*, timeout=None) -> tuple[ToolDescriptor, ...]` | `tools(options?) -> Promise<ToolDescriptor[]>` | `TS: planned` | |
| `models(*, timeout=None) -> tuple[ModelCard, ...]` | `models(options?) -> Promise<ModelCard[]>` | `TS: planned` | Python reuses the local kernel's own `ModelCard`; TS should define one `ModelCard` type shared the same way, not a second shape. |
| `swarm_templates(*, timeout=None) -> tuple[SwarmTemplate, ...]` | `swarmTemplates(options?) -> Promise<SwarmTemplate[]>` | `TS: planned` | |

## Streaming (spec 04 §7.3/§7.5)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `stream(run_id, *, timeout=None) -> AsyncIterator[RunEvent]` (native async generator — the one method that is not a sync wrapper) | `stream(runId, options?): AsyncIterable<RunEvent>` | `TS: planned` | Idiomatic in both languages: `async for event of client.stream(runId)` / `for await (const event of client.stream(runId))`. Python's reconnect semantics (full-jitter backoff, retry budget reset per successful reconnect, no `Last-Event-ID` resumption — the wire format carries no event id) must be matched exactly; this is a documented limitation, not a Python-specific shortcut, so the TS client should not silently promise more than Python delivers. |

## Errors (spec 04 §7.5)

| Python | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `korchestrator.exceptions.ApiError(message, *, status, code=None, trace_id=None)` — a `KorchError` subclass with `.status: int`, `.code: str`, `.trace_id: str \| None` | `class ApiError extends KorchError { status: number; code: string; traceId?: string }` | `TS: planned` | One error type for every failed `KorchestratorClient` call in both languages — never a raw transport (`httpx`/`fetch`) exception. `NetworkError`/`TimeoutError` (Python) cover connection-level failures (no response received) the same way in both languages — a real response with a non-2xx status is always `ApiError`; a dropped connection is `NetworkError`/its TS equivalent. |
| `KorchestratorClient._request`'s retry policy: 3 attempts, full-jitter exponential backoff, retry on `429`/`502`/`503`/`504` and connection failures, never any other `4xx` | Same policy, same status codes | `TS: planned` | ADR 0008's own context section mentions "retry on 429 and 503 but never 4xx" — an earlier, less precise sketch. Spec 04 §7.5's `429`/`502`/`503`/`504` list is what the Python client actually implements and is authoritative; the TS client should match the Python behavior, not the ADR's paraphrase. |

## Models (spec 05, spec 04 §7)

| Python (`korchestrator.models.remote` / `korchestrator.models.routing`) | TypeScript (planned) | Status | Notes |
|---|---|---|---|
| `RemoteRunResult` | `RemoteRunResult` | `TS: planned` | `status` is the normalized string `RunStatus`, never the engine's raw numeric code, in both languages. |
| `RunSummary` | `RunSummary` | `TS: planned` | |
| `RunEvent` | `RunEvent` | `TS: planned` | |
| `CallerIdentity` | `CallerIdentity` | `TS: planned` | |
| `Quota` | `Quota` | `TS: planned` | |
| `ApiKey` | `ApiKey` | `TS: planned` | See the key-management note above re: `SecretStr` vs plain `string`. |
| `ApiKeySummary` | `ApiKeySummary` | `TS: planned` | |
| `ToolDescriptor` | `ToolDescriptor` | `TS: planned` | `input_schema` (not `schema` — reserved by Python's `pydantic.BaseModel`); TS has no equivalent reservation, but `inputSchema` should still be used for cross-language consistency. |
| `SwarmTemplate` | `SwarmTemplate` | `TS: planned` | |

## Re-entry condition

Per ADR 0008, building the TypeScript client requires **both**:

1. A named consumer needs it (a specific product/partner use case).
2. The remote contract above has been stable across at least one minor release — no breaking
   change to endpoints, auth, error shape, or method vocabulary.

Until then, this document is the settled target — not a promise of a delivery date.
