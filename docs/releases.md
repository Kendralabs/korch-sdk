# Releases

!!! note "Public distribution via PyPI (ADR 0021)"
    Korchestrator is public: the repository is public and releases publish to
    [PyPI](https://pypi.org/project/korchestrator/) via **Trusted Publishing** (OIDC — no stored
    API token). `pip install korchestrator[dspy]` works for anyone, no GitHub credential needed.
    See [Installation](installation.md). This supersedes the private-distribution pass in
    [ADR 0020](https://github.com/Kendralabs/korch-sdk/blob/main/docs/adr/0020-private-distribution-defers-pypi-publishing.md);
    the decision to go public and enable PyPI is recorded in
    [ADR 0021](https://github.com/Kendralabs/korch-sdk/blob/main/docs/adr/0021-repository-goes-public-pypi-trusted-publishing.md).

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

   **This merge-back must be a fast-forward, not a merge commit.** A normal PR merge (base=`staging`,
   head=`main`) creates a new commit *on* `staging`, which makes `main` an ancestor of `staging` —
   backwards from the invariant (`dev` ancestor-of `staging` ancestor-of `main`). Right after a
   release, `main` is already a fast-forward descendant of `staging` (the release PR's only parent
   was `staging`), so push it directly instead of merging a PR:

   ```bash
   git push origin main:staging
   git push origin main:dev
   ```

   Verify before moving on:

   ```bash
   git fetch origin
   git merge-base --is-ancestor origin/dev origin/staging \
     && git merge-base --is-ancestor origin/staging origin/main \
     && echo OK
   ```

## One-time setup: PyPI Trusted Publisher

Before the **first** publish, and only then, the PyPI account that owns the `korchestrator`
project must register this repository as a trusted publisher. This is an identity/ownership action
on the PyPI account itself — no CI job, agent, or token can do it; it takes about five minutes:

1. Sign in at [pypi.org](https://pypi.org) with the account that will own the `korchestrator`
   project (create the account first if it doesn't exist yet — no need to reserve the name
   manually, a pending publisher does that automatically on first publish).
2. Go to **Account settings → Publishing** (directly:
   [pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)).
3. Add a **pending publisher** with exactly:
   - PyPI project name: `korchestrator`
   - Owner: `Kendralabs`
   - Repository name: `korch-sdk`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
4. In the GitHub repository, create a **Environment** named `pypi` (Settings → Environments) if it
   doesn't already exist. Optionally add required reviewers for an auditable approval gate before
   every publish — recommended given a PyPI publish is irreversible (see below).
5. The **first** successful run of the `publish` job in `release.yml` (from the exact repo,
   workflow file, and environment name above) creates the `korchestrator` project on PyPI
   automatically and converts the pending publisher into an active one. No further setup is needed
   for subsequent releases.

Nothing else in this repository, CI, or an agent's local environment can perform this step — it
requires the account owner's own PyPI login (and, if enabled, 2FA).

## What the release workflow does today

On a `vX.Y.Z` tag push, or a manual `workflow_dispatch` run against an existing tag
(`.github/workflows/release.yml`):

1. **`build`** — validates the tag matches `src/korchestrator/version.py`, builds the wheel and
   sdist (`python -m build`), installs the **built wheel** (not the source tree) into a fresh
   virtualenv outside the repo and confirms `korchestrator.__version__` matches the tag, confirms
   the sdist itself builds a wheel, generates an SBOM (`cyclonedx-bom`, CycloneDX JSON), generates
   `SHA256SUMS` over the wheel/sdist/SBOM, and attests build provenance
   (`actions/attest-build-provenance`).
2. **`publish`** — uploads the wheel and sdist to PyPI via **Trusted Publishing** (OIDC;
   `pypa/gh-action-pypi-publish`) — no long-lived API token is stored anywhere. Gated on the `pypi`
   GitHub Environment.
3. **`github-release`** — publishes a GitHub Release for the tag with the wheel, sdist, SBOM, and
   `SHA256SUMS` attached, and notes extracted directly from the tagged `CHANGELOG.md` section.
4. **`verify-published`** — installs the just-published version from the **real public PyPI
   index** (`pip install korchestrator==X.Y.Z`, no git ref, no credential), retrying briefly for
   index-propagation lag, and confirms `korchestrator.__version__` matches. This is the check that
   proves `pip install korchestrator` actually works for a stranger with no relationship to this
   repository.
5. **`deploy-docs`** — redeploys documentation (`docs.yml`) so published docs stay in sync with
   the release. The koe-proxy VPS deploy documented in `DOCS_DEPLOYMENT.md` remains the primary
   published documentation URL; GitHub Pages (now free, since the repo is public) is a secondary
   target the same workflow already produces.

## Releases are immutable

Once published, a version is never overwritten, re-tagged, or deleted:

- A defective release is fixed **forward** with a new patch version — `0.2.1` supersedes `0.2.0`;
  `0.2.0` stays on the release list.
- **Yank** a release on PyPI (`pip install` still resolves an exact pin, but the version is hidden
  from `pip install korchestrator` with no version pinned) or mark the GitHub Release as a
  pre-release/draft — only if it's actively harmful (a security defect, data loss, a wholly broken
  artifact). This is not deletion; existing pins keep working.
- Tags never move. Consumers and anyone who downloaded a release asset assume a tag is permanent.
- PyPI additionally **refuses to let the same version number ever be re-uploaded**, even after a
  yank — this is a platform rule, not just a project convention.

## Next

- [Installation](installation.md) — how to `pip install` a release.
- [Versioning](versioning.md) — how the bump itself is decided.
- [Migration](migration.md) — what changes between versions and how it's communicated.
