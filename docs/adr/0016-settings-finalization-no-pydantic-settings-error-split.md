# ADR 0016 — Settings finalization: no `pydantic-settings`, and the `ConfigurationError`/`ValidationError` split

- **Status:** Accepted
- **Date:** 2026-07-23
- **Deciders:** SDK maintainers
- **Phase:** P8
- **Supersedes / Superseded by:** Reopens and reaffirms [ADR 0009](0009-settings-on-pydantic-core-no-pydantic-settings.md), which explicitly deferred this question to P8. Does not supersede ADR 0004 or ADR 0009 — extends them.

## Context

P8.1 finalizes `Settings`: the full spec 08 §1.3 variable table (23 variables, several
`SecretStr`), `.env` file support, and `configure()`/`get_settings()`. ADR 0009 deferred exactly
this to P8 and explicitly invited reopening the `pydantic-settings` question "if a concrete
requirement (e.g. `.env` loading for local development) justifies the dependency." `.env` loading
has now arrived, so that reopening condition is live.

Separately, `PROJECT_STATE.md` §6 has flagged an unresolved overlap since P5: `ConfigurationError`
and `ValidationError` both nominally cover "invalid configuration," `ConfigurationError` has
several real call sites (env JSON parsing, unresolved model-card sources, an unsupported
`PERSISTENCE_BACKEND`, a graph-less `TemporalRuntime.start()`) but is not in top-level `__all__`,
and spec 08 §1.2 says `configure()` raises `ValidationError` — with no stated rule for when the
other type applies. `configure()` landing now makes this a live, user-facing question that can no
longer be deferred.

## Decision

**Two decisions, filed together because both gate P8.1.**

### 1. No `pydantic-settings` — continue `Settings.from_env()`, add a hand-written `.env` reader

`Settings` stays a plain `pydantic.BaseModel`; `config/` gains a small, explicit `.env` parser
(`_read_dotenv_file`) merged into `from_env()`'s existing precedence chain
(`argument > environment variable > .env file > declared default`). `SecretStr` typed fields use
`pydantic.SecretStr`, which is already part of `pydantic` core — no new dependency required for
either capability ADR 0009 named as the reopening trigger.

The reopening condition in ADR 0009 is not met: everything `pydantic-settings` would add over the
existing pattern — `.env` parsing and secret typing — is available from `pydantic` alone. Adding
the dependency would buy convenience (no hand-written `.env` reader, ~15 lines) at the cost of
enlarging the base install beyond `pydantic`, which ADR 0004 and ADR 0009 both treat as a
load-bearing, market-facing invariant, checked by a dedicated CI base-install job. That trade is
not justified by a ~15-line parser.

### 2. `ConfigurationError` vs `ValidationError`

- **`ValidationError`** — a value fails **structural** validation: wrong type, out of range, not
  a recognised enum member, a failing `pydantic` field/model validator. This is what `configure()`
  raises per spec 08 §1.2 — it wraps the underlying `pydantic.ValidationError` from
  `Settings.from_env(**overrides)` with `raise ... from exc`, consistent with how `Agent` already
  wraps `AgentConfig`'s pydantic errors (ADR-adjacent existing pattern, `agents/base.py`).
- **`ConfigurationError`** — the value is structurally valid but the **configuration it describes
  cannot be resolved or is not supported**: malformed JSON in an env var (fails before a
  `Settings` field even exists to validate), an unresolvable model-card source, an unimplemented
  backend (`PERSISTENCE_BACKEND=kcg`), a missing bound collaborator (no clock, no gateway, no
  Temporal client), a signal-only `TemporalRuntime` asked to `start()`. Every existing
  `ConfigurationError` call site already fits this rule without change, including the ones
  `configure()` can still surface (a malformed `AGENT_MODEL_MAP`/`ROUTING_WEIGHTS` JSON string).
- **`ConfigurationError` stays out of top-level `korchestrator.__all__`**, matching spec 04 §6's
  literal `__init__.py` example, which lists `configure` but not `ConfigurationError`. It remains
  reachable exactly like `TimeoutError` already is — `from korchestrator.exceptions import
  ConfigurationError` — and stays part of the documented compatibility surface (constants,
  exceptions, and supporting protocols are covered even when not top-level, per
  `api-and-compatibility.md`). Promoting it to top-level was considered (§ Alternatives) and
  rejected as an unforced deviation from an explicit spec example.

