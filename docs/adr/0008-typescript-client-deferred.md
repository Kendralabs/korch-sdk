# ADR 0008 — TypeScript client deferred

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

Spec §7.1 places a TypeScript twin at `clients/typescript/`, publishing
`@kendralabs/korchestrator-sdk`, and spec §12 Phase 9 specifies it in detail: `KorchestratorClient`
with `baseUrl` and mutually exclusive `apiKey`/`accessToken`, a 30s timeout, 3 retries with
exponential backoff, retry on 429 and 503 but never 4xx, `ApiError { status, message, code,
traceId }`, the runs API with streaming as an `AsyncIterable`, dual CJS/ESM output, `msw` tests, and
an npm publish job. platform reference §13.5 lists both a Python and a TypeScript SDK as targets,
both currently backlog.

Two facts decide the timing. First, the remote contract (spec §13) has never been implemented by any
client — the Python client is itself a Phase 9 deliverable. A contract that has not been implemented
once is not stable; the first implementation is what discovers its gaps. Second, there is no named
TypeScript consumer today. Kendra Studio, the most likely one, is itself backlog
(platform reference §15).

Building both clients simultaneously against an unimplemented contract means every contract
discovery costs two implementations, two test suites, two release pipelines, and a parity
reconciliation — before anyone has asked for the second one.

## Decision

**The TypeScript client is specified but not built in Phases 0–12.**

What that means concretely:

- **`clients/typescript/` does not exist** in the repository. Not as a stub, not as a placeholder
  package.json. An empty directory invites partial implementation.
- **There is no npm publish job** in `.github/workflows/release.yml`, and no Node toolchain in CI.
- **The contract is documented now.** The parity matrix ships as documentation from Phase 9, listing
  every Python method with its intended TypeScript name and marking each **"TS: planned"**. The
  method vocabulary (`run` / `runSwarm` / `runAndWait`), the auth scheme (ADR 0005), and the error
  shape are fixed by ADRs already, so the TS client will be built to a settled contract rather than
  a rediscovered one.
- **The Python client is the reference implementation.** Where the spec and the Python client
  disagree, the discrepancy is resolved and the spec updated — that reconciliation is precisely the
  work that must happen once, not twice.

**Re-entry condition — both must hold before the TS client is built:**

1. **A named consumer needs it.** A specific product or partner with a specific use case, not a
   general expectation that TypeScript users exist.
2. **The remote contract has been stable across at least one minor release** — meaning a minor
   release has shipped with no breaking change to the endpoints, auth, error shape, or method
   vocabulary of `korchestrator.remote`.

When both hold, the TS client is built under a superseding ADR that also settles its repository
location (see below) and its independent SemVer line (spec §10.7 permits the TS package to version
independently of the Python distribution).

**Repository location is deliberately left open.** Spec §7.1 places it in this repository, and that
remains the default because parity is far easier to enforce when both clients are reviewed in one
diff. But if the TS client grows its own release cadence, its own consumers, and its own issue
stream, a separate repository becomes the better home. The superseding ADR decides; this ADR only
records that the question is open rather than settled by the spec's current wording.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Build both clients now, in parallel** | The strongest argument for it is real: writing two implementations against one contract simultaneously is the best way to discover that the contract has language-specific assumptions baked in, and it eliminates a later parity-catch-up effort. Rejected on sequencing, not on merit. The contract is not yet stable, so every discovery would be paid for twice; the release pipeline, npm credentials, and dual CJS/ESM build are real infrastructure to build and maintain; and there is no consumer, so the entire cost is incurred before any value is realised. Deferring is reversible; the work is not wasted, only postponed. |
| **Build the TS client in a separate repository now** | Would let it move independently from day one and is the likely long-term home. Rejected *now* for the same reason as above plus one more: parity drift is much harder to catch across repositories, and parity is the property most at risk in a two-language client. Kept explicitly open as the future home — this is the one alternative recorded as unresolved rather than closed. |
| **Ship a stub `clients/typescript/` with a placeholder package.json** | Signals intent and reserves the npm name. Rejected because a stub in the tree is worse than nothing: it will be partially implemented by someone who assumes it is in progress, it appears in the repository structure as if it were a deliverable, and CI must either ignore it (rot) or build it (cost for no artefact). Reserving the npm name, if desired, is a registry action that requires no directory. |
| **Auto-generate the TS client from an OpenAPI spec of the remote contract** | Would nearly eliminate parity drift and much of the implementation cost — genuinely the most attractive technical option. Rejected as premature rather than wrong: it requires an authoritative OpenAPI document that does not yet exist, and generated clients typically miss exactly the parts spec §12 Phase 9 cares about (an idiomatic streaming `AsyncIterable`, the retry policy, JSDoc, the ergonomic error shape). Worth revisiting inside the superseding ADR. |
| **Drop the TypeScript client entirely** | Would remove a standing obligation. Rejected: TypeScript is one of two stated target languages for enterprise AI/platform teams, and Kendra Studio is a TypeScript surface. The demand is expected; only its timing is uncertain. |

