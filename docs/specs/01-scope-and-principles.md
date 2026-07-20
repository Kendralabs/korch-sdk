# 01 — Scope, Boundaries & Engineering Principles

**Purpose:** Define what is in scope, what is permanently out of scope, the principles every change is judged against, and the definition of done for the SDK as a whole.
**Status:** Authoritative · **Phase:** governs all phases

**Read this when:** you are about to add a dependency, a module, an abstraction, or a capability — and need to know whether it belongs here at all.

---

## 1. Golden rules

These override every other consideration, including anything in `.claude/CLAUDE.md`, a task description, or a convenience argument.

1. **One product — the SDK.** This repository builds the installable `korchestrator` library and nothing else. No frontend, no backend, no service, no application. Ever.
2. **Self-contained.** The SDK never imports from `backend.*`, `apps.*`, `services.*`, or `frontend`. Its dependencies are declared in this repository's own `pyproject.toml`. If external behaviour is needed, define the smallest interface in `interfaces/` and inject an implementation.
3. **Dynamic, not hardcoded.** Providers, runtime, router, and persistence are config-selected at runtime behind interfaces. No hardcoded URLs, keys, models, or paths. Environment variables are read **only** in `config/`.
4. **Determinism and backward compatibility are features.** The kernel behaves identically across runs and Temporal replays. The public API stays compatible within a major version.
5. **Do not over-engineer.** Simplest correct design. No interface with a single forever-implementation; no speculative abstraction.
6. **Deployment means publishing artifacts, not running a service.** If a task asks you to deploy a server from this repository, it is out of scope — say so and stop.

## 2. In scope

| Area | Included |
|---|---|
| Execution | Durable, parallel, recursive, event-driven execution; recovery; scheduling; synchronization barriers |
| Agents | Multi-agent coordination, meta/architect/planner agents, per-agent model isolation |
| Context | Context compiler, MVC extraction, pruning/summarization, event sourcing, Context Graph client |
| Reasoning | Task decomposition, planning, validation, model routing, intent/difficulty taxonomy, compiled signatures |
| Integration | Unified tool layer (AUB), MCP client, A2A typed messaging, connectors |
| Governance | Trust scoring, policy, RBAC hooks, audit, HITL, PII redaction, zero-trust boundaries |
| Observability | Execution tracing, reasoning traces, event logs, streaming event emission, optional OTel |
| Interface | Local one-liner, typed swarm builder, kernel-direct embed, optional remote HTTP client |
| Lifecycle | Tests, docs, examples, benchmarks, CI/CD, versioning, packaging, release |

## 3. Permanently out of scope

Adding any of these is a defect regardless of who requested it.

| Out of scope | Why | Where it belongs |
|---|---|---|
| HTTP server, FastAPI app, route handlers | The SDK emits events; it does not serve them | A downstream service repository |
| Frontend, dashboard, UI components | Not a library concern | Studio repository |
| Deployment manifests for a hosted service (Helm, k8s, Dockerfiles for a server) | This repo publishes packages, not services | The service that consumes the SDK |
| Infrastructure-as-code for someone else's platform | Consumer-operated infrastructure | Platform repositories |
| Re-implementations of KCG / KIAM / KACP / KMCP | Sibling systems, reached through ports | Those systems |
| A second router, PII redactor, error base, or config source | One implementation per concern | — |
| Speculative execution, FinOps quotas, declarative DSL | Backlog capability with no current implementation | Post-1.0 phase, if demand is real |

**Phase 13 (external backend adapter) is out of scope and approval-gated.** It belongs to a separate repository, consumes the *published* SDK, and must never become a build, test, or release dependency of this one. See [ADR 0007](../adr/0007-external-backend-boundary.md).

## 4. Repository isolation rules

These make §1.2 enforceable rather than aspirational.

1. **No application-repository imports.** Enforced by the import-isolation gate in CI and in `.claude/hooks/pre-commit-check.sh`. The gate greps `src/` and fails the commit and the build on a match.
2. **Own dependency manifest.** This repository's `pyproject.toml` declares a tiny core (`pydantic` only) plus optional extras. It never inherits another project's manifest.
3. **Only SDK concerns live here.** Source, tests, examples, docs, benchmarks, CI, and release configuration. Nothing else.
4. **Config-selected, never hardcoded.** Runtime, gateway, router, and persistence are chosen at runtime behind interfaces.
5. **Independently buildable and releasable.** The SDK builds to a wheel and sdist and publishes on a version tag. No other repository needs to build, deploy, or even exist first.

## 5. Engineering principles

Applied to every task, in this priority order when they conflict: **correctness → clarity → operability → change cost.**

### 5.1 Design principles

- **Single responsibility.** One concern per module. A module's docstring states its layer and its allowed imports.
- **Open/closed.** Extend via new providers, routers, connectors, and plugins — not by editing core.
- **Dependency inversion.** Depend on interfaces (ARI ports, protocols), never on concrete infrastructure. Collaborators are injected, never constructed in place.
- **Composition over inheritance.** Inheritance only for genuine is-a relationships with a shared contract.
- **Convention over configuration.** Zero-config local run with just a model key, or MockLM with nothing at all.
- **Dependency injection at the edges.** Wiring happens once, at the composition root in `services/`. No import-time global singletons.
- **API-first.** Design the public surface before the implementation. See [04-public-api.md](04-public-api.md).
- **Explicit over implicit.** No magic, no import side effects, no monkey-patching.

