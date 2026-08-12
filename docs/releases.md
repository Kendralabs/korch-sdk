# Releases

!!! note "Not live yet"
    Publishing (PyPI, SBOM/checksums, provenance attestation, the docs deploy) is Phase 12 of this
    project and hasn't shipped yet. `.github/workflows/release.yml` today builds a wheel/sdist on a
    `vX.Y.Z` tag and verifies the artifact imports correctly in a clean environment — nothing is
    published. This page describes the intended process; the parts marked "Phase 12" aren't live.

## How a release is decided

1. Every change intended for the release is merged into `dev`, green on the full CI matrix, then
   promoted to `staging` and verified there. Releases are cut from `staging`, never from `dev`.
2. The version bump follows [Versioning](versioning.md)'s SemVer rules, applied to the diff since
   the last release. If the compatibility surface changed, an ADR justifying it already exists.
3. A release PR (`chore/release-vX.Y.Z`) from `staging` into `main` contains exactly two kinds of
   change: the
   version bump in `src/korchestrator/version.py`, and the CHANGELOG edit moving `[Unreleased]`
   into a dated section. Nothing else.
4. Every entry under `Changed`/`Deprecated`/`Removed` in that CHANGELOG section has a matching
   [Migration](migration.md) section with a before/after example.
5. Merge into `main`, then tag: a signed, annotated `vX.Y.Z` tag on the merge commit, matching
   `version.py` exactly (`release.yml` fails the build if it doesn't).

## What the release workflow does today

On a `vX.Y.Z` tag push:

1. Validates the tag matches `src/korchestrator/version.py`.
2. Builds the wheel and sdist (`python -m build`).
3. Installs the **built wheel** (not the source tree) into a fresh virtualenv, outside the repo, and
   confirms `korchestrator.__version__` matches the tag.

## What's coming in Phase 12

- Publishing to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (no
  long-lived API token stored anywhere).
- SBOM generation, checksums (`SHA256SUMS`), and provenance attestation on every release.
- A GitHub release with notes drawn directly from the CHANGELOG.
- A post-publish install verification from PyPI itself, on a machine that isn't the CI runner.
- The documentation site deploying automatically alongside the release.

## Releases are immutable

Once published, a version is never overwritten, re-tagged, or deleted:

- A defective release is fixed **forward** with a new patch version — `0.2.1` supersedes `0.2.0`;
  `0.2.0` stays on the index.
- A version is **yanked** at the registry only if it's actively harmful (a security defect, data
  loss, a wholly broken artifact). Yanking hides it from resolution for new installs while leaving
  existing pins working — it is not deletion.
- Tags never move. Consumers, mirrors, SBOM references, and provenance attestations all assume a
  tag is permanent.

## Next

- [Versioning](versioning.md) — how the bump itself is decided.
- [Migration](migration.md) — what changes between versions and how it's communicated.
