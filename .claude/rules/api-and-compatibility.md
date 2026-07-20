# Rule — Public API & compatibility

Repository-specific. Authority: `docs/specs/04-public-api.md`, `docs/specs/10-release-versioning-and-cicd.md`.

## The compatibility surface

Exactly four things are public. Everything else is internal and may change in any release.

1. `korchestrator.__all__`
2. The ARI ports and documented supporting protocols
3. The models marked public in `docs/specs/05-modules-and-data-models.md`
4. The remote contract in `docs/specs/04-public-api.md` §7

If it is not one of those four, do not treat it as a contract — and do not let a user's reliance on
it become one by accident.

## API-first

Design the public surface **before** implementing. In the PR description, state the signature, the
return type, the exceptions, and the example — then build to it. Check every name against the
canonical vocabulary (`docs/specs/04-public-api.md` §3.1) before writing it down.

## Every public callable

- Fully type-hinted, `mypy --strict` clean
- Returns a typed model, never a bare `dict`
- Google-style docstring with a runnable offline example
- Optional parameters are **keyword-only** (`*` separator) so adding one later is non-breaking
- Raises only `KorchError` subclasses
- No import-time side effects

## Is this change breaking?

| Breaking (MAJOR) | Not breaking (MINOR/PATCH) |
|---|---|
| Removing/renaming a name in `__all__` | Adding a name to `__all__` |
| Removing/renaming a public model field | Adding an optional field with a default |
| Adding a required parameter | Adding a keyword-only parameter with a default |
| Narrowing an accepted input type | Widening an accepted input type |
| Widening a returned type | Narrowing a returned type |
| Changing an exception type at a boundary | Adding a subclass of an already-raised type |
| Changing a default that alters results | Changing a default that only affects performance |
| Changing a serialized schema untagged | Adding a version-tagged migration |

While `0.x`, a MINOR may break — but it must be **stated loudly** in the CHANGELOG, never slipped in.

## The snapshot test

`__all__` is guarded by a golden-file test. When it fails, that is the design working: you are being
asked to decide, deliberately, whether this is an addition or a removal. Update the golden file
**only** together with a CHANGELOG entry and an explicit version decision in the same PR.

## Deprecation

Never remove a public name without notice:

1. Emit a `DeprecationWarning` naming the replacement and the removal version
2. Keep it working for at least one minor release
3. Document replacement, migration path, and removal version in the CHANGELOG and migration guide
4. Remove only in a MAJOR (or a MINOR while `0.x` that says so)

Deprecations ship with a test asserting the warning fires and the old path still returns the same
result as the new one.

## Version discipline

- **Never edit `src/korchestrator/version.py`** outside a release PR. It is the single source of the
  version and is denied by the permission rules in `.claude/settings.json`.
- Every user-visible change lands with its CHANGELOG entry **in the same PR**.
- Documentation, docstrings, examples, and the parity matrix change in the same PR as the contract.
