# ADR 0020 — First releases distribute privately via GitHub Releases; PyPI publishing deferred

- **Status:** Accepted
- **Date:** 2026-08-12
- **Deciders:** SDK maintainers (Kendra / Fintricity)
- **Phase:** P12 (CI/CD, packaging & publishing) — narrows P12.4 (Publish) and P12.6 (Dry run)
- **Supersedes / Superseded by:** None. Amends the publish target described in
  `docs/specs/10-release-versioning-and-cicd.md` §6 and `docs/specs/12-implementation-plan.md`
  P12.4/P12.6; does not change P12.1–P12.3's design (version validation, artifact verification,
  supply-chain scanning), which are implemented as specified.

## Context

Spec 10 designs the release pipeline around **PyPI Trusted Publishing**: a tagged release builds,
scans, and publishes an immutable wheel/sdist to the public `pypi.org` index, verified by a
post-publish install job. That design assumes the package is meant to be public.

The `korchestrator` GitHub repository (`Kendralabs/korch-sdk`) is **private** today, and the
decision — confirmed directly with the maintainer — is to keep the SDK's source and its distributed
artifacts private for the first release. PyPI has no free mechanism for a private index: publishing
a wheel there makes it world-readable regardless of the GitHub repo's visibility. Publishing to
PyPI would therefore mean making the SDK public as a side effect of cutting a release, which is not
what was decided.

Phase 12 has not started (`PROJECT_STATE.md` lists it "Not started"), and the existing
`.github/workflows/release.yml` is a P0.8 skeleton — it already builds and verifies the artifact in
a clean environment on a `vX.Y.Z` tag but publishes nowhere. There's a real gap: a tagged release
today produces a verified artifact that never reaches a consumer.

## Decision

Cut the first release (`v0.1.0`) and all releases until this ADR is revisited using a
**private-distribution pipeline** instead of PyPI:

1. `release.yml`'s existing `build` job (version-validate, build wheel+sdist, verify the built
   artifact in a clean environment outside the source tree) is retained unchanged — it is
   distribution-target-agnostic and matches P12.1/P12.2 exactly as specified.
2. A new `checksums` step generates `SHA256SUMS` over the wheel and sdist (P12.3, narrowed — no SBOM
   or provenance attestation in this pass; see Consequences).
3. A new `github-release` job publishes a **GitHub Release** on the (private) repository, attaching
   the wheel, sdist, and `SHA256SUMS`, with release notes extracted from the tagged `CHANGELOG.md`
   section. This works identically on a private repo — no plan restriction applies to release
   assets, only to GitHub Pages and some Advanced Security features.
4. No job publishes to PyPI or any other public/private package index. P12.4 (Publish) and P12.6
   (TestPyPI dry run) are **deferred**, not implemented, until a future ADR decides to make the
   package public.
5. Consumers install via a git reference pinned to the release tag, authenticated with their own
   GitHub credentials (PAT or SSH deploy key) since the repo is private:
   ```bash
   pip install "korchestrator[dspy] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
   ```
   or by downloading the wheel from the GitHub Release and installing it locally. `docs/releases.md`
   and `docs/installation.md` document this as the current, correct instruction — not a stopgap
   note pointing at a future PyPI install.
6. `scripts/cut_release.py` automates the mechanical steps of a release (version bump, CHANGELOG
   date flip, release-branch/PR creation, tagging) so future releases don't require re-deriving the
   runbook in `docs/specs/10-release-versioning-and-cicd.md` §9 by hand. It targets the same
   `chore/release-vX.Y.Z` branch-and-PR shape the runbook already specifies.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Publish to public PyPI now, per the original spec 10 design | Directly contradicts the maintainer's private-distribution decision; would make the source-derived artifact world-downloadable the moment a tag is pushed, regardless of repo visibility. |
| Stand up a private package index (GitHub Packages, or a hosted PyPI-compatible registry) so consumers get a plain `pip install korchestrator` | Real option for later, but materially more setup (registry provisioning, auth wiring, index-url configuration for every consumer) than the maintainer asked for in this pass. Left as a documented future option, not built speculatively — the abstraction test in `.claude/rules/architecture-boundaries.md` (demonstrated variability, stable axis, net removal) doesn't clear for a second distribution channel nobody has asked to use yet. |
| Leave `release.yml` as the unpublishing skeleton and hand-run `gh release create` manually each time | Rejected: leaves no auditable, repeatable CI path from tag to artifact; the manual step is exactly the kind of undocumented tribal knowledge the runbook exists to prevent. |
| Skip checksums too, ship only raw dist files | Rejected: `SHA256SUMS` is one `sha256sum` invocation, materially cheap, and is the one piece of P12.3 a consumer with no CI trust chain of their own can actually use to verify what they downloaded. |

## Consequences

**Positive**

- A tagged release now actually reaches a consumer (a GitHub Release with attached artifacts),
  closing the gap where `release.yml` verified an artifact and then discarded it.
- Nothing about the SDK's source or its build artifacts becomes public as a side effect of this
  release process — matches the confirmed decision.
- `scripts/cut_release.py` removes the highest-risk manual step (hand-editing `version.py` and the
  CHANGELOG under time pressure) from every future release.
- P12.1–P12.3's design is unaffected and remains eligible to feed a future public-PyPI phase without
  rework — only the publish target (P12.4) and its dry run (P12.6) are deferred.

**Negative**

- Consumers need a GitHub credential (PAT or SSH key) with read access to this repo to install via
  `pip install git+https://...`; there is no anonymous, credential-free install path today. This is
  the direct cost of staying private and is called out explicitly in `docs/installation.md`.
- SBOM generation and build-provenance attestation (the rest of P12.3) are **not** implemented in
  this pass — only checksums. `cyclonedx-bom` and `actions/attest-build-provenance` are
  straightforward additions but weren't required to unblock the first release; tracked as follow-up
  work under P12.3, not silently dropped.
- `docs/specs/10-release-versioning-and-cicd.md` §6 still describes the full public-PyPI pipeline as
  written — it is the target design for when this ADR is revisited, not the current implementation.
  A short amendment note at the top of that section points here so a reader doesn't mistake the
  spec's example workflow for what actually runs today.

**Neutral**

- No public API surface changes. This ADR is entirely about the distribution mechanism, not the
  package contents.

## Compliance

- `release.yml`'s `github-release` job is exercised end-to-end by the `v0.1.0` tag push that
  accompanies this ADR's merge to `main`; its output (a GitHub Release with the wheel, sdist, and
  `SHA256SUMS` attached) is the verification artifact.
- `scripts/cut_release.py` is covered by its own unit tests (`tests/unit/test_cut_release.py`,
  matching the existing convention for `scripts/check_benchmark_regression.py`) exercising the
  version-bump arithmetic and the CHANGELOG rewrite against fixture content, without touching git
  or the network.
- `ruff check`, `ruff format --check`, and `mypy --strict` are clean on the new script.

## Rollback

Fully reversible and low-risk: dropping the `checksums`/`github-release` jobs from `release.yml`
returns it to the P0.8 skeleton; no persisted state, public model, or `__all__` entry is touched. If
a future decision makes the package public, implementing P12.4/P12.6 as spec 10 already describes is
additive — it does not require undoing anything this ADR adds.
