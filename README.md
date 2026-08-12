# Kendra Orchestration Engine (KOE)

**Durable, deterministic, multi-agent execution as an installable Python library.**

[![Status](https://img.shields.io/badge/status-alpha-orange)](docs/specs/11-build-phase-plan.md)
[![Version](https://img.shields.io/badge/version-0.1.0-blue)](docs/adr/0002-single-authoritative-version.md)
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.13-blue)](docs/specs/02-repository-structure.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](docs/adr/0003-license-apache-2-0.md)

> **First release, distributed privately.** Phases 0–11 are complete; `v0.1.0` is tagged and
> published as a GitHub Release on this private repo, not on PyPI
> ([ADR 0020](docs/adr/0020-private-distribution-defers-pypi-publishing.md)) — see
> [Installation](#installation). See [Project status](#project-status).

---

## What this is

KOE runs multi-agent workflows ("swarms"). That combination buys four things ad-hoc agent frameworks do not
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
behaviours real multi-agent systems depend on. The superstep kernel treats cycles as first-class, so
execution is a loop rather than a fixed path:

```
event → decision → branch → parallel agents → merge → feedback → repeat
```

## How it's used

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

## Features

Everything below ships and is tested today — see [Project status](#project-status) for what's
still outstanding. 26 subpackages under `src/korchestrator/`, each with a single layer and a
single responsibility ([docs/specs/03-architecture.md](docs/specs/03-architecture.md)):

| Module | Layer | What it does |
|---|---|---|
| `services` | Façade | Composition root — the `Korch` / `Swarm` / `Agent` builders, hooks and middleware |
| `core` | Kernel | The BSP superstep kernel — graph, supersteps, reducers, activation and halting |
| `runtime` | Adapter | `IDurableRuntime` twice over: in-process `local_runtime` and durable, replayable `temporal_runtime` |
| `agents` | Cognitive | DSPy-backed reasoning — agent base, `WorkerAgent`, `ArchitectAgent`, compiled signatures |
| `taxonomy` | Cognitive | Classifies an objective's intent/difficulty; holds the built-in agent-descriptor catalogue |
| `routing` | Cognitive | Per-agent model selection — explicit/fallback, algorithmic, semantic, composite/user-function strategies |
| `providers` | Adapter | Default ARI implementations — `MockLM` (offline default), OpenAI-compatible gateway, local identity/sandbox |
| `tools` | Integration | Agent Utility Bridge — connector registry, schema validation, timeouts, rate limits, the Shield gate |
| `mcp` | Integration | Model Context Protocol client — discovers a server's tools and exposes them as connectors |
| `a2a` | Integration | Agent-to-agent handoffs, transformed into typed directed messages |
| `context` | Context | Compiles execution context; extracts the Minimum Viable Context and prunes the hot loop |
| `events` | Integration | Publishes transport-agnostic execution events (the SDK emits, it never serves HTTP) |
| `governance` | Governance | Trust scoring, policy evaluation, human-in-the-loop pause/resume decisions |
| `security` | Leaf | `Shield` — the one PII/secret redactor |
| `persistence` | Context | Bitemporal Context Graph client behind `GraphRepository` (in-memory default backend) |
| `models` | Contract | The frozen Pydantic domain models exchanged across every boundary |
| `interfaces` | Contract | The ARI ports (`IIdentityProvider`, `IExecutionSandbox`, `IModelGateway`) and supporting protocols |
| `exceptions` | Leaf | The whole `KorchError` tree — every deliberate SDK error is one subclass |
| `config` | Leaf | The only module that reads env/`.env`; owns `Settings` and `configure()`/`get_settings()` |
| `constants` | Leaf | Default values, error-code enums, event names |
| `types` | Leaf | Shared type aliases, `TypedDict`s and non-ARI protocols |
| `validators` | Leaf | Boundary validation for parameters, config, graphs, tool schemas and responses |
| `logging` | Leaf | The namespaced `korchestrator` logger and `enable_logging()`/`disable_logging()` |
| `serializers` | Leaf | Deterministic, version-tagged JSON round-tripping for `AgentState`/`ExecutionPlan`/`ModelCard`/`RunResult` |
| `telemetry` | Leaf | Optional OpenTelemetry spans/metrics, zero cost when disabled (`[otel]`) |
| `clients` | Client | `KorchestratorClient` — the Tier-4 remote HTTP client (`[remote]`), re-exported as `korchestrator.remote` |

Capability highlights that fall out of those modules:

- **Local or durable execution** — the same graph runs synchronously in-process or on a durable
  workflow engine with crash recovery, pause/resume, and replay, chosen by one config value.
- **Per-agent model routing** — mix models (and providers) in a single swarm; route explicitly, by
  algorithm, by semantic similarity, or by your own function.
- **Tool use** — first-party connectors, MCP servers, and custom connectors behind one bridge with
  schema validation, timeouts, and rate limiting.
- **Governance & HITL** — trust scoring and policy checks that can auto-pause a run for human
  approval (durable runtime only).
- **PII/secret redaction** — the `Shield` gate, applied on tool output and context-graph ingest.
- **Bitemporal audit trail** — the Context Graph answers "what did the agent know when it decided?"
- **Streaming** — subscribe to transport-agnostic execution events as a run progresses.
- **Deterministic testing** — `MockLM` is the default model gateway; nothing touches the network
  unless you configure a real one.

## Installation

**Distributed privately, not on PyPI** — `Kendralabs/korch-sdk` is a private repository and stays
that way ([ADR 0020](docs/adr/0020-private-distribution-defers-pypi-publishing.md)). Install a
released version straight from a tag (needs a GitHub credential with read access to this repo):

```bash
pip install "korchestrator[dspy] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
pip install "korchestrator[all] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
```

or from a local clone:

```bash
git clone git@github.com:Kendralabs/korch-sdk.git && cd korch-sdk
pip install -e '.[dspy]'      # cognitive layer (agents, compiled signatures) — most users need this
pip install -e '.[all]'       # everything
```

See [docs/installation.md](docs/installation.md) for the full extras table and credential setup
(SSH key vs. PAT), and [docs/releases.md](docs/releases.md) for how releases are cut and tagged.

The base install has **one runtime dependency**. Everything heavy is an optional extra, lazy-imported
so `import korchestrator` stays fast and the kernel stays embeddable. The default configuration runs
offline against a deterministic mock model — no keys, no services, no infrastructure.

> **Windows note.** `pip install -e '.[dev]'` installs console scripts (`mkdocs`, `pytest`, `ruff`,
> `mypy`, `bandit`, `pre-commit`, …) into your per-user `Scripts` directory (e.g.
> `%APPDATA%\Python\Python3xx\Scripts`). If a bare command isn't found right after install, either
> run it as `python -m <tool>` (e.g. `python -m mkdocs serve`) in the current shell, or add that
> `Scripts` directory to your user `PATH` and open a new terminal. See
> [docs/troubleshooting.md](docs/troubleshooting.md).

## Quick start — first run to a passing test suite

A complete, ordered sequence from a clone to a verified local setup. Every step runs offline; none
of it needs API keys, Docker, or a deployed service.

```bash
# 1. Clone and install (dev extras: every extra + lint/type/test/docs tooling)
git clone <repository-url> && cd korch-sdk
pip install -e '.[dev]'

# 2. Verify the import — works on the base install, no extras, no network
python -c "import korchestrator; print(korchestrator.__version__)"

# 3. Run your first swarm, entirely offline against MockLM
python examples/01_one_liner.py
python examples/02_swarm.py          # typed builder, multiple agents, per-agent models

# 4. Explore the rest of the example set
python examples/03_custom_agent.py   # subclass Agent, override its reasoning step
python examples/04_custom_tool.py    # write and mount a custom tool connector
python examples/05_mcp_tool.py       # discover tools from an MCP server (needs [mcp])
python examples/06_custom_router.py  # write a custom per-agent model router
python examples/07_streaming.py      # consume execution events as a run progresses

# 5. Run the full quality gate the way CI does
ruff check src/korchestrator tests
ruff format --check src/korchestrator tests
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing

# 6. Build and preview the documentation site locally
mkdocs build --strict
mkdocs serve      # → http://127.0.0.1:8000
```

(Use `python -m mkdocs`, `python -m pytest`, etc. in place of the bare command if step 1's console
scripts aren't on `PATH` yet — see the Windows note above.)

### Testing a single module

Tests mirror `src/korchestrator/<module>` one-to-one under `tests/unit/<module>/`. Run just one
module's suite while you're working on it:

```bash
pytest tests/unit/core -v          # kernel
pytest tests/unit/providers -v     # MockLM, gateways, identity/sandbox
pytest tests/unit/routing -v       # model routing strategies
pytest tests/unit/tools -v         # Agent Utility Bridge
pytest tests/unit/governance -v    # trust scoring, policy, HITL
pytest tests/unit/clients -v       # remote client contract
```

Other suites live in `tests/integration/`, `tests/e2e/`, `tests/regression/`, and `tests/smoke/`.
The **base-install kernel suite** — what must pass with only `pydantic` installed, no extras — is:

```bash
pytest tests/unit/core tests/unit/models tests/smoke
```

Coverage floor: 90% global, 97% for `core/`, 99% for `models/` — ratcheted up over time, never down.
Full command reference: [docs/specs/09-testing-and-quality.md](docs/specs/09-testing-and-quality.md).

## Project status

`v0.1.0` released (privately). Built in ordered phases:

| Phase | Delivers | Status |
|---|---|---|
| P0–P1 | Scaffold, decisions, frozen API contracts | **Complete** |
| P2–P3 | Superstep kernel; local + durable runtimes | **Complete** |
| P4–P5 | Agents, compiled signatures, model routing | **Complete** |
| P6–P7 | Tools/MCP/A2A, streaming, governance, context graph | **Complete** |
| P8–P9 | Cross-cutting foundations; remote client | **Complete** |
| P10 | Testing, benchmarks & quality gates | **Complete** |
| P11 | Documentation, examples & DX | **Complete** |
| P12 | CI/CD, packaging & publishing | Private-distribution pipeline shipped (ADR 0020); PyPI publishing deferred |

Current state, including known gaps: [`.claude/memory/PROJECT_STATE.md`](.claude/memory/PROJECT_STATE.md).

**Versioning.** [SemVer](docs/specs/10-release-versioning-and-cicd.md). While `0.x`, a **minor
release may contain breaking changes** — this is stated plainly in every changelog entry that
carries one. From `1.0.0` the full compatibility policy applies without exception.

## Documentation

The published docs site ([`docs/`](docs/), built with MkDocs — `mkdocs serve` to preview locally):

| Start here | For |
|---|---|
| [docs/installation.md](docs/installation.md) | The base install and every optional extra |
| [docs/quickstart.md](docs/quickstart.md) | Install to your first completed run |
| [docs/tutorials/](docs/tutorials/index.md) | Swarms, custom agents/tools/routers, MCP, HITL, streaming |
| [docs/reference/](docs/reference/index.md) | Auto-generated API reference |

The engineering record (not published to the docs site — internal, for anyone building the SDK
itself):

| Start here | For |
|---|---|
| [docs/specs/README.md](docs/specs/README.md) | The authoritative specification set (00–12) |
| [docs/specs/00-overview.md](docs/specs/00-overview.md) | What Korchestrator is, and the glossary |
| [docs/specs/03-architecture.md](docs/specs/03-architecture.md) | Layering, ARI ports, the dependency rule |
| [docs/specs/04-public-api.md](docs/specs/04-public-api.md) | Public surface and compatibility contract |
| [docs/specs/12-implementation-plan.md](docs/specs/12-implementation-plan.md) | The step-by-step task list |
| [docs/adr/](docs/adr/README.md) | Why things were decided the way they were |
| [docs/background/](docs/background/README.md) | Superseded source inputs, kept for provenance |

## Contributing

Read [docs/specs/01-scope-and-principles.md](docs/specs/01-scope-and-principles.md) first — it
defines what belongs in this repository and what never will. Follow [Quick start](#quick-start--first-run-to-a-passing-test-suite)
above to get installed and green, plus this one extra step:

```bash
chmod +x .claude/hooks/pre-commit-check.sh   # once, after cloning — enforces the gates below at commit time
```

Branches promote forward only: `dev` (integration) → `staging` (release candidate) → `main`
(released, and the repository default). Branch off `dev` as `<type>/p<phase>-<slug>` and open the
PR against `dev` — GitHub proposes `main`, which is wrong for feature work. Use Conventional
Commits with a phase tag (`feat(core): implement superstep kernel + reducers [P2]`). Never commit
directly to `dev`, `staging`, or `main`, and never bypass the hooks. Every change touching `src/`
updates [`.claude/memory/ENGINEERING_LOG.md`](.claude/memory/ENGINEERING_LOG.md) before it is
committed. The full model, including the hotfix exception, is in
[`.claude/rules/branching-and-promotion.md`](.claude/rules/branching-and-promotion.md).

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
