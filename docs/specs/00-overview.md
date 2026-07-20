# 00 — Product Overview & Context

**Purpose:** Establish the shared mental model — what Korchestrator is, what problem it solves, why it is an SDK, and the vocabulary the rest of the specs use without redefining.
**Status:** Authoritative · **Phase:** governs all phases

**Read this when:** you are new to the repository, or you need the canonical definition of a term (superstep, swarm, ARI port, FractalFlow, MVC) used elsewhere in `docs/specs/`.

---

## 1. What this repository is

This repository is the **Korchestrator SDK** — an installable Python library (`korchestrator`) that packages the Korchestrator durable multi-agent execution kernel as a reusable framework.

It is **one product: the SDK**. Not a frontend, not a backend, not a hosted service. Developers integrate through code — `pip install korchestrator` and `from korchestrator import Korch` — they do not operate a service or hand-roll HTTP to get value.

The boundaries that follow from this are specified in [01-scope-and-principles.md](01-scope-and-principles.md) and are non-negotiable.

## 2. What Korchestrator is

Korchestrator (Kendra Orchestrator) is the **durable, multi-agent execution runtime — the kernel — of the Kendra Labs platform**. It owns the lifecycle of agent swarms: building, planning, running, monitoring, pausing, resuming, and executing them.

Technically, it runs each swarm as a **Pregel-style Bulk Synchronous Parallel (BSP) computation on top of Temporal**. That combination gives every multi-agent run four properties that ad-hoc agent frameworks do not have:

| Property | Mechanism |
|---|---|
| Crash-proof durability | Temporal event sourcing; every superstep is checkpointed |
| Deterministic replay | BSP supersteps + order-independent reducers + no nondeterminism in workflow scope |
| Parallel fan-out across 100+ agents | One `SuperstepActivity` fanning out with `asyncio.gather` |
| Bitemporal auditability | Valid-time + transaction-time on every recorded fact |

### 2.1 Three infrastructure primitives

1. **Temporal.io — durable workflow execution.** Every superstep is checkpointed, so crashes lose no progress, execution resumes, replay and time-travel debugging are possible, and human-in-the-loop pause/resume is native via durable signals (up to 24h).
2. **Pregel (BSP) — the parallel engine.** All active agents compute in parallel against a frozen state snapshot, exchange typed messages over directed edges, then a global synchronization barrier merges their outputs through deterministic **reducers**. No locks, no races, no last-writer-wins.
3. **DSPy compiled signatures — typed reasoning.** Reasoning is a declarative, typed, optimizable, versioned program rather than a fragile prompt string. Each agent can run on a **different model** within the same superstep via scoped `dspy.context(lm=...)`.

The execution model is specified in full in [06-execution-model.md](06-execution-model.md).

### 2.2 Scope boundary of the orchestrator itself

Korchestrator's scope is strictly the lifecycle of agent swarms. It is **not** the system of record for institutional knowledge, context creation, or identity storage — those belong to sibling platform systems. The SDK exposes orchestration; it does not re-implement memory, identity, or policy engines. Where it needs them, it defines a port and injects an implementation ([07-extensibility.md](07-extensibility.md)).

| Sibling system | Role | Relationship |
|---|---|---|
| **KACP** (Agentic Control Plane) | Policy Decision Point (PDP) | Governs what the orchestrator may do |
| **KCG** (Kendra Context Graph) | Bitemporal memory + decision-trace graph | Where the orchestrator writes memory and audit trail |
| **KMCP** (Kendra MCP Server) | Enterprise tool gateway, Policy Enforcement Point (PEP) | Every tool call flows through it |
| **KIAM** | Identity and access (JWTs, wallets) | Supplies tenant and agent identity |
| **Kendra AI Gateway** | Model hosting and routing | Where LLM calls are ultimately routed |

The SDK talks to all of these through the three ARI ports (§4) and runs correctly with none of them present.

## 3. The problem: why traditional orchestrators fail

As enterprises move from `A → B → C` pipelines to meshes where every agent may talk to every agent, coordination complexity grows roughly **O(N²)** and ad-hoc orchestration collapses. The answer is a central execution kernel that owns scheduling, synchronization, and communication.

| Traditional systems | Korchestrator |
|---|---|
| Linear DAG / fixed sequential pipelines | **FractalFlow** — recursive, event-driven, self-correcting, parallel |
| Stateless execution | **Event-sourced** execution (durable, replayable) |
| Vector RAG / prompt memory | **Context Graph** (bitemporal, governed, provenance, confidence) |
| Prompt-based and fragile | **Compiled signatures** (deterministic, reproducible, versioned) |
| No memory, hard recovery, poor coordination | Durable memory, deterministic recovery, synchronized coordination |

**Why not a DAG.** A directed *acyclic* graph cannot express the cyclic, self-correcting, dynamically branching behaviour real multi-agent systems need — reflection, retries, multi-turn negotiation. Pregel treats cycles as first-class. Execution is a continuous loop rather than a fixed path:

```
event → decision → branch → parallel agents → merge → feedback → repeat
```

**Agent execution is not code execution.** An agent may wait days for a human approval. Agent state is therefore decoupled from process state and made durable — an idle agent consumes no compute.

## 4. How the SDK differs from LangChain / CrewAI / AutoGen