Bare `Settings(...)`/`Settings.from_env(...)` construction (not via `configure()`) is unchanged:
it still raises `pydantic.ValidationError` directly, matching every existing test
(`test_invalid_enum_value_is_rejected`, `test_from_env_rejects_an_invalid_value`). Only the new
`configure()` entry point wraps.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Adopt `pydantic-settings` now that `.env` support is required | Solves `.env`/`SecretStr` "for free," but both are already available without it (a hand-written `.env` reader, `pydantic.SecretStr`). Enlarges the base install for a convenience that costs nothing to build directly — the exact trade ADR 0009 already rejected once. |
| Make `ValidationError` cover configuration-resolution failures too (drop `ConfigurationError`) | Simpler taxonomy, but throws away a distinction every existing call site already relies on (structural vs resolution failures), and removing an established, call-site-backed error type is a bigger, riskier change than clarifying when to use it. |
| Wrap bare `Settings(...)` construction into `korchestrator.ValidationError` too, not just `configure()` | More consistent with `Agent`'s wrapping, but breaks existing tests that assert raw `pydantic.ValidationError` from bare construction, and spec 08 §1.2's promise is scoped to `configure()` specifically. Deferred — revisit only with an explicit compatibility decision, since `Settings` is public and this is a breaking change to its raised-exception type. |
| Add `ConfigurationError` to top-level `korchestrator.__all__` | It is genuinely reachable from `configure()`, so this has real appeal. Rejected: spec 04 §6's `__init__.py` example is explicit and does not include it — the same treatment `TimeoutError` already gets deliberately. Deviating without a named consumer or a concrete pain point is exactly the unforced spec drift `.claude/CLAUDE.md`'s "on any conflict, the specs win" rule exists to prevent; `korchestrator.exceptions.ConfigurationError` stays fully catchable, just not top-level. |

## Consequences

**Positive**

- No new runtime dependency; the base install stays `pydantic`-only, unchanged from ADR 0004/0009.
- The `ConfigurationError`/`ValidationError` split now has a written rule new call sites can be
  checked against, closing the gap flagged since P5.
- `configure()` matches spec 08 §1.2's literal promise (`ValidationError` on invalid values)
  while still surfacing `ConfigurationError` for the failures that were always going to raise it.

**Negative**

- The hand-written `.env` reader is one more small piece of config machinery to maintain, though
  it is intentionally minimal (read the file, split `KEY=VALUE` lines, ignore comments/blank
  lines) and does not attempt `pydantic-settings`'s full feature set (nested delimiters, secret
  file sources, etc.) — none of which this SDK currently needs.
- A caller who wants to catch a malformed-JSON-env-var failure from `configure()` specifically
  (as opposed to any `KorchError`) still needs the submodule import
  (`korchestrator.exceptions.ConfigurationError`) — a minor ergonomic cost, same as `TimeoutError`.

**Neutral**

- Bare `Settings(...)` still raises raw `pydantic.ValidationError`; only `configure()` wraps. A
  future ADR could change this, but it is out of scope here.

## Compliance

- The base-install CI job (P0.7) continues to assert `pydantic` is the only runtime dependency —
  proves the `pydantic-settings` decision is honoured.
- `tests/unit/config/test_configure.py` asserts `configure()` raises `korchestrator.ValidationError`
  (not raw `pydantic.ValidationError`) on an invalid override, and that a malformed JSON env var
  raises `korchestrator.exceptions.ConfigurationError`.
- `tests/unit/test_public_surface.py`'s golden file matches spec 04 §6 exactly —
  `ConfigurationError` absent from top-level `__all__`, present and importable from
  `korchestrator.exceptions`.

## Rollback

Reversible. Adopting `pydantic-settings` later requires its own superseding ADR per ADR 0004's
process, replacing `from_env`/the `.env` reader with `BaseSettings` while keeping field names
stable. Un-wrapping `configure()` back to raw `pydantic.ValidationError`, or promoting
`ConfigurationError` to top-level `__all__`, are each a documented, versioned public-surface
change (a MINOR while `0.x`, stated loudly in the CHANGELOG per `api-and-compatibility.md`).
