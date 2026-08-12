# Releases

!!! note "Private distribution (ADR 0020)"
    Korchestrator is not published to PyPI. The repository is private, and per
    [ADR 0020](adr/0020-private-distribution-defers-pypi-publishing.md) releases distribute as
    **GitHub Releases on this private repo** instead — PyPI has no free private-index tier, and
    publishing there would make the SDK world-readable regardless of the repo's own visibility.
    `.github/workflows/release.yml` builds, verifies, checksums, and publishes a GitHub Release on
    every `vX.Y.Z` tag; see [Installation](installation.md) for how to `pip install` from it.

## How a release is decided

1. Every change intended for the release is merged into `dev`, green on the full CI matrix, then
   promoted to `staging` and verified there. Releases are cut from `staging`, never from `dev`.
2. The version bump follows [Versioning](versioning.md)'s SemVer rules, applied to the diff since
   the last release. If the compatibility surface changed, an ADR justifying it already exists.
3. A release PR (`chore/release-vX.Y.Z`) from `staging` into `main` contains exactly two kinds of
   change: the version bump in `src/korchestrator/version.py`, and the CHANGELOG edit moving
   `[Unreleased]` into a dated section. Nothing else. `scripts/cut_release.py prepare` automates
   both edits and opens this PR.
4. Every entry under `Changed`/`Deprecated`/`Removed` in that CHANGELOG section has a matching
   [Migration](migration.md) section with a before/after example.
5. Merge into `main`, then tag: an annotated (or signed, with `--sign`) `vX.Y.Z` tag on the merge
   commit, matching `version.py` exactly (`release.yml` fails the build if it doesn't).
   `scripts/cut_release.py tag` automates the tag creation and push.
6. After the tag push and the release workflow completes, merge `main` back into `staging` and
   `dev` so all three branches converge again — the promotion invariant in
   `.claude/rules/branching-and-promotion.md` expects this "at rest" state between releases.

## What the release workflow does today

On a `vX.Y.Z` tag push (`.github/workflows/release.yml`):

1. **`build`** — validates the tag matches `src/korchestrator/version.py`, builds the wheel and
   sdist (`python -m build`), installs the **built wheel** (not the source tree) into a fresh
   virtualenv outside the repo and confirms `korchestrator.__version__` matches the tag, confirms
   the sdist itself builds a wheel, and generates `SHA256SUMS` over both artifacts.
2. **`github-release`** — publishes a GitHub Release for the tag with the wheel, sdist, and
   `SHA256SUMS` attached, and notes extracted directly from the tagged `CHANGELOG.md` section.
   Works identically on a private repo — release assets aren't subject to the plan restrictions
   that gate GitHub Pages or Advanced Security features.
3. **`verify-private-install`** — installs the package via
   `pip install git+https://...@github.com/...@vX.Y.Z`, authenticated with the workflow run's own
   short-lived `GITHUB_TOKEN`, and confirms `korchestrator.__version__` matches — proving the same
   install path a real consumer with repo read access will use actually works.

## What's deferred (ADR 0020)

- Publishing to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) — the
  package would become world-readable the moment a tag is pushed, which contradicts staying
  private. Revisit only alongside an explicit decision to make the SDK public.
- SBOM generation and build-provenance attestation. Checksums (`SHA256SUMS`) ship today; the rest
  of the supply-chain tooling in `docs/specs/10-release-versioning-and-cicd.md` §6 is additive
  follow-up work, not something this pass silently dropped.
- A documentation site deploy tied to the release tag. `.github/workflows/docs.yml` already
  deploys to GitHub Pages on every push to `main` (private-repo Pages requires a paid GitHub
  plan); it isn't re-triggered by the release tag specifically.

## Releases are immutable

Once published, a version is never overwritten, re-tagged, or deleted:

- A defective release is fixed **forward** with a new patch version — `0.2.1` supersedes `0.2.0`;
  `0.2.0` stays on the release list.
- **Yank** a release only if it's actively harmful (a security defect, data loss, a wholly broken
  artifact) — mark the GitHub Release as a pre-release/draft or add a prominent warning to its
  notes so new installs are steered away, while existing pins keep working. This is not deletion.
- Tags never move. Consumers and anyone who downloaded a release asset assume a tag is permanent.

## Next

- [Installation](installation.md) — how to actually `pip install` a private release.
- [Versioning](versioning.md) — how the bump itself is decided.
- [Migration](migration.md) — what changes between versions and how it's communicated.
