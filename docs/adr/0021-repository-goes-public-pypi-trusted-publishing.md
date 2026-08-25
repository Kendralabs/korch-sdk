# ADR 0021 — Repository becomes public; PyPI publishing enabled via Trusted Publishing

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** Maintainer (Kendra / Fintricity)
- **Phase:** P12 (CI/CD, packaging & publishing) — implements P12.4 (Publish) and P12.6 (dry-run
  verification) as originally specified; both were deferred by ADR 0020.
- **Supersedes:** [ADR 0020](0020-private-distribution-defers-pypi-publishing.md). ADR 0020's
  reasoning (PyPI has no private-index tier; publishing there makes the artifact world-readable
  regardless of repo visibility) is unchanged — what changed is the underlying decision it was
  conditioned on: the repository is no longer staying private.

## Context

ADR 0020 kept `Kendralabs/korch-sdk` private and distributed `v0.1.0` only as a GitHub Release,
specifically because publishing to PyPI would have made the SDK world-readable as a side effect of
a decision to stay private — a side effect nobody had asked for at the time.

That constraint is now moot: the maintainer decided to make the repository public directly, not as
an accidental consequence of a packaging choice. With the source already public, the reason to keep
the *build artifact* off PyPI no longer applies — a private-only wheel would just mean an installer
needs a GitHub credential for a package whose source anyone can already read, which is unnecessary
friction with no security benefit left to protect.

Before flipping visibility, the full tracked history (current tree and `git log --all -p`) was
scanned for committed secrets (AWS-style keys, GitHub/OpenAI-style tokens, private key blocks,
`.env` files). The only matches were the redaction test's own documentation-example literals
(`tests/unit/security/test_redactor.py`, using AWS's public `AKIAIOSFODNN7EXAMPLE`) and the
`.env.example` placeholder (`ANTHROPIC_API_KEY=sk-ant-your-anthropic-key`) — no real credential was
ever committed. The PyPI project name `korchestrator` was confirmed unclaimed
(`https://pypi.org/pypi/korchestrator/json` → 404) before this ADR was written.

## Decision

1. **The GitHub repository becomes public.** `Kendralabs/korch-sdk` visibility changes from
   private to public. This is the maintainer's direct decision, not a side effect of the packaging
   change below.
2. **`release.yml` is rewritten to the full pipeline `docs/specs/10-release-versioning-and-cicd.md`
   §6 already specified** — the design ADR 0020 explicitly left as "additive, not requiring
   rework" once this day came:
   - `build` — unchanged (version-validate, build wheel+sdist, verify the built artifact in a
     clean environment, verify the sdist builds a wheel) plus the two pieces ADR 0020 deferred:
     an SBOM (`cyclonedx-bom`, CycloneDX JSON) and a build-provenance attestation
     (`actions/attest-build-provenance`).
   - `publish` — new. Publishes to PyPI via **Trusted Publishing (OIDC)** —
     `pypa/gh-action-pypi-publish`, no long-lived API token stored in this repository or anywhere
     else. Gated on a `pypi` GitHub Environment for an auditable approval trail.
   - `github-release` — unchanged in shape, now also carries the SBOM.
   - `verify-published` — new, replaces `verify-private-install`. Installs the just-published
     version from the **real public index** (`pip install korchestrator==X.Y.Z`, no git ref, no
     credential) with a short retry loop for index propagation lag, and imports it. This is the
     check that actually proves "`pip install korchestrator`" works for a stranger with no
     relationship to this repository.
   - `deploy-docs` — new, calls the existing `docs.yml` workflow so a release always redeploys
     current documentation. (Public-repo GitHub Pages is free — ADR 0020's private-repo Pages
     paywall no longer applies either, though the koe-proxy VPS deploy documented in
     `DOCS_DEPLOYMENT.md` remains the primary published URL.)
3. **PyPI Trusted Publisher registration is a one-time action only the PyPI account owner can take**
   — creating a *pending* publisher at `https://pypi.org/manage/account/publishing/` (project name
   `korchestrator`, owner `Kendralabs`, repository `korch-sdk`, workflow `release.yml`, environment
   `pypi`) before the first publish. This is out of band from anything CI or an agent can do — it
   is an identity/ownership action on the maintainer's own PyPI account. Documented step-by-step in
   `docs/releases.md`.
4. **`v0.1.0` is re-published under the new pipeline, not re-versioned.** PyPI has never seen this
   version (it only ever shipped as a GitHub Release asset), so uploading it now is a first upload,
   not a re-upload of a yanked or superseded version. Triggered via `workflow_dispatch` against the
   existing `v0.1.0` tag once the pending publisher is registered — no new tag, no version bump.
5. **Documentation updated in the same change:** `README.md`, `docs/installation.md`,
   `docs/releases.md`, `DOCS_DEPLOYMENT.md` — `pip install korchestrator[dspy]` (no git ref, no
   credential) becomes the primary documented install path; the git-ref/SSH install moves to an
   "installing an unreleased commit" appendix, since it is still useful for that case even though
   it is no longer required for tagged releases.
6. `docs/specs/10-release-versioning-and-cicd.md` §6's amendment note (pointing readers to ADR
   0020 to explain why the spec's own example workflow didn't match reality) is removed — the
   implemented `release.yml` now matches the spec directly.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Keep the repo private, publish to PyPI anyway | This is exactly the side effect ADR 0020 was written to avoid — a public artifact with a private, harder-to-audit source. Not chosen because the repository visibility decision came first and independently, and PyPI's own terms already assume public, inspectable source for a public package. |