| Dimension | LangChain / CrewAI / AutoGen | Korchestrator SDK |
|---|---|---|
| Failure model | In-memory; a crash loses all progress | Durable by default — resumes from the last superstep |
| Concurrency | Ad-hoc sequential/async, shared-state races | Deterministic Pregel BSP with conflict-free reducers |
| Model use | Typically one model per chain | Per-agent model isolation — heterogeneous models in one parallel step |
| Memory | Flat string / vector RAG | Bitemporal governed Context Graph + MVC compiler |
| Prompts | Fragile prompt strings | Compiled signatures (typed, versioned, reproducible) |
| Human-in-the-loop | Bolt-on callbacks | Native durable HITL via signals |
| Governance | None or bolt-on | Zero-trust governance (trust scores, policy, audit, approval) |
| Portability | Framework-coupled | ARI ports — run local with just a key, or plug into enterprise services with no agent-logic change |

This is not a generic prompt-chaining toolkit. It is a durable execution substrate for long-running, auditable, governed, multi-model agent workflows.

## 5. The ARI ports — the portability contract

The SDK interacts with the outside world through exactly three abstract ports. Each has a local default and an enterprise implementation.

| Port | Role | Local default | Enterprise implementation |
|---|---|---|---|
| `IIdentityProvider` | Authenticate agents to a DID | Local (unsecured) identity | KIAM / KACP |
| `IExecutionSandbox` | Isolated tool/code execution | Local subprocess | OpenSandbox |
| `IModelGateway` | Route reasoning to an LLM | Direct provider / MockLM | Kendra AI Gateway |

A developer runs the SDK with **just a model key and a local process**. As they scale they plug in enterprise implementations **without changing agent logic**. That is the entire point of the port boundary; see [03-architecture.md](03-architecture.md).

## 6. The five-layer control plane

| Layer | Name | Responsibility | SDK home |
|---|---|---|---|
| L1 | Runtime Kernel | Execution loop, scheduling, synchronization, communication | `core/`, `runtime/` |
| L2 | Cognitive Reasoning | Planning, LLM routing, task decomposition, validation | `agents/`, `routing/`, `taxonomy/` |
| L3 | Context Management | Context compiler, memory, state, event sourcing, Context Graph | `context/`, `persistence/`, `models/state.py` |
| L4 | Interface & Tool Integration | APIs, MCP, enterprise systems, search, databases | `tools/`, `mcp/`, `a2a/` |
| L5 | Governance & Security | RBAC, authz, audit, encryption, policy, PII redaction, HITL | `governance/`, `security/` |

The L1 runtime loop is: `receive event → reason → schedule → execute → synchronize → communicate → repeat`.

## 7. End-to-end flow the SDK must be able to drive

```
User goal → intent analysis → planner (cognitive) → compiled signature → context compiler
→ minimum viable context → FractalFlow graph generation → meta-agent optimization
→ task scheduling → parallel agent execution → tool/API/MCP integration
→ synchronization (Pregel supersteps) → context updates & event sourcing
→ governance & policy validation → observability & tracing → final response
```

Every capability in that flow must be reachable from the public API by the end of the build. The capability-to-module-to-phase mapping is the coverage contract in [11-build-phase-plan.md](11-build-phase-plan.md).

## 8. Repository starting point

This is a **greenfield repository**. There is no existing package, client, or docs site to migrate, and no backend here to read from.

Two consequences worth internalising:

- **No parity fallback.** Correctness is defined by these specs and the tests written alongside each phase — never by diffing against another implementation. An existing engine may be consulted as a behavioural reference, but is never imported, vendored, or required by CI.
- **Contracts are decided once.** Naming, version, license, extras matrix, auth scheme, and the remote contract are settled in Phase 0 and recorded in [`docs/adr/`](../adr/README.md). Later phases consume those decisions rather than re-opening them.

## 9. Glossary

Terms used throughout the specs without redefinition.

| Term | Meaning |
|---|---|
| **Swarm** | A directed graph of agents executed as one run |
| **Superstep** | One parallel round: compute → barrier → reduce → checkpoint |
| **Barrier** | The global synchronization point separating supersteps |
| **Reducer** | A deterministic, order-independent merge function for a state channel |
| **`StateUpdate`** | The typed delta an agent emits; agents never mutate shared state directly |
| **Frozen snapshot** | The immutable view of state an agent computes against during a superstep |
| **FractalFlow** | The recursive, cyclic, event-driven execution shape (as opposed to a DAG) |
| **ARI** | Agent Runtime Interface — the three ports in §5 |
| **AUB** | Agent Utility Bridge — the unified tool layer |
| **MVC** | Minimum Viable Context — the smallest context sufficient for a task |
| **Compiled signature** | A typed, versioned, optimizable DSPy reasoning program |
| **HITL** | Human-in-the-loop; a durable pause awaiting human input |
| **Trust score** | A 0.0–1.0 governance score that can gate a run into a paused state |
| **Bitemporal** | Carrying both valid-time (when true) and transaction-time (when recorded) |
| **Architect Agent** | The meta-agent that performs intent analysis and synthesizes the agent graph |
| **Tier 1–4** | The four levels of SDK usage — see [04-public-api.md](04-public-api.md) |

## 10. Honest status of the underlying platform

The durable execution kernel and its REST/SSE surface exist and work. Much of what turns it into a product — governed Context Graph retrieval, autonomous planning depth, the declarative authoring DSL, the studio UI — is backlog.

This shapes SDK scope directly, and the specs handle it with one consistent rule:

> **Interface now, implement minimally.** Where a capability is real, implement it. Where it is backlog, define the smallest port with an in-memory or no-op default so the SDK runs standalone, and leave the richer backend to a post-1.0 phase. Never build a speculative abstraction for a capability with no current implementation.

Applied cases: `GraphRepository` ships with an in-memory default (`PERSISTENCE_BACKEND=none` runs fully standalone); speculative execution, FinOps quotas, and the declarative DSL are out of scope for Phases 0–12 and are not reserved as abstractions.

---

**Next:** [01-scope-and-principles.md](01-scope-and-principles.md) — the rules that make these boundaries enforceable.
