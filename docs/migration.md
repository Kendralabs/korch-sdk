# Migration

Two different things use the word "migration" in this project — code you call, and data you've
persisted. This page covers both.

## API migrations (deprecated names)

!!! note "Nothing deprecated yet"
    Korchestrator is still on its first release, `0.1.0` — nothing in the public API has been
    deprecated yet. This section explains the mechanism so you know what to expect, and it's where
    a before/after example lands the day something *is* deprecated (see
    [Versioning](versioning.md#deprecation-policy) for the policy itself).

When a public name is renamed or replaced, the old name keeps working — it doesn't disappear the
same release it's replaced:

1. The deprecated name emits a `DeprecationWarning` on use, naming its replacement and the version
   it will be removed in.
2. It stays fully functional for **at least one full MINOR release** after the release that
   deprecates it — a deprecation never changes behavior on its own.
3. This page gains a section with a concrete before/after example, and the CHANGELOG carries the
   change under `### Deprecated` (and later `### Removed`).

A worked example of the *shape* this will take, once something is actually deprecated:

```python
# Before (deprecated in a hypothetical 0.4.0, still works, warns)
swarm.add_agent(agent)

# After (the replacement, available starting the same release)
swarm.add(agent)
```

Run your test suite with `-W error::DeprecationWarning` (or Python's `-W error` flag) periodically
to catch a deprecated call site before its removal version actually arrives.

## Data migrations (serialized state)

Separately from the API, every model in the compatibility surface that gets persisted —
`AgentState`, `ExecutionPlan`, `ModelCard`, `RunResult` — is serialized through
`korchestrator.to_json`/`from_json` with an explicit `schema_version` tag in the envelope, not
inferred from the payload shape.

```python
from datetime import datetime, timezone

from korchestrator import from_json, to_json
from korchestrator.models.state import AgentState

state = AgentState(
    run_id="r1", objective="summarize the quarterly report",
    transaction_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
)
payload = to_json(state)                     # {"schema_version": 1, "data": {...}, ...}
restored = from_json(payload, AgentState)    # applies registered migrations if payload is older
assert restored == state
```

If you've persisted checkpoints from an older version and upgrade the SDK, `from_json` applies any
registered migration for that model, in sequence, automatically — you don't hand-write a migration
script for your own data. If a payload's `schema_version` is *newer* than the installed package
supports (you downgraded, or a payload came from a newer writer), `from_json` raises
`ValidationError` rather than silently misreading it.

No schema version has moved past `1` yet, so no migration exists to demonstrate — this section
gains a concrete before/after the first time one ships.

## Next

- [Versioning](versioning.md) — the policy this page's mechanism serves.
- [Troubleshooting](troubleshooting.md) — what to do if `from_json` raises on your data.