| Use a long-lived PyPI API token stored as a GitHub secret instead of Trusted Publishing | Trusted Publishing (OIDC) has been PyPI's recommended mechanism since 2023 specifically because it removes a durable, exfiltratable credential from CI — a stored token is strictly worse with no offsetting benefit, and spec 10 already specified Trusted Publishing. |
| Cut a new `v0.1.1` for the first PyPI publish instead of re-publishing `v0.1.0` | Rejected per the explicit instruction to use the already-published version; PyPI has no record of `v0.1.0` today, so publishing it now is not a version-immutability violation — nothing already on the index is being touched. |

## Consequences

**Positive**

- `pip install korchestrator[dspy]` — no GitHub credential, no git — works for anyone, which is
  the entire point of taking the source public.
- SBOM and build-provenance attestation (the rest of P12.3, explicitly deferred by ADR 0020) ship
  in this same change rather than as separate follow-up work.
- No stored long-lived credential is added anywhere in the pipeline — Trusted Publishing's OIDC
  token is minted per-run and expires with the run.
- `release.yml` now matches `docs/specs/10-release-versioning-and-cicd.md` §6 exactly, closing the
  gap ADR 0020 explicitly flagged as temporary.

**Negative**

- The full commit history becomes world-readable at the same moment the repository turns public.
  Verified clean (see Context) but this is a one-way action — anything missed cannot be un-exposed
  by later making the repo private again, since forks/clones/search-engine caches may already
  exist. Rotate, don't just delete, if anything is ever found after the fact.
- The `pypi` GitHub Environment and the pending trusted publisher must be configured once, by hand,
  by whoever owns the PyPI account — this is not automatable and blocks the first `publish` job run
  until done.
- Once published, `v0.1.0` on PyPI is permanent per PyPI's own immutability rules (same as
  `docs/releases.md`'s existing "Releases are immutable" section) — a defective first release
  must be fixed forward with `v0.1.1`, never overwritten.

**Neutral**

- No public API surface changes. This ADR is entirely about repository visibility and the
  distribution mechanism, not the package contents.

## Compliance

- `release.yml`'s `publish` and `verify-published` jobs are exercised end-to-end by the
  `workflow_dispatch` run against the `v0.1.0` tag that accompanies this ADR — `verify-published`
  installing from the real public index with no credential is the verification artifact.
- `ruff check`, `ruff format --check`, and `mypy --strict` are clean on any code touched (none —
  this ADR only changes workflow YAML and documentation).

## Rollback

Reverting to private distribution is possible but not symmetric with ADR 0020's own rollback: a
package already published to PyPI cannot be unpublished (only yanked, which keeps it installable
by exact pin while warning against new installs — see `docs/releases.md`). Reverting would mean:
dropping the `publish`/`verify-published` jobs from `release.yml` (mechanically easy, same as ADR
0020's own rollback), yanking any already-published PyPI versions, and making the GitHub repository
private again (does not retroactively un-expose history already cloned or indexed). Given that
asymmetry, this decision should be treated as effectively one-way in practice even though no single
step is technically irreversible.
