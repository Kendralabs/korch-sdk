# ADR 0009 — Settings on the pydantic core, env read inside `config/`

- **Status:** Accepted
- **Date:** 2026-07-21
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** Refines the `config/` allowed-imports note in
  spec 05 §1 and the P0.3 task wording in spec 12; upholds and does not supersede
  [ADR 0004](0004-dependency-extras-matrix.md).

## Context

Spec 05 §1 lists `pydantic-settings` as an allowed import for `config/` with **no
extra**, and spec 12 P0.3 says to build `config/settings.py` "with `pydantic-settings`".
`config/` has no extra, and `Settings` sits on the default Tier-1 one-liner path, so
whatever `config/settings.py` imports at module scope becomes a **base-install runtime
dependency**.

That collides with [ADR 0004](0004-dependency-extras-matrix.md), which is emphatic and
Accepted: *"The base install depends on `pydantic` alone… Nothing joins the base install
without a superseding ADR."* `pydantic-settings` is a distinct PyPI distribution, not part
of `pydantic`'s transitive set, so adding it to the base would break the flagship,
repeatedly-marketed property that `pip install korchestrator` pulls in `pydantic` and
nothing else (spec 02 §8.1, spec 03 §3.1, CLAUDE.md golden rule 3).

Two specs therefore conflict on one concrete point: *is `pydantic-settings` a base
dependency?* The manifest (spec 02 §8) and ADR 0004 say the base is `pydantic`-only; spec
05 and P0.3 imply `pydantic-settings` ships at base.

## Decision

**`Settings` is built on `pydantic.BaseModel`, and `config/` reads the environment directly
via `os.environ`.** The SDK does **not** take a runtime dependency on `pydantic-settings`.

- Reading `os.environ` is confined to `config/`, which is the single sanctioned place for
  environment access (spec 08 §1.1) and is exactly where the env-confinement gate expects
  it.
- Environment-aware construction is an explicit `Settings.from_env(**overrides)`
  classmethod with precedence **argument > environment variable > declared default**.
  Bare `Settings(...)` performs no environment access, which keeps it pure and makes tests
  free of ambient-environment leakage.
- The `.env`-file, `SecretStr`, and nested-settings machinery that `pydantic-settings`
  offers is **deferred to P8**, where the full `Settings` table, `configure()`, and
  `get_settings()` land. P8 may reopen this decision if a concrete requirement (e.g.
  `.env` loading for local development) justifies the dependency — via its own superseding
  ADR, per ADR 0004's rule.

This resolves the conflict in favour of the higher-priority, load-bearing invariant
(pydantic-only base) and follows ADR 0004's own process: a dependency joins the base only
with a superseding ADR, and this ADR declines to add one.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Add `pydantic-settings` to the base install (write a superseding ADR authorising it) | Matches spec 05/P0.3 literally and gives `.env`/`SecretStr` for free. Rejected: it enlarges the base beyond `pydantic`, eroding the flagship "pydantic-only" install and import-purity story that ADR 0004, spec 02 §8.1, and spec 03 §3.1 treat as a core differentiator — a real, user-visible cost for a 3-field settings object. The convenience it buys is not needed until the full P8 `Settings`. |
| Put `pydantic-settings` behind a new `[config]` extra | The default one-liner would then fail on a base install, breaking zero-config Tier 1 (spec 08 §1.1). Worse than either real option. |
| Read env outside `config/` (e.g. in `services/`) | Violates the single-reader rule (spec 08 §1.1) and the env-confinement gate. Non-starter. |

## Consequences

**Positive**
- The base install remains `pydantic`-only; ADR 0004's guarantees and the base-install /
  import-purity gates are untouched (they never named `pydantic-settings`, and the kernel
  suite — `core/`, `models/` — does not import `config/` at all).
- `Settings(...)` is pure and deterministic; tests construct it with explicit values and
  need not scrub the ambient environment.
- One fewer runtime dependency to pin, scan, and keep license-compatible.

**Negative**
- `Settings.from_env()` re-implements a thin slice of what `pydantic-settings` does
  (reading named variables, applying precedence). For three scalar fields this is a few
  lines; it grows in P8 and must be watched so it does not become a second config system.
- No `.env` file support at P0. Acceptable: P0–P3 configure via real environment variables
  or explicit arguments; `.env` ergonomics arrive in P8.

**Neutral**
- Field values are matched case-sensitively against their `Literal` types (`"local"`, not
  `"LOCAL"`), the same as `pydantic-settings` would do for value coercion.

## Rollback

Reversible and cheap. If P8 adopts `pydantic-settings`, it writes a superseding ADR adding
it to the base (or an extra), replaces `from_env` with `BaseSettings`, and keeps the public
`Settings` field names stable so no consumer breaks. Nothing in this ADR is on the
serialized or public-API compatibility surface beyond the `Settings` field names, which are
unchanged either way.
