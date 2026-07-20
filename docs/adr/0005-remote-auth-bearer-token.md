# ADR 0005 — Remote auth: Bearer token

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

Spec §2.10 and §13.2 leave the remote authentication scheme open between two candidates —
`Authorization: Bearer <api-key | KIAM JWT>` and `X-API-Key: sk-...` — and require one to be chosen
in Phase 0 and implemented identically in every client. The choice must be made before the Phase 9
client is written, because auth is threaded through every request, every error mapping, every test
fixture, and every documentation snippet; changing it later touches all of them.

The forces:

- **Two credential kinds, one lifecycle.** A hosted engine issues per-tenant API keys for
  getting-started and machine-to-machine use, and accepts Keycloak/KIAM-issued JWTs for tenants on
  enterprise SSO (platform reference §9). A tenant migrating from the first to the second must not
  require a different client code path.
- **Scopes already exist.** `korchestrator:read` / `:write` / `:admin` are defined by the engine
  contract; the SDK's job is to carry the credential and map the resulting errors, not to interpret
  scopes locally.
- **Tenancy is a security boundary.** Tenant is resolved server-side from the credential. Any design
  in which the client can influence tenant selection is a privilege-escalation surface.
- **The golden rule of one implementation per concern** (spec §4) applies to auth as much as to
  routing or redaction.

## Decision

**`Authorization: Bearer <credential>` is the single authentication scheme.** One header, one code
path, in every client in every language.

**One header carries both credential kinds.** The value is either a per-tenant API key or a
KIAM-issued JWT. The client does not inspect, parse, or classify it — it is an opaque string that
the client attaches and the server validates. This is the property that makes an API-key-to-SSO
migration a configuration change for the user and a no-op for the SDK.

**Scopes** are enforced server-side: `korchestrator:read` for GET, `korchestrator:write` for
`POST /v1/run*`, `resume`, `cancel`, and `edit-resume`, and `korchestrator:admin` for key
management.

**Error mapping** is normative for every client. HTTP status → SDK exception:

| Status | Meaning | Raised |
|---|---|---|
| 401 | Missing, malformed, expired, or revoked credential | `AuthError` |
| 403 | Valid credential, insufficient scope | `AuthError` (distinct message and code) |
| 402 | Quota or wallet exhausted | `QuotaExceededError` |

**Credential handling rules — these are hard requirements, not guidance:**

- The SDK **never logs** the credential, at any log level, in any form, including truncated or
  prefixed.
- The SDK **never writes** it to disk — no cache file, no config file, no crash dump.
- It is **redacted from exception messages, exception `repr`, telemetry attributes, and span data**.
  A `KorchestratorClient` `repr` must not disclose it.
- It is supplied by argument or by `Settings` from the environment (spec §9.1); the SDK does not
  read credential files or discover credentials from ambient sources.

**Tenant is never client-supplied.** The server derives tenant from the credential. The client sends
no tenant field that the server would trust for authorisation. (A tenant *hint* for routing may
exist in the contract, but it is not an authorisation input, and the SDK documents it as such.)

## Alternatives considered

| Option | Why rejected |
|---|---|
| **`X-API-Key: sk-...`** | Slightly clearer at the wire level — the header name says exactly what it carries, and it avoids the confusion of a "Bearer" prefix on something that is not an OAuth token. It is also marginally harder to leak into a proxy log that special-cases `Authorization`. Rejected because it only carries one of the two credential kinds. The moment a tenant moves to KIAM JWTs, a second header and a second scheme must be introduced, and every client, test, doc, and error path forks. Choosing `X-API-Key` is choosing to do this work twice. |
| **Accept both, auto-detect by value shape** (JWT if it has two dots, else API key) | Maximally forgiving to users, and superficially attractive. Rejected on two grounds. It violates one-implementation-per-concern (spec §4) and doubles the auth test matrix — every auth-sensitive test must now run under both schemes — for a benefit no user actually asked for. Worse, shape-sniffing a credential is a correctness hazard: the classification can be wrong, and a wrong classification produces a confusing failure at a security boundary. `Authorization: Bearer` already accepts both values without needing to tell them apart. |
| **Client-side JWT validation** — parse and check `exp`/scopes before sending | Would give faster, clearer errors and save a round trip on an expired token. Rejected because it makes the client a second authorisation implementation whose view can diverge from the server's, requires a JWT parsing dependency in a client whose only dependency should be `httpx`, and tempts the client into trusting claims. The server is the only authority; 401 and 403 are the answer. |
| **mTLS instead of a bearer credential** | Stronger transport-level authentication, and the platform already runs an mTLS mesh internally (platform reference §9). Rejected for the *SDK client* surface: it requires certificate provisioning and rotation by every SDK user, which is a hostile getting-started experience, and it does not remove the need for a scoped application credential. mTLS remains available as an additional transport-layer control that the operator can require; it is orthogonal to this decision. |

## Consequences

**Positive**

- One code path, one test matrix, one documented scheme. A tenant migrating from API keys to SSO
  changes a configuration value and nothing else.
- Uses the standard `Authorization` header, so proxies, gateways, and observability tooling handle
  it conventionally, and users need no explanation of a bespoke header.
- Server-side tenant derivation removes an entire class of cross-tenant escalation bug from the
  client surface.

**Negative**

- `Bearer` conventionally implies an OAuth 2.0 token, so carrying a static API key under it is a
  mild abuse of the convention that will occasionally require explanation in docs.
- The client cannot give a helpful local error for an expired JWT; the user sees a 401 mapped to
  `AuthError` and must read the message. Accepted as the cost of not building a second authorisation
  implementation.

**Neutral**

- Scope enforcement is entirely server-side. The SDK documents the scopes so users can request the
  right ones, but never checks them.
- The credential is opaque to the SDK, so key rotation, expiry policy, and issuance are engine
  concerns and appear nowhere in this repository.

## Compliance

- **Single scheme:** `tests/unit/test_remote_auth.py` asserts, against a mocked transport (`respx`),
  that every request the client makes carries exactly one `Authorization: Bearer <value>` header and
  that the client emits no `X-API-Key` header under any configuration.
- **Error mapping:** the same module parametrises 401 / 403 / 402 responses and asserts the mapped
  exception type and error code, per spec §9.3.
- **No credential leakage — the load-bearing test:**
  `tests/unit/test_credential_redaction.py` constructs a client with a sentinel credential, then
  drives every failure path (connection error, timeout, 401, 500, validation error) while capturing
  all `korchestrator` log records, the exception `str` and `repr`, and the client's own `repr`. It
  asserts the sentinel appears in none of them. It additionally asserts the sentinel appears in no
  emitted telemetry attribute.
- **No disk writes:** the same suite asserts no file is created under the working directory or any
  cache path during a client session.
- **Secret scanning:** `gitleaks` runs in CI (spec §10.4) over the repository, so a credential
  committed in an example or fixture fails the build. Examples use inert placeholder values only.
- **Tenant handling:** reviewer check — no code path may send a client-supplied value that the
  documented contract treats as an authorisation input.

## Rollback

Changing the scheme after the remote client ships is a breaking change for every deployed engine and
every user of the client simultaneously, because both ends must change together. It would require a
transition period in which the engine accepts both schemes, a minor release of the client that emits
the new one, and a deprecation window per spec §10.7.

**Point of no return:** the first published release containing `korchestrator.remote`. Before that,
the scheme is a constant in one module. After it, the wire contract is public and a change is a
coordinated two-sided migration. Adding a *second* scheme later is possible but is explicitly what
this ADR exists to prevent.
