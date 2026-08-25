# Korchestrator SDK

**Durable, deterministic, multi-agent execution as an installable Python library.**

!!! warning "Beta release — v0.1.0"
    Korchestrator is currently at **v0.1.0**, published for early access and beta testing.
    The kernel, execution model, and public API described on this site are implemented and
    tested (see [Status](#status) below) — this is working software, not a design sketch — but
    the public surface is still being validated against real integrations. While the version
    stays on the `0.x` line, a **minor** release may include breaking changes; every one is
    documented with a migration note. See [Versioning](versioning.md) for the exact compatibility
    promise, and treat anything not listed there as subject to change. Feedback on the API from
    this beta period is what determines what ships in `1.0`.

Korchestrator runs multi-agent workflows ("swarms") as a Bulk Synchronous Parallel superstep
computation, with an in-process runtime for zero-infrastructure local execution and a durable
workflow-engine runtime for crash-proof, replayable execution — selected by configuration alone,
with no change to agent code.

## Why this exists

Most agent frameworks treat a multi-agent run as a program: a script that calls models in some
order, holds its state in memory, and loses everything if the process dies. That model breaks down
exactly where multi-agent systems get interesting — many agents reasoning concurrently, a run that
needs to survive a crash or a multi-hour human approval wait, and a requirement to explain *why*
the system did what it did, after the fact, to someone who wasn't watching it happen.

Korchestrator treats a run as **computation over state**, not a script, borrowing three ideas that
each solve one piece of that problem:

| Problem | Idea borrowed from | What it buys |
|---|---|---|
| Concurrent agents racing on shared state | **Bulk Synchronous Parallel (BSP)** — the model large-scale graph-processing systems use | Every agent computes against the same frozen snapshot; results never depend on which agent happened to finish first |
| A crash, or a human taking hours to approve a step | **Durable, event-sourced workflow execution** | Every superstep is checkpointed; a crash resumes instead of restarting, and a run can pause for days awaiting review |
| "Why did the system decide that?", asked later | **Bitemporal record-keeping** (valid-time and transaction-time, distinct) | Every fact carries both *when it was true* and *when the system learned it* — an audit trail that survives later corrections |
| Fragile, hand-tuned prompt strings | **Typed, compiled reasoning signatures** (via DSPy) | Reasoning is a versioned, optimizable program, not a string a refactor can silently break |

None of these ideas are novel on their own — this is where they combine specifically for
multi-agent LLM orchestration. See [Architecture](architecture.md) for the mechanics, and
[docs/specs/00-overview.md](https://github.com/kendralabs/korch-sdk/blob/main/docs/specs/00-overview.md)
in the repository for the full design rationale, including how this differs concretely from
ad-hoc chain/graph-based agent frameworks.

## Get started

- [Installation](installation.md) — the base install and every optional extra
- [Quick Start](quickstart.md) — install to your first completed run
- [Tutorials](tutorials/index.md) — swarms, custom agents/tools/routers, MCP, human-in-the-loop, streaming
- [Architecture](architecture.md) — how the superstep kernel, the ARI ports, and the layering fit together, and why
- [API Reference](reference/index.md) — the full public surface
- [Contributing & Feedback](contributing.md) — report a bug, request a feature, or contribute code

## Status

Phases 0 through 11 (kernel, runtimes, agents, routing, tools/MCP/A2A, governance, cross-cutting
foundations, testing, and this documentation) are complete and covered by the test suite described
in [docs/specs/09-testing-and-quality.md](https://github.com/kendralabs/korch-sdk/blob/main/docs/specs/09-testing-and-quality.md).
`v0.1.0` is tagged and published as a
[GitHub Release](https://github.com/kendralabs/korch-sdk/releases/tag/v0.1.0) on this private
repository — not yet on PyPI, a deliberate, documented choice while the repository stays private
(see [Releases](releases.md)).

"Complete" describes what has shipped and is tested — not a claim that the public API is frozen.
That's exactly what the `0.x` line and this beta period are for: see
[Versioning](versioning.md) for what's covered by the compatibility promise today, and the
`CHANGELOG.md` in the repository for what has landed release by release.