## Consequences

**Positive**

- Phases 0–12 carry no Node toolchain, no npm credentials, no dual-build configuration, and no
  cross-language parity obligation. That is meaningful capacity returned to the kernel.
- The TS client, when built, targets a contract that has survived a real implementation and at least
  one release — it starts from a settled specification rather than discovering one.
- No published npm package means no npm deprecation, no abandoned-package problem, and no user
  depending on something unfinished.

**Negative**

- TypeScript consumers have no supported client and must call the HTTP API directly against the
  spec §13 contract. If a consumer appears sooner than expected, they wait or hand-roll.
- The parity matrix documents a surface that does not exist, which is a mild credibility cost and
  must be labelled unambiguously — hence the mandatory "TS: planned" marker on every row.
- The npm name `@kendralabs/korchestrator-sdk` is unreserved unless registered separately.

**Neutral**

- Spec §7.1 shows `clients/typescript/` in the repository layout. That section describes the target
  structure; this ADR records that the directory is not created during Phases 0–12. The spec's
  layout section cites this ADR so a reader does not mistake the absence for an omission.
- The TS package versions independently when it exists (spec §10.7); ADR 0002 governs the Python
  distribution only.

## Compliance

- **Absence is asserted, not assumed.** A CI check fails the build if `clients/typescript/` exists
  while this ADR is Accepted, and fails if any workflow file under `.github/workflows/` references
  `npm publish`, `npm`, or a Node setup action. This prevents a well-intentioned stub from landing.
- **Parity matrix labelling:** a docs test asserts that every row of the parity matrix has a
  TypeScript status of exactly `planned`, and that no documentation page instructs a user to
  `npm install @kendralabs/korchestrator-sdk`. A doc that tells users to install a nonexistent
  package is the specific failure this check prevents.
- **Contract stability tracking:** the re-entry condition is verifiable from the CHANGELOG — a minor
  release with no entry under Changed or Removed touching `korchestrator.remote` satisfies
  condition 2. Condition 1 (a named consumer) is a judgement call recorded in the superseding ADR.
- **Method vocabulary:** ADR 0001's compliance check already fixes the shared vocabulary, so the
  future TS client cannot drift on names.

## Rollback

Trivially cheap in the direction of building it. This ADR removes nothing and closes no door — it
defers work and fixes the contract the deferred work will target. Reversing it means writing a
superseding ADR (0009 or later) that records the named consumer, confirms contract stability,
decides the repository location, and re-enables the Node toolchain and publish job.

**Point of no return:** none while the client is unbuilt. One appears the moment
`@kendralabs/korchestrator-sdk` is first published to npm — from that point the package name,
version line, and public surface are a public commitment governed by spec §10.7, and npm's
unpublish policy makes a published version effectively permanent.
