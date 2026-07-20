# Rule — Python standards

Repository-specific. The org-wide engineering baseline still applies.
Authority: `docs/specs/05-modules-and-data-models.md`, `docs/specs/08-configuration-and-cross-cutting.md`.

## Typing

- Python ≥3.10, `src/` layout, full type hints, `mypy --strict` clean. `py.typed` ships in the wheel.
- Public functions return **typed Pydantic models, never a bare `dict`**.
- Use modern syntax: `X | None` not `Optional[X]`, `list[str]` not `List[str]`.
- `Protocol` for structural contracts (the ARI ports); `ABC` only when shared implementation exists.
- No `Any` in a public signature. If you genuinely need it, justify it in a comment.
- Builder methods return `Self` so chaining type-checks.

## Module shape

- One responsibility per module. `<500` lines per file, `<50` lines per function.
- Explicit `__all__` in every module.
- A module docstring stating **its layer and its allowed imports**:

```python
"""Pregel BSP kernel.

Layer: L1 core (framework-free).
Allowed imports: korchestrator.interfaces, korchestrator.models, stdlib, pydantic.
"""
```

## Naming

| Thing | Convention |
|---|---|
| Classes | `PascalCase` |
| Functions, modules, variables | `lower_snake` |
| ARI ports | `I<Name>` — `IModelGateway` |
| Constants | `UPPER_SNAKE` |
| Private | `_leading_underscore` |
| The remote client class | `KorchestratorClient` — always, everywhere |

Use the canonical vocabulary in `docs/specs/04-public-api.md` §3.1: `run`, `run_swarm`,
`run_and_wait`, `run_id`, `superstep`, `final_answer`, `StateUpdate`. One concept, one name — in
code, docstrings, docs, examples, and error messages.

## Errors

- Everything catchable is a `KorchError` subclass: `AuthError`, `ValidationError`, `NetworkError`,
  `ProviderError`, `TimeoutError`, `RateLimitError`, `QuotaExceededError`, `RoutingError`,
  `GovernanceHaltError`, `RunFailedError`, `RunTimeoutError`, `ToolError`, `MissingExtraError`.
- **Never leak a raw `temporalio`/`httpx`/`dspy` exception.** Wrap with `raise ... from exc`.
- Never catch an exception and return a success value. Never swallow an exception silently.
- Messages are **actionable** — say what failed, why, and what to do:

```python
# Bad
raise ValidationError("invalid objective")

# Good
raise ValidationError(
    f"Objective must be at least 10 characters, got {len(objective)}. "
    f"Describe the goal in a sentence, e.g. 'Summarize Q3 incident reports'."
)
```

## Logging

- One namespaced logger: `logging.getLogger("korchestrator")`, with a `NullHandler`, **off by default**.
- Never mutate the root logger. Never use `print()`. Never log credentials, tokens, or PII.
- Structured fields, not interpolated prose: `logger.info("superstep.complete", extra={...})`.

## Docstrings

Google style on every public callable, with a **runnable example** that works offline (MockLM or
fixture data). The example is collected as a doctest — if it cannot run in CI, it is wrong.

```python
async def run(self, objective: str, *, max_supersteps: int = 10) -> RunResult:
    """Run a swarm against an objective and return the terminal result.

    Args:
        objective: The goal, at least 10 characters.
        max_supersteps: Hard halt bound. Defaults to 10.

    Returns:
        The terminal :class:`RunResult`, including ``final_answer``.

    Raises:
        ValidationError: If ``objective`` is shorter than 10 characters.
        RunTimeoutError: If the run exceeds ``max_supersteps``.

    Example:
        >>> from korchestrator import Korch
        >>> result = Korch(mock=True).run("Summarize durable agent execution")
        >>> result.status
        'completed'
    """
```

## Pydantic

- Pydantic v2 syntax. `model_config` not inner `Config`.
- Models on the workflow path are **frozen** (`model_config = ConfigDict(frozen=True)`) — the
  frozen-snapshot rule depends on it.
- Every field typed and documented. Optional fields have defaults so adding one stays non-breaking.
- Validate at trust boundaries; fail fast with actionable messages.

## Async

- The kernel is async-first. Provide a sync wrapper where it materially helps DX.
- Never block the event loop. Run blocking work (DSPy calls) via `asyncio.to_thread` so superstep
  parallelism is real rather than nominal.
- Never create an event loop inside library code.
