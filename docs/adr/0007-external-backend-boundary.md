# ADR 0007 — External backend boundary

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

A working Korchestrator engine exists outside this repository as a hosted service with a FastAPI
surface, Temporal workers, and integrations into KACP, KCG, KIAM, and KMCP (platform reference §1,
§10). That service is where the kernel logic currently lives, and it is the obvious source of code
for this SDK.

That very convenience is the risk this ADR exists to close. Every plausible way of reusing it —
importing from it, extracting a shared library, vendoring modules — reintroduces the coupling the
SDK was created to eliminate. Spec §2.7 is explicit that orchestration capability which only exists
inside a running service is reachable only by operating that service or forking it, and that neither
is a developer product. Spec §5 makes the boundary a hard rule; the golden rules in §0 make it
non-negotiable.

The pressure is not hypothetical. It arrives as reasonable-sounding requests: "just import the
existing router", "extract the shared models into a common package", "vendor the Pregel runner so we
don't rewrite it". Each is locally cheaper and globally fatal.

## Decision

**The SDK imports nothing from an application repository.** No `backend.*`, no `apps.*`, no
`services.*`, no `frontend` — as an import, a dependency in `pyproject.toml`, a test fixture, a CI
step, or a vendored copy.

**The SDK does not depend on a hosted service and is never versioned against one.** It builds,
tests, publishes, and runs with no service in existence. Every test passes offline (spec §10.1). No
CI job in this repository contacts, deploys, or waits on an engine.

**The dependency arrow points one way only.** Any hosted engine is a *downstream consumer* of the
published SDK — it installs `korchestrator` from the registry like any other user, and adds only
transport, authentication, and tenancy on top. It lives in its own repository, on its own release
cadence, and is Phase 13: out of scope, approval-gated, and never a dependency of this repository.

```
korchestrator (this repository — the product)
      ▲ consumed by
hosted engine / backend (separate repository, thin adapter)   ← Phase 13, out of scope
      ▲ called by
korchestrator.remote (this repository — speaks the wire contract, depends on no deployment)
```

Note the shape: `korchestrator.remote` (ADR 0001, ADR 0005) speaks a documented HTTP *contract*
(spec §13). Speaking a contract is not depending on an implementation — the client ships, tests, and
is useful as a specification even if no engine is ever deployed.

**Where external behaviour is genuinely needed, define the smallest interface in `interfaces/` and
inject an implementation.** This is what the ARI ports are (spec §2.8): `IIdentityProvider`,
`IExecutionSandbox`, `IModelGateway` each have a local default in this repository and a Kendra
implementation elsewhere. The port belongs here; the Kendra-specific implementation does not.

**Consequence we accept deliberately: there is no parity fallback.** Correctness is defined by
`docs/specs/` and by the tests written alongside each phase — never by diffing against the existing
engine. The engine may be consulted as a *behavioural reference* by a human reading it; it is never
imported, vendored, or made a CI dependency, and "the backend does it this way" is not an argument
that settles a design question here. The spec is.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Extract a shared core library from the backend, consumed by both** | The strongest alternative and the one that will keep being proposed. It avoids writing the kernel twice and guarantees the two systems agree, which is a genuine benefit. Rejected because it recreates the exact dependency the SDK exists to remove, one level down: the SDK's release cadence becomes bounded by the shared library's, a change needed by the backend forces a version the SDK must absorb, and the shared library inevitably accretes service concerns (auth, tenancy, transport) because that is where its other consumer lives. The SDK would once again be unable to ship on its own schedule — the failure being fixed. |
| **Vendor the relevant backend modules into `src/`** | Fastest possible start, no runtime coupling, and full control over the copy. Rejected because vendored code silently drifts from its origin with no mechanism to detect it, and ownership becomes ambiguous — a bug fixed upstream does not reach here, a bug fixed here does not reach upstream, and neither team knows the other's version. It also imports the origin's licence and header obligations into a repository with its own licence policy (ADR 0003). |
| **SDK depends on a running engine for integration tests** | Would give genuine end-to-end confidence against the real system, which offline tests cannot. Rejected because it makes CI depend on a deployment: the SDK's build breaks when someone else's service is down, and contributors cannot run the suite. Contract tests against a mocked transport (`respx`) give most of the value at none of the cost; contract verification against a live engine belongs in the *engine's* CI, running against a published SDK version. |
| **Build the backend in this repository too** ("it's all one product") | Simplifies coordination and removes the two-repository overhead entirely. Rejected as a direct violation of golden rule §0.1–§0.2 and the entire premise of the repository. It would put deployment manifests, HTTP concerns, and service infrastructure into a package whose value proposition is being embeddable and infrastructure-free. |

## Consequences

**Positive**

- The SDK builds, tests, versions, and publishes on its own cadence, blocked by nothing and no one.
- It is genuinely embeddable — a user's application takes on `pydantic` and whatever extras it
  chooses, and no service dependency.
- The contract is the interface, so a hosted engine can be rewritten, replaced, or discontinued
  without touching the SDK.
- The boundary is mechanically checkable, so it does not depend on reviewer vigilance.

**Negative**

- Kernel logic that already exists elsewhere is written again here, against the specs. That is
  duplicated effort, and it is the deliberate price of independence.
- Without a parity fallback, every behavioural question must be answered from the specs and locked
  by a test. Where the specs are silent, we decide and record — which is slower than copying.
- Divergence between this SDK and the existing engine is possible and, over time, likely. Managing
  that is the engine's problem as a downstream consumer, not ours.

**Neutral**

- The engine remains available as a behavioural reference for humans. Reading it is fine; importing
  it is not. That distinction must be stated explicitly, because it is the one people blur.
- Kendra-specific ARI implementations (KIAM, OpenSandbox, AI Gateway) live outside this repository.
  Only the ports live here.

## Compliance

- **Import-isolation gate — the primary enforcement.** Runs in CI (`ci.yml`) and locally in
  `.claude/hooks/pre-commit-check.sh` before every commit. It greps the package source for
  application-repository imports and fails on any match:

  ```
  grep -RnE "from (backend|apps|services)\.|import (backend|apps|services)\." src/korchestrator \
    && echo "ISOLATION VIOLATION" || echo "OK"
  ```

  It must print `OK`. The hook blocks the commit; the CI job blocks the merge and the release.
- **Manifest check:** `version-validate` asserts that `pyproject.toml`'s runtime dependencies contain
  only `pydantic` plus the declared extras (ADR 0004) — no path dependency, no VCS dependency, no
  private index requirement.
- **Offline test suite:** the full suite runs with no network access. Any test that reaches a socket
  fails, which structurally prevents a live-engine dependency from being introduced.
- **No service jobs:** reviewer check on `.github/workflows/` — no job may deploy, contact, or wait
  on an engine. Spec §12 Phase 12 states this as a release validation criterion.
- **Vendoring:** reviewer judgement, not automatable. A PR adding a file whose provenance is another
  repository must be rejected or accompanied by a superseding ADR.

## Rollback

Reversing this decision means making the SDK depend on an external application, which contradicts
golden rules §0.1–§0.3 and the premise of the repository. It is not a change that would be made; it
would be the decision to build a different product.

**Point of no return:** the first published release. Once users have installed a package that
depends only on `pydantic`, adding a dependency on an application repository or a hosted service is
a breaking change for every consumer — it would change the install footprint, the network
requirements, and the operational profile of every application embedding the SDK. Practically, this
boundary is permanent from the first release, which is precisely why it is enforced by a gate rather
than by convention.
