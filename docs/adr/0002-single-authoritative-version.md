# ADR 0002 — Single authoritative version

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

A version number in a published SDK appears in at least six places: the source tree, the package
metadata, the runtime `__version__` attribute, the documentation site, the CHANGELOG, and the git
tag. Every one of those is a place where a human can forget to bump. The failure mode is not loud —
the package installs fine, imports fine, and reports a version that is a lie. Support then debugs
the wrong code.

Spec §10.7 requires exactly one authoritative source with everything else deriving from it, and
requires CI to fail when they disagree. Spec §2.10 lists this among the decisions that must not be
deferred past Phase 0, because retrofitting single-sourcing after several releases means auditing
every prior tag.

Additional constraints specific to this repository:

- The SDK must be usable from a source checkout and in editable installs (`pip install -e .`), which
  developers and CI both do. `__version__` must be correct in that mode, not only after a build.
- The build backend is `hatchling` (spec §12 Phase 0), which supports reading the version from code.
- `.claude/settings.json` already denies `Edit(src/korchestrator/version.py)` to agents, so the
  authoritative file must be one that a human deliberately edits during a release PR.

## Decision

**`src/korchestrator/version.py` is the single source of truth.** It contains one meaningful line:

```python
__version__ = "0.1.0"
```

No other file in the repository contains a version literal for this package.

**Everything else derives:**

- `pyproject.toml` declares `dynamic = ["version"]` and configures
  `[tool.hatch.version] source = "code"` with `path = "src/korchestrator/version.py"`, so package
  metadata is read from the file at build time.
- `src/korchestrator/__init__.py` re-exports it: `from .version import __version__`, listed in
  `__all__`.
- The documentation site reads it at build time; the release tag is `v{__version__}`; the CHANGELOG
  heading for the release must match.

**A `version-validate` CI job fails the build** if `version.py`, the built distribution's metadata,
and — on a tag build — the git tag do not all agree.

**The starting version is `0.1.0`.** While on `0.x`, a minor bump may contain breaking changes; this
is stated in the README and CHANGELOG per spec §10.7. From `1.0.0` the full SemVer and deprecation
policy applies without exception.

**`version.py` is edited only in a release PR.** This is enforced two ways: the Claude Code
permission rule `Edit(src/korchestrator/version.py)` in `.claude/settings.json` `permissions.deny`
blocks agents outright, and reviewers reject a version bump that arrives in a feature PR.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Version literal in `pyproject.toml` only; `__version__` computed at runtime via `importlib.metadata.version("korchestrator")` | This is the most common modern pattern and it genuinely reduces moving parts. Rejected because it fails in exactly the modes this SDK is used in during development: from an un-installed source checkout it raises `PackageNotFoundError`, and in editable installs it can report stale metadata after a bump. `__version__` must never raise or lie, including in a test run against the source tree. |
| `setuptools-scm` / version derived from the git tag | Eliminates the bump step entirely and makes tag/metadata disagreement structurally impossible — a real advantage. Rejected because the version becomes invisible in the source tree (a reader cannot answer "what version is this?" from the code), builds from a tarball without git history break or silently produce `0.0.0`, and tests cannot assert against a fixed expected version without reimplementing the derivation. |
| Version in `__init__.py` rather than a dedicated `version.py` | Nearly equivalent, and one fewer file. Rejected because `__init__.py` is the public API surface and will import from submodules; a build backend reading the version from it can trigger those imports at build time, and the permission-deny rule would then block edits to the file every feature PR needs to touch. A dedicated, import-free module is the reason this pattern is worth the extra file. |
| Two authoritative versions (Python package and TypeScript client versioned independently) | Spec §10.7 explicitly allows the TS client its own SemVer line. Not applicable yet — no TS client exists (ADR 0008). When it does, it gets its own source of truth in its own manifest; this ADR governs the Python distribution only. |

## Consequences

**Positive**

- `import korchestrator; korchestrator.__version__` is correct in every mode: source checkout,
  editable install, built wheel, sdist.
- Version skew between tag, metadata, and code is caught by CI before publish, not by a user's bug
  report after.
- Tests can assert an exact expected version, which makes the release checklist mechanically
  verifiable.

**Negative**

- The release still requires a manual edit. Human error is reduced to a single file but not
  eliminated; the `version-validate` job is what catches it.
- `dynamic = ["version"]` means the version is not readable by grepping `pyproject.toml`, which
  surprises tooling and readers that expect a static field.

**Neutral**

- `version.py` is deliberately import-free and dependency-free. It must stay that way — importing
  anything into it would run that import at build time.
- The permission-deny rule blocks agents but not humans; it is a guardrail against accidental
  agent-authored bumps, not a security control.

## Compliance

- **CI job `version-validate`** (in `.github/workflows/ci.yml`) is the enforcement point. It builds
  the distribution, then asserts that: (a) the literal in `src/korchestrator/version.py`, (b) the
  `Version` field of the built wheel's metadata, and (c) on tag builds, the tag with its leading `v`
  stripped, are all equal. Any disagreement fails the build. `release.yml` will not publish unless
  this job is green.
- **Single-literal check:** the same job greps the repository for a second version literal and fails
  if a `MAJOR.MINOR.PATCH` string is assigned to a name containing `version` anywhere outside
  `src/korchestrator/version.py`, `CHANGELOG.md`, and lockfiles.
- **Runtime check:** `tests/unit/test_version.py` asserts `korchestrator.__version__` is importable,
  is a valid SemVer string, and equals the literal in `version.py`.
- **Edit guard:** `.claude/settings.json` → `permissions.deny` contains
  `Edit(src/korchestrator/version.py)`. Reviewers additionally reject any non-release PR whose diff
  touches that path.

## Rollback

Cheap. Switching to any other single-sourcing scheme is a change to `pyproject.toml`, the
`version-validate` job, and one test — no user-visible surface changes, because `__version__` and
the package metadata keep the same shape whatever produces them.

**Point of no return:** none for the mechanism. There is one for the *value*: published versions are
immutable (spec §10.8). A version number that has been published to the registry can never be reused
or overwritten — a bad release is superseded by a new patch and yanked if harmful. So the mechanism
is reversible at any time; a published number never is.
