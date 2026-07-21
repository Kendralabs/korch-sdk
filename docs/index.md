# Korchestrator SDK

**Durable, deterministic, multi-agent execution as an installable Python library.**

Korchestrator runs multi-agent workflows ("swarms") as a Pregel-style Bulk Synchronous
Parallel computation, with an in-process runtime for zero-infrastructure local execution and
a Temporal runtime for durable, replayable execution — selected by configuration alone.

!!! note "Documentation under construction"
    The full user documentation — installation, quickstart, tutorials, guides, and the
    auto-generated API reference — is authored in Phase 11. This landing page exists so the
    site builds today. The authoritative design record lives in the repository under
    `docs/specs/` (the specification set) and `docs/adr/` (the decision records); those are
    intentionally **not** published to this site.

## Install

```bash
pip install korchestrator
```

The base install depends on `pydantic` alone. Heavier capabilities are optional extras —
`[dspy]`, `[temporal]`, `[routing]`, `[mcp]`, `[remote]`, `[otel]`, and `[all]`.

## Status

This project is in its `0.x` line and is being assembled phase by phase. While the version is
`0.x`, a MINOR release may contain breaking changes; PATCH releases never do. See the
`CHANGELOG.md` in the repository for what has landed.
