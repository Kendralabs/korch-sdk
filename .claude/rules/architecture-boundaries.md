# Rule — Architecture boundaries

Repository-specific. The org-wide architecture baseline (`Fintricity/.claude/rules/architecture.md`)
still applies; this file adds the constraints unique to the SDK. Authority: `docs/specs/03-architecture.md`.

## The dependency rule

Dependencies point **inward**. Never outward, never sideways.

```
services (façade / composition root)
  → agents
    → core (Pregel)
      → interfaces / models
```

Feature modules (`routing`, `tools`, `mcp`, `a2a`, `governance`, `persistence`, `context`,
`events`, `runtime`, `taxonomy`) depend inward on `interfaces/` and `models/` only — **never on each
other**. `providers/`, `runtime/temporal_runtime.py`, and `clients/` implement interfaces.
`config`, `exceptions`, `logging`, `telemetry`, `serializers`, `validators`, `security`, `types`,
`constants` are leaf utilities with no upward dependencies.

## Non-negotiables

| # | Rule | If you think you need to break it |
|---|---|---|
| B1 | `core/` imports only `interfaces/`, `models/`, stdlib, `pydantic` | You need a port, not an import. Apply the abstraction test below. |
| B2 | No sibling imports between feature modules | Move the shared type to `models/` or the shared contract to `interfaces/` |
| B3 | No import from `backend`/`apps`/`services`/`frontend` (external packages) | Define the smallest interface in `interfaces/` and inject an implementation |
| B4 | No import cycles | The cycle is telling you two modules are actually one, or that a contract is missing |
| B5 | Heavy deps (`dspy`, `temporalio`, `httpx`, OTel, embeddings) are imported **inside the function that needs them**, in their one owning module | There is no exception. A top-level heavy import breaks the base install. |
| B6 | Env vars are read **only** in `config/` | Add the field to `Settings` and inject it |
| B7 | Wiring happens **only** in `services/`. Nothing below constructs its own collaborators. | Add the parameter and let the composition root resolve it |
| B8 | No import-time side effects, no module-level singletons | Use a lazily-resolved accessor behind the composition root |

`korchestrator.services` is this package's own façade and is legal. B3 forbids importing an
**external application package** named `services`.

## The abstraction test — all three must hold

Before adding any interface, base class, factory, or plugin point:

1. **Demonstrated variability** — two real implementations exist or are committed in a named phase.
2. **Stable axis** — the thing that varies is not itself likely to be redesigned.
3. **Net removal** — the abstraction removes more code than it adds, or removes a dependency from an inner layer.

If any fails, write the concrete implementation. An abstraction added "for later" is a defect.

## Optional-dependency contract

A missing extra must raise an actionable `KorchError`, never a bare `ImportError`:

```python
def _load_dspy():
    try:
        import dspy
    except ImportError as exc:
        raise MissingExtraError(
            "The cognitive layer requires the 'dspy' extra. "
            "Install it with: pip install 'korchestrator[dspy]'"
        ) from exc
    return dspy
```

## Before you add a module

Answer these in the PR description. If you cannot, the module is in the wrong place.

- Which layer does it belong to, and what is it allowed to import?
- Does an existing module already own this concern? (One implementation per concern — never a
  second router, redactor, error base, or config source.)
- Does it introduce a dependency? Which extra owns it?
- Is this in scope at all? (`docs/specs/01-scope-and-principles.md` §3)

## Enforcement

The isolation gate (`.claude/hooks/pre-commit-check.sh` and CI) blocks B3 at commit time.
`import-linter` contracts in CI block B1, B2, and B4. A unit test blocks B6. Treat a gate failure
as a design signal, never as an obstacle to route around — and never with `--no-verify`.
