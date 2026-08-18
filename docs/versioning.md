# Versioning

Korchestrator follows [Semantic Versioning 2.0.0](https://semver.org) (`MAJOR.MINOR.PATCH`),
starting at `0.1.0`.

| Bump | When |
|---|---|
| **MAJOR** | A backward-incompatible change to the compatibility surface (below) |
| **MINOR** | Backward-compatible new functionality; a new deprecation; a new optional extra |
| **PATCH** | Backward-compatible bug fixes, documentation, performance, and internal refactors |

!!! warning "Beta testing — 0.x notice"
    **`v0.1.0` is a beta release**, published for early access and real-world feedback while the
    public API is still being validated by integrators. While the version is `0.x`, a MINOR
    release may contain breaking changes — PATCH releases never do. If you adopt it during this
    period, pin the exact version you tested against and read the `CHANGELOG.md` before bumping.
    See below for exactly what's covered by the compatibility promise even during beta.

## The compatibility surface

Only what's listed here is covered by the SemVer promise. **Everything else is internal and may
change in any release, including patch releases** — regardless of whether it happens to be
importable.

| In the compatibility surface | Not in it |
|---|---|
| Names exported from `korchestrator.__all__` | Any name starting with `_` |
| The ARI ports: `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway` | Concrete provider implementations' internals |
| The documented protocols: `IDurableRuntime`, `GraphRepository`, `BaseRouter`, `AUBConnector` | Module paths not re-exported from the package root |
| The documented Pydantic models and their field names, types, and serialized form | Undocumented model fields and private validators |
| The `KorchError` hierarchy and its error codes | Exception message wording |
| The remote contract: endpoint paths, request/response shapes, the auth scheme, status vocabulary | Retry timing, connection pooling, internal client structure |
| Recognised environment variables and `Settings` field names | Default values that are documented as tunable |
| The serialized on-the-wire form of state, tagged with its schema version | In-memory representation |

Adding a field with a default is backward-compatible. Removing a field, narrowing a type, changing
a default that alters behaviour, or renaming anything in the left column is breaking.

See the [API reference](reference/index.md) for exactly what's in each category today.

## The 0.x caveat, stated plainly

This is a deliberate, published exception to the usual SemVer reading: it exists because the
public surface is still being validated by real integrators, and freezing it prematurely would
force either a `1.0` the project cannot honour or a stream of major bumps that communicate nothing.

Even during `0.x`:

- A breaking change still gets an ADR, a CHANGELOG entry (under `### Removed` or `### Changed`),
  and a migration note.
- A breaking change still goes through the deprecation path below **when it's possible to** — an
  ADR must say why, on the occasions it isn't.
- PATCH releases are never breaking, at any version, `0.x` included.

From `1.0.0` onward the compatibility policy applies without exception, and this notice comes down.

## Deprecation policy

Nothing in the compatibility surface is removed without first being deprecated:

| Requirement | Detail |
|---|---|
| Warning | The deprecated name emits a `DeprecationWarning` on use, naming its replacement and removal version |
| Overlap | Stays functional for at least one full MINOR release after the release that deprecates it |
| Documentation | The docstring gains a deprecation note; [Migration](migration.md) gains a before/after example |
| CHANGELOG | An entry under `### Deprecated` when introduced, `### Removed` when actually removed |
| Removal | Only in a release whose bump rule permits it (MAJOR, or MINOR while `0.x`) |

A deprecation never changes behaviour on its own — the deprecated path keeps working exactly as
before until it's actually removed.

## Supported Python versions

**3.10, 3.11, 3.12, and 3.13** — CI tests every one. Dropping a version is a MINOR bump while
`0.x` and a MAJOR bump thereafter, and only after that version's upstream end-of-life.

## Next

- [Migration](migration.md) — what to expect if something you depend on is deprecated or changed.
- [Releases](releases.md) — how a version actually ships.