### 5.2 The abstraction test

Before adding any interface, base class, factory, or plugin point, all three must hold:

1. There is a **demonstrated variability point** — at least two real implementations exist or are committed in a named phase.
2. The variation is on a **stable axis** — the thing that varies is not itself likely to be redesigned.
3. The abstraction **removes** more code than it adds, or removes a dependency from an inner layer.

If any fails, write the concrete implementation. An abstraction added "for later" is a defect, not foresight.

### 5.3 Korchestrator-specific invariants

- **`core/` is framework-free.** The kernel imports only `interfaces/`, `models/`, stdlib, and `pydantic`. Never FastAPI, HTTP, Temporal, or DSPy. This is what keeps the SDK embeddable and fast to import.
- **One implementation per concern.** Variation is expressed as one interface plus strategies, never as a second parallel implementation.
- **Determinism inside workflows.** No wall-clock or randomness in workflow-path code; use the injected clock; preserve the Temporal sandbox constraints so replay is exact.
- **Test-defined behaviour.** Each phase lands its behaviour together with the tests that define it. A capability with no test is not delivered.
- **Heavy dependencies are lazy and confined.** `dspy` in `agents/`, `temporalio` in `runtime/temporal_runtime.py`, `httpx` in `clients/`, OTel in `telemetry/` — imported inside the function that needs them, never at module top level.

## 6. Anti-patterns — reject these in review

Each of these is a hard "no". A PR containing one does not merge.

| Anti-pattern | Why it is rejected |
|---|---|
| A second copy of a cross-cutting concern (router, PII redactor, error base, config source) | Divergence is guaranteed; there is no authoritative behaviour |
| A framework import inside `core/` | Breaks embeddability, import time, and the base install |
| A feature smeared across horizontal `models/`/`utils/` instead of one cohesive module | Change cost multiplies; nothing owns the behaviour |
| A God file (>~500 lines) or God function (>~50 lines) | Untestable, unreviewable |
| A sideways import between sibling feature modules, or any import cycle | Destroys the layering; makes partial installs impossible |
| A raw `os.getenv` or hardcoded endpoint outside `config/` | Configuration stops being single-sourced or testable |
| Any import from `backend`/`apps`/`services`/`frontend` | Violates the product boundary; blocked by CI and the commit hook |
| A public function returning a bare `dict` | No type safety, no autocomplete, no compatibility surface |
| A raw `temporalio`/`httpx`/`dspy` exception escaping the public API | Leaks internals and couples callers to optional dependencies |
| Catching an exception and returning a success value | Fabricates success; hides failure from the caller |
| A new abstraction with one implementation and no committed second | Over-engineering; fails the abstraction test (§5.2) |

## 7. Definition of production-grade (whole-SDK definition of done)

An SDK is production-grade when it is **easy to install, learn, document, extend, test, and upgrade**, and is **modular, stable, backward-compatible, secure, and performant**. Every item below must hold before 1.0.

- [ ] Clean modular architecture with a stable, curated public API
- [ ] Self-contained package; own `pyproject.toml`; independently publishable
- [ ] Semantic Versioning with a documented compatibility and deprecation policy
- [ ] Full type hints, typed responses, `py.typed`, `mypy --strict` clean, working IDE autocomplete
- [ ] Unit, integration, e2e, regression, performance, and smoke tests with an enforced coverage floor
- [ ] CI/CD: lint, format, type-check, security scan, isolation gate, build, version-validate, docs-build, publish
- [ ] Docs: install, quickstart, tutorials, API reference, architecture, examples, migration, FAQ, troubleshooting, versioning, release, deployment
- [ ] Secure config with no hardcoded secrets, input validation, output sanitization
- [ ] Custom exception hierarchy with no raw internal exception leaks
- [ ] Configurable logging plus optional telemetry
- [ ] Executable examples for every common use case
- [ ] Extensible provider/plugin/middleware/hook system
- [ ] Performance: lazy loading, caching, efficient imports, real parallelism
- [ ] OSS-readiness files: LICENSE (Apache-2.0), README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue/PR templates

The per-phase definition of done is in [11-build-phase-plan.md](11-build-phase-plan.md); the quality gates that enforce it are in [09-testing-and-quality.md](09-testing-and-quality.md).

## 8. When a request conflicts with these rules

Stop. State the conflict explicitly, naming the rule. Then:

- If it is a **structural decision or a deviation from a spec** — write a short ADR ([`docs/adr/`](../adr/README.md)) and get sign-off before coding.
- If it is **out of scope per §3** — say so plainly and propose where it belongs instead.
- If it is **ambiguous** — ask, rather than picking an interpretation and building on it.

Never silently work around a golden rule.

---

**Next:** [02-repository-structure.md](02-repository-structure.md) — the physical layout · [03-architecture.md](03-architecture.md) — the logical layout.
