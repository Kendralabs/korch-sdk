# Rule — Determinism

Repository-specific and the easiest rule in this codebase to violate by accident. Determinism is a
**product feature**: the kernel must behave identically across runs and across Temporal replays.
Authority: `docs/specs/06-execution-model.md`.

## Applies to

Any code on the **workflow path**: `core/`, `models/`, `runtime/*_runtime.py` workflow scope, the
reducers, the graph, and anything they call. It does **not** apply inside activities, providers, or
tool connectors — that is exactly where nondeterminism is supposed to live.

## The four hard rules

| # | Rule | Instead |
|---|---|---|
| D1 | No wall-clock in workflow scope — `datetime.now()`, `time.time()`, `date.today()` | The runtime's injected clock |
| D2 | No randomness in workflow scope — `random`, `uuid4()`, `secrets`, unseeded sampling | An injected seeded source, or generate it in an activity and pass it in |
| D3 | No I/O in workflow scope — network, filesystem, database, model calls | Move it into an activity; the workflow orchestrates, activities act |
| D4 | No dependence on iteration or completion order | Reducers must be order-independent (§ below) |

## Why: the replay contract

Temporal re-executes workflow code from the event history to rebuild state. If the code takes a
different path on replay than it did originally, the workflow is corrupt. Anything nondeterministic
in workflow scope guarantees that eventually. The `local_runtime` will not catch this for you — a
bug of this class is invisible locally and fatal in production.

## The frozen-snapshot rule

Agents compute against an **immutable snapshot** of state and emit `StateUpdate` deltas. They never
mutate shared state.

- No agent may observe another agent's partial work within the same superstep.
- Results therefore cannot depend on scheduling order.
- Mutating shared state from inside an agent is a defect even when the tests pass.

## Reducer laws

Every reducer MUST satisfy these, and every reducer MUST have a property-based test proving it:

| Law | Meaning | Why it matters |
|---|---|---|
| **Associative** | `f(f(a,b),c) == f(a,f(b,c))` | The barrier can merge in any grouping |
| **Order-independent** | The merged result does not depend on `asyncio.gather` completion order | Concurrency cannot change the outcome |
| **Total** | Defined for every valid input, including empty and single-element | No merge can crash the barrier |

`UniqueAppend` and `MergeDict` are additionally **idempotent** — merging the same delta twice must
equal merging it once, because at-least-once delivery is a real condition.

## Serialization determinism

Serialization is part of the replay surface. It MUST be:

- **Stable** — sorted keys, no set iteration order, no `id()`-derived values, no locale dependence.
- **Version-tagged** — every serialized payload carries a schema version.
- **Round-trip exact** — `from_json(to_json(x)) == x` for every public model, tested across a
  version bump.

## Checklist before committing kernel or runtime code

- [ ] No `datetime.now()`, `time.time()`, `random`, or `uuid4()` in workflow-path code
- [ ] No I/O in workflow scope
- [ ] New reducers have property-based tests for associativity and order-independence
- [ ] A repeatability test asserts identical results across repeated runs of the same graph and seed
- [ ] If the Temporal path changed: the replay test passes
- [ ] If a serialized model changed: the schema version bumped and round-trip stability holds

## Grep for your own mistakes

```bash
grep -rnE "datetime\.now|time\.time\(|uuid4\(|\brandom\." src/korchestrator/core src/korchestrator/models
```

This must return nothing.
