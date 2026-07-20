# Korchestrator SDK

**Durable, deterministic, multi-agent execution as an installable Python library.**

[![Status](https://img.shields.io/badge/status-pre--alpha-orange)](docs/specs/11-build-phase-plan.md)
[![Version](https://img.shields.io/badge/version-0.1.0--unreleased-blue)](docs/adr/0002-single-authoritative-version.md)
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.13-blue)](docs/specs/02-repository-structure.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](docs/adr/0003-license-apache-2-0.md)

> **Pre-implementation.** This repository currently contains the specification set, the architecture
> decision records, and the engineering configuration. The package source does not exist yet —
> Phase 0 scaffolds it. See [Project status](#project-status).

---

## What this is

Korchestrator runs multi-agent workflows ("swarms") as a **Pregel-style Bulk Synchronous Parallel
computation on top of Temporal**. That combination buys four things ad-hoc agent frameworks do not
have:

- **Durability** — every superstep is checkpointed. A crash resumes from the last barrier instead of
  losing the run.
- **Determinism** — agents compute against a frozen state snapshot and emit deltas that merge through
  order-independent reducers. Concurrency cannot change the result.
- **Real parallelism** — 100+ agents execute in one superstep, each able to run on a *different*
  model.
- **Auditability** — bitemporal decision records answer "what did the agent know when it decided?"

It is not a prompt-chaining toolkit. It is an execution substrate for long-running, auditable,
governed, multi-model agent workflows.

## Why not a DAG

A directed *acyclic* graph cannot express reflection, retries, or multi-turn negotiation — the
behaviours real multi-agent systems depend on. Pregel treats cycles as first-class, so execution is a
loop rather than a fixed path:

```
event → decision → branch → parallel agents → merge → feedback → repeat
```

## How it will be used

Four tiers, all from `from korchestrator import ...`. Tiers 1–3 run entirely in-process with no
service and no network.

```python
# Tier 1 — one-liner. Zero infrastructure.
from korchestrator import Korch
print(Korch().run("Research durable agent execution and summarize the top 3").final_answer)

# Tier 2 — typed swarm builder, per-agent model isolation.
from korchestrator import Swarm, Agent
result = (
    Swarm(objective="Review this PR for security and performance")
    .add(Agent(id="security", role="security-reviewer", model="claude-3.5-sonnet"))
    .add(Agent(id="perf", role="performance-reviewer", model="gpt-4o-mini"))
    .add(Agent(id="lead", role="review-lead"))
    .edges([("security", "lead"), ("perf", "lead")])
    .run(max_supersteps=5)
)

# Tier 3 — the kernel directly, for embedding.
from korchestrator.core import PregelRunner

# Tier 4 — drive a hosted engine (optional, [remote] extra).
from korchestrator.remote import KorchestratorClient
```

Full surface: [docs/specs/04-public-api.md](docs/specs/04-public-api.md).

## Installation

```bash
pip install korchestrator                 # core — depends on pydantic alone
pip install 'korchestrator[dspy]'         # cognitive layer (agents, compiled signatures)
pip install 'korchestrator[temporal]'     # durable runtime
pip install 'korchestrator[all]'          # everything
```

The base install has **one runtime dependency**. Everything heavy is an optional extra, lazy-imported
so `import korchestrator` stays fast and the kernel stays embeddable. The default configuration runs
offline against a deterministic mock model — no keys, no services, no infrastructure.

## Project status

Pre-alpha, private, and **not yet published**. Built in ordered phases:

| Phase | Delivers | Status |
|---|---|---|
| P0–P1 | Scaffold, decisions, frozen API contracts | Not started |
| P2–P3 | Pregel kernel; local + Temporal runtimes | Not started |
| P4–P5 | Agents, compiled signatures, model routing | Not started |
| P6–P7 | Tools/MCP/A2A, streaming, governance, context graph | Not started |
| P8–P9 | Cross-cutting foundations; remote client | Not started |
| P10–P12 | Testing, docs, CI/CD and publishing | Not started |

Current state, including known gaps: [`.claude/memory/PROJECT_STATE.md`](.claude/memory/PROJECT_STATE.md).

**Versioning.** [SemVer](docs/specs/10-release-versioning-and-cicd.md). While `0.x`, a **minor
release may contain breaking changes** — this is stated plainly in every changelog entry that
carries one. From `1.0.0` the full compatibility policy applies without exception.

## Documentation

| Start here | For |
|---|---|
| [docs/specs/README.md](docs/specs/README.md) | The authoritative specification set (00–12) |
| [docs/specs/00-overview.md](docs/specs/00-overview.md) | What Korchestrator is, and the glossary |
| [docs/specs/03-architecture.md](docs/specs/03-architecture.md) | Layering, ARI ports, the dependency rule |
| [docs/specs/04-public-api.md](docs/specs/04-public-api.md) | Public surface and compatibility contract |
| [docs/specs/11-build-phase-plan.md](docs/specs/11-build-phase-plan.md) | Phase objectives and acceptance criteria |
| [docs/specs/12-implementation-plan.md](docs/specs/12-implementation-plan.md) | **The step-by-step task list — start here to build** |
| [docs/adr/](docs/adr/README.md) | Why things were decided the way they were |
| [docs/background/](docs/background/README.md) | Superseded source inputs, kept for provenance |

## Contributing

Read [docs/specs/01-scope-and-principles.md](docs/specs/01-scope-and-principles.md) first — it
defines what belongs in this repository and what never will.

```bash
git clone <repository-url> && cd korch-sdk
pip install -e '.[dev]'
chmod +x .claude/hooks/pre-commit-check.sh   # once, after cloning

ruff check src/korchestrator tests
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing
```

Branch off `develop` as `<type>/p<phase>-<slug>`. Use Conventional Commits with a phase tag
(`feat(core): implement Pregel kernel + reducers [P2]`). Never commit directly to `main` or
`develop`, and never bypass the hooks. Every change touching `src/` updates
[`.claude/memory/ENGINEERING_LOG.md`](.claude/memory/ENGINEERING_LOG.md) before it is committed.

Working with an AI coding agent? The repository is configured for it: [`.claude/CLAUDE.md`](.claude/CLAUDE.md)
is the always-on ruleset, `.claude/rules/` holds the enforceable constraints, and `/phase`, `/verify`,
`/log`, and `/adr` cover the standard workflow.

## Non-goals

This repository ships **one product: the SDK**. It will never contain a frontend, a backend, an HTTP
server, or deployment manifests for a hosted service. "Deployment" here means publishing package
artifacts, not running anything. A hosted engine, if one exists, is a downstream consumer of the
published package — see [ADR 0007](docs/adr/0007-external-backend-boundary.md).

## License

Apache-2.0 — chosen for its explicit patent grant. See
[ADR 0003](docs/adr/0003-license-apache-2-0.md).
