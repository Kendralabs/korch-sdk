# Korchestrator SDK

**Durable, deterministic, multi-agent execution as an installable Python library.**

Korchestrator runs multi-agent workflows ("swarms") as a Pregel-style Bulk Synchronous
Parallel computation, with an in-process runtime for zero-infrastructure local execution and
a Temporal runtime for durable, replayable execution — selected by configuration alone.

!!! note "Documentation in progress"
    Installation and the Quick Start are published. Tutorials, the auto-generated API reference,
    and the user guides (architecture, versioning, deployment, migration, FAQ, troubleshooting)
    are still being authored (Phase 11). The authoritative design record lives in the repository
    under `docs/specs/` (the specification set) and `docs/adr/` (the decision records); those are
    intentionally **not** published to this site.

## Get started

- [Installation](installation.md) — the base install and every optional extra
- [Quick Start](quickstart.md) — install to your first completed run

## Status

This project is in its `0.x` line and is being assembled phase by phase. While the version is
`0.x`, a MINOR release may contain breaking changes; PATCH releases never do. See the
`CHANGELOG.md` in the repository for what has landed.
