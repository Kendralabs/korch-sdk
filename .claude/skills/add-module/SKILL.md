---
name: add-module
description: Add a new module, port, provider, connector, or router to the Korchestrator SDK in the correct layer, with the tests, exports, docstrings and log entry that make it complete. Use when creating any new module under src/korchestrator/ or extending an existing extension point.
---

# Adding a module to the SDK

The mechanical steps are easy; the decisions are what this skill is for. Work through them in order.

## Step 1 — Should this module exist at all?

Answer honestly before writing anything:

- **Is it in scope?** (`docs/specs/01-scope-and-principles.md` §2–3.) HTTP servers, UI, deployment
  manifests, and re-implementations of sibling platform systems are permanently out.
- **Does something already own this concern?** There is exactly one router, one PII redactor, one
  error base, one config source. If you are adding a second, you are wrong — extend the existing one
  with a strategy.
- **Is it an abstraction?** If it is an interface, base class, factory, or plugin point, apply the
  abstraction test — all three must hold:
  1. Two real implementations exist or are committed in a named phase
  2. The axis of variation is stable
  3. It removes more code than it adds, or removes a dependency from an inner layer

  If any fails, write the concrete implementation instead. This is the single most common way this
  codebase gets worse.

## Step 2 — Pick the layer

| Kind of module | Goes in | May import |
|---|---|---|
| Port / protocol | `interfaces/` | `models/`, stdlib, pydantic |
| Domain model (DTO) | `models/` | stdlib, pydantic |
| Kernel logic | `core/` | `interfaces/`, `models/`, stdlib, pydantic — **nothing else** |
| Reasoning / agent | `agents/` | inward + `dspy` (lazy) |
| Feature (routing, tools, mcp, a2a, governance, persistence, context, events, taxonomy) | its own folder | `interfaces/`, `models/` only — **never a sibling feature** |
| ARI implementation | `providers/` | inward + its own dependency (lazy) |
| Runtime adapter | `runtime/` | inward + `temporalio` in `temporal_runtime.py` only (lazy) |
| Façade / wiring | `services/` | anything inward |
| Utility (config, exceptions, logging, telemetry, serializers, validators, security, types, constants) | its own folder | stdlib, pydantic; no upward deps |

If you cannot place it cleanly, the module is doing two things. Split it.

## Step 3 — Write the module

```python
"""One-line summary of the single responsibility.

Layer: <L1 core | L2 cognitive | feature | adapter | leaf utility>.
Allowed imports: <the explicit list>.
"""

from __future__ import annotations

__all__ = ["PublicName"]
```

Constraints: `<500` lines per file, `<50` lines per function, full type hints, `mypy --strict` clean,
explicit `__all__`, Google-style docstrings with runnable offline examples on every public callable.

**Dependencies.** Any new dependency belongs to an extra, is imported **inside the function that
needs it**, and raises `MissingExtraError` with the install command when absent. Adding a dependency
needs an ADR.

**Wiring.** The module does not construct its collaborators. It accepts them. Resolution happens once,
in `services/`.

**Configuration.** No `os.getenv`. Add the field to `Settings` and accept it as a parameter.

## Step 4 — Extension points: match the existing shape

If you are adding a provider, router, connector, or backend, read
`docs/specs/07-extensibility.md` first and implement the documented protocol exactly. Registration
happens at the composition root or via the documented entry-point group — never by editing core.

## Step 5 — Tests

`tests/unit/<layer>/test_<module>.py`, mirroring `src/`. The tests must **fail without the module**.

- Use deterministic fakes: MockLM, in-memory repository, injected fake clock, `respx` for HTTP.
- No network, no real model, no `sleep`, no wall-clock, no shared state.
- If it touches `core/`, `models/`, reducers, or serialization, add determinism tests: repeatability,
  reducer laws (property-based), replay if the Temporal path changed, serde round-trip stability.
- If it belongs to `core/` or `models/`, coverage floor is 95%.
- Assert on behaviour and outputs, not call counts.

## Step 6 — Exports and docs

- Public? Add it to `__init__.py` and `__all__`, update the golden snapshot file **deliberately**,
  and add a CHANGELOG entry in the same PR.
- Internal? Leave it out of `__all__` — an accidental export becomes a contract you must support.
- Update the module catalogue in `docs/specs/05-modules-and-data-models.md`.
- Add an example under `examples/` if it introduces a user-facing capability.

## Step 7 — Verify

Run `/verify`. All gates green, isolation gate printing `OK`. Report honestly what ran.

## Step 8 — Log it

Run `/log`. All ten fields in `.claude/memory/ENGINEERING_LOG.md`, plus a refresh of
`PROJECT_STATE.md`. The pre-commit hook blocks a `src/` change without it.

## Completion checklist

- [ ] In scope; no duplicate concern; abstraction test passes (if it is an abstraction)
- [ ] Correct layer; imports legal; no sibling imports; no cycles
- [ ] New dependency (if any) is an extra, lazy-imported, ADR'd
- [ ] Module docstring names the layer and allowed imports; explicit `__all__`
- [ ] Full type hints; `mypy --strict` clean; typed return, never a bare dict
- [ ] Docstrings with runnable offline examples
- [ ] Only `KorchError` subclasses escape; internal exceptions wrapped with `from exc`
- [ ] Tests fail without the change; determinism tests where required
- [ ] Exports, spec 05 catalogue, CHANGELOG, and examples updated
- [ ] `/verify` green; engineering log and project state updated
