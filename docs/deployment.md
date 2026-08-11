# Deployment

**"Deployment" for this repository means publishing package artifacts, not running a service.**
There is no server, container, or environment operated from this repository, and it never will
be — see [Non-goals](https://github.com/kendralabs/korch-sdk#non-goals). This page instead covers
what matters when *your* application, which embeds Korchestrator, goes to production.

## What actually gets published

| Deliverable | Where it lands |
|---|---|
| Immutable wheel and sdist | PyPI (once Phase 12 ships — see [Releases](releases.md)) |
| SBOM, checksums, provenance attestation | The GitHub release |
| This documentation site, for the released version | GitHub Pages |

## Configuring the SDK for production

Everything is read through `Settings` — bare construction reads no environment (deterministic,
testable); `Settings.from_env()` layers `.env`, then the process environment, then explicit
overrides, in that order. The recognised environment variables are part of the compatibility
surface (see [Versioning](versioning.md)) — they don't change without a deprecation cycle.

The variables you're most likely to set in production:

| Variable | Controls |
|---|---|
| `KORCH_RUNTIME` | `local` (default) or `temporal` — see [Architecture](architecture.md#two-runtimes-one-contract) |
| `MOCK_LLM` | Defaults to `false` automatically once a gateway key is configured — set explicitly to force one way or the other |
| `KENDRA_AI_GATEWAY_URL` / `KENDRA_GATEWAY_API_KEY` | The real model gateway (`SecretStr` — never logged, never in a repr) |
| `TEMPORAL_ADDRESS` / `TEMPORAL_NAMESPACE` / `TEMPORAL_TASK_QUEUE` | Where the durable runtime connects |
| `PERSISTENCE_BACKEND` | `memory` (default) or a real graph store, if you need audit history to survive a restart |
| `KORCH_TELEMETRY_ENABLED` | Turns on OTel spans/metrics (`[otel]` extra) — zero overhead when off |
| `KORCH_LOG_LEVEL` | Attaches a handler to the `korchestrator` logger — off by default so an embedding app's own logging is never touched |

Never hardcode a credential in code you commit — inject it via the environment or your platform's
secret manager, and let `Settings.from_env()` pick it up. The SDK never writes a credential to
disk and never includes one in a log line, a repr, or an exception message; this is
[test-locked](reference/remote.md), not just documented.

## Choosing a runtime for production

- **Local runtime** — fine for a request/response service where a run completing in seconds is
  acceptable and losing an in-flight run on a crash is tolerable (e.g. it gets retried at a higher
  level).
- **Durable runtime** — the durable choice: a run survives a worker crash and resumes from its
  last checkpointed superstep, and it supports human-in-the-loop pause/resume. Requires operating
  (or subscribing to) a durable workflow engine cluster — provisioning and running that cluster is
  **your** infrastructure, not something this SDK ships or manages.

Either way, the infrastructure the SDK connects to — the workflow engine, a persistence backend, a model
gateway, MCP servers — is provisioned and operated by you, selected by configuration, and always
optional. The zero-config default runs entirely without any of it: local runtime, MockLM, in-memory
persistence.

## The remote client's contract

If your application drives a *hosted* Korchestrator engine instead of embedding the kernel
directly (`[remote]` extra, `KorchestratorClient`), its wire contract — endpoint paths,
request/response shapes, the status vocabulary, and the `Authorization: Bearer` auth scheme — is
part of the compatibility surface, versioned exactly like a Python signature. See the
[remote client reference](reference/remote.md).

## Next

- [Releases](releases.md) — what publishing actually does.
- [Troubleshooting](troubleshooting.md) — common production-configuration mistakes.
