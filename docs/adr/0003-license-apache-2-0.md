# ADR 0003 — License: Apache-2.0

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

Spec §2.10 and §10.11 require the license to be chosen in Phase 0 and applied to `LICENSE` and
package metadata before the first release. This is not a formality: the license is the single
hardest decision in the repository to reverse, because reversing it requires the consent of everyone
who has contributed under the old terms.

The forces that decide it:

- **Enterprise procurement.** The stated target users are enterprise AI/platform teams and regulated
  buyers (HIPAA / SOC 2 / FCA). Their legal review reads the license before the README.
- **OEM / white-label embedding.** A stated business objective is that other companies embed the
  engine in their own products. That is a redistribution scenario, and redistribution under an
  unclear patent position is the thing acquirer counsel flags.
- **Category convention.** Infrastructure frameworks in this space — Temporal, OpenTelemetry,
  Kubernetes, Kafka — are Apache-2.0. Deviating from category convention costs adoption and invites
  questions that a conventional choice never raises.
- **Dependency compatibility.** The core dependency is `pydantic` (MIT); extras pull `dspy`,
  `temporalio`, `httpx`, and OpenTelemetry, all permissively licensed. Whatever we choose must stay
  compatible with what we depend on, and must keep that true as dependencies change.

## Decision

**The SDK is licensed under Apache License 2.0.**

Applied consistently:

- `LICENSE` at the repository root contains the unmodified Apache-2.0 text with the correct
  copyright line for Kendra Laboratories Limited.
- `pyproject.toml` declares the license in `[project]` metadata and carries the matching
  `License :: OSI Approved :: Apache Software License` classifier, so it appears correctly on the
  registry page.
- A `NOTICE` file at the repository root carries the attribution notices required by Apache-2.0 §4(d)
  for this work and for any bundled third-party material. It is included in the sdist and wheel via
  `MANIFEST.in`. It stays short — `NOTICE` is for legally required attribution, not for changelogs
  or credits.
- **Header convention:** source files carry a single-line copyright comment
  (`# Copyright (c) 2026 Kendra Laboratories Limited. SPDX-License-Identifier: Apache-2.0`). The full
  boilerplate header is not required in every file; the SPDX identifier is sufficient for automated
  scanners and keeps diffs readable.

**Third-party license compatibility is a CI concern, not a review-time hope.** The dependency scan
in CI includes a license check that fails the build when a direct or transitive dependency carries a
license incompatible with redistribution under Apache-2.0 (notably copyleft in the GPL/AGPL family,
or an unidentifiable license).

The decisive factor is Apache-2.0 §3, the express patent grant from contributors to users, together
with §3's retaliation clause. MIT grants copyright permission and is silent on patents; that silence
is what enterprise procurement repeatedly flags and what OEM embedding cannot leave unresolved.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **MIT** | Genuinely simpler, shorter, and universally understood — for a small library it would be the right call. Rejected because it contains no express patent grant. For a product whose stated distribution model includes OEM/white-label embedding by other companies, the implied-licence argument that covers MIT in practice is exactly the argument enterprise counsel refuses to accept in writing. MIT would cost us procurement cycles on every enterprise deal to save a few pages of licence text. |
| **BSD-3-Clause** | Same substantive position as MIT plus a no-endorsement clause. Same fatal gap: no patent grant. It buys nothing over MIT that matters here. |
| **Proprietary now, relicense to open source later** | Preserves maximum optionality on day one, and if the SDK never takes external contributions the relicense is a board decision and nothing more. Rejected because the cost of that path grows monotonically and irreversibly: from the first external contribution onward, relicensing requires a CLA signed in advance or per-contributor sign-off retroactively, and retroactive sign-off from contributors who have moved on is the classic project-blocking problem. Choosing openness later is far more expensive than choosing it now. |
| **BSL 1.1 or an open-core split** | A legitimate commercial strategy, and it protects against a hyperscaler running the engine as a service. Rejected *for the SDK* on two grounds. First, mechanics: a source-available or split license complicates the extras matrix (ADR 0004) and packaging, since consumers must reason about which extra falls under which terms. Second, sequencing: this is a business-model decision, and it can be layered on later for **server-side** components — the hosted engine of ADR 0007 — without changing the SDK's license. Keeping the client library permissive while monetising the server is the standard shape, and it stays available to us. |

## Consequences

**Positive**

- The express patent grant removes the most common blocker in enterprise legal review and makes OEM
  embedding contractually clean.
- Matches category convention, so the license raises no questions from developers evaluating the SDK.
- Compatible with every current and plausible dependency; permits commercial use, modification, and
  redistribution without a copyleft obligation propagating to consumers.

**Negative**

- Apache-2.0 imposes real obligations on redistributors: preserve notices, state changes, ship the
  `NOTICE` file. We inherit the duty to keep `NOTICE` accurate, and consumers inherit obligations
  they would not have under MIT.
- No protection against a third party operating a hosted service built on this SDK. That is an
  accepted cost of the permissive choice; the mitigation, if ever needed, lives on the server side.
- Once external contributions land under Apache-2.0, moving to any more restrictive license becomes
  effectively impossible without a CLA regime we have chosen not to impose.

**Neutral**

- The `NOTICE` file is a maintenance obligation, not an optional courtesy. It must be updated when
  bundled third-party material changes.
- The SPDX-identifier header convention means license scanners work without full boilerplate in
  every file, but it does require the header to actually be present.

## Compliance

- **CI license check:** the security/dependency stage of `ci.yml` runs a license scan over the
  resolved dependency set (direct and transitive, all extras) and fails on any license outside the
  permissive allowlist (Apache-2.0, MIT, BSD-2/3-Clause, ISC, PSF) or on `UNKNOWN`. Adding a
  dependency with a non-allowlisted license requires a superseding ADR, not a suppression.
- **Metadata check:** `version-validate` additionally asserts that the built wheel's metadata
  declares Apache-2.0 and that the `LICENSE` file is present in both the sdist and the wheel.
- **Header check:** a pre-commit hook asserts that every `.py` file under `src/korchestrator/`
  carries the `SPDX-License-Identifier: Apache-2.0` line.
- **NOTICE presence:** `MANIFEST.in` includes `NOTICE`; the clean-environment install smoke test
  (spec §10.4) checks it is present in the installed distribution.

## Rollback

Reversible **only** while the copyright holder is the sole contributor. Up to that point, changing
the license is editing three files.

**Point of no return:** the first accepted contribution from anyone outside the copyright holder, or
the first publish to a public registry — whichever comes first. After either, relicensing requires
per-contributor consent (or a CLA obtained in advance, which this project deliberately does not
require) and cannot revoke the rights already granted to anyone who obtained a published version.
Practically: the license is permanent from the first public release.
