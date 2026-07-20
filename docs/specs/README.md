# Korchestrator SDK — Specification Set

**Purpose:** This directory is the authoritative design record for the Korchestrator SDK. Every
structural, behavioural, and process decision that governs this repository is recorded here.

**Read this when:** you are about to write code, review a PR, plan a phase, or resolve a
disagreement about how something in this repository should work.

---

## Authority

`docs/specs/` is authoritative. `.claude/CLAUDE.md` is a condensed, always-on operating summary for
agents and humans; it deliberately compresses and therefore loses nuance. **On any conflict between
`.claude/CLAUDE.md` and a document in this directory, the spec wins.** If a conflict is found, the
correct response is to fix `.claude/CLAUDE.md` in the same PR that discovers it — not to follow the
summary.

Source material lives in [`docs/background/`](../background/README.md) and is historical input. It
informed these specs; it does not override them, and it is excluded from the published docs site.

---

## The specification set

| # | Document | Purpose | Read this when |
|---|---|---|---|
| 00 | [00-overview.md](00-overview.md) | What Korchestrator is, the problem it solves, and the shape of the product | You are new to the project or need the one-page mental model |
| 01 | [01-scope-and-principles.md](01-scope-and-principles.md) | What is in scope, what is permanently out of scope, and the engineering principles that decide close calls | You are unsure whether a proposed capability belongs in this repository |
| 02 | [02-repository-structure.md](02-repository-structure.md) | The authoritative repository layout, naming conventions, root file inventory, `pyproject.toml`, and pre-commit config | You are adding a file, a module, a test, or a dependency |
| 03 | [03-architecture.md](03-architecture.md) | Layering, dependency direction, the ARI ports, and the framework-free kernel rule | You are placing new code in a layer or reviewing an import |
| 04 | [04-public-api.md](04-public-api.md) | The curated public surface: the four usage tiers, `__all__`, and the compatibility contract | You are adding, renaming, or removing anything a user can import |
| 05 | [05-modules-and-data-models.md](05-modules-and-data-models.md) | Every module's responsibility and every public Pydantic model | You need to know where a concern lives or what a model contains |
| 06 | [06-execution-model.md](06-execution-model.md) | Pregel supersteps, reducers, activation and halting rules, durability, and determinism | You are changing the kernel, a runtime adapter, or serialization |
| 07 | [07-extensibility.md](07-extensibility.md) | Providers, routers, connectors, MCP servers, persistence backends, middleware, and hooks | You are adding an extension point or a plugin |
| 08 | [08-configuration-and-cross-cutting.md](08-configuration-and-cross-cutting.md) | Settings precedence, environment variables, errors, logging, telemetry, security, validation | You are reading config, raising an error, or emitting a log or span |
| 09 | [09-testing-and-quality.md](09-testing-and-quality.md) | Test types, determinism testing, coverage policy, test doubles, benchmarks, quality gates, review expectations | You are writing tests, adding a gate, or reviewing a change |
| 10 | [10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) | SemVer and deprecation policy, version single-sourcing, CHANGELOG, CI/CD workflows, the release runbook | You are cutting a release, touching CI, or making a breaking change |
| 11 | [11-build-phase-plan.md](11-build-phase-plan.md) | Phases 0–12 with Objective / Build / Validation / Definition of Done per phase | You are starting a task and need its acceptance criteria |
| 12 | [12-implementation-plan.md](12-implementation-plan.md) | Task-level decomposition of every phase: deliverables, dependencies, acceptance, commit messages, critical path | You are about to start work and need to know what to do next |

---

## Reading order

**New human contributor (first day):** 00 → 01 → 03 → 04 → 02 → 09 → then 12 for the task list and
11 for its acceptance criteria. Read 05 and 06 when you first touch the kernel; read 10 before your
first release PR.

**AI agent starting a task:** 12 (find the next task, its deliverables and dependencies) → 11
(restate the phase Objective / Validation / DoD) → 01 (confirm scope) → 04 (design the public
surface first) → 03 and 02 (place the code correctly) → 09 (write the tests that lock the
behaviour) → 08 for cross-cutting concerns. Consult 05, 06, 07, and 10 as the task requires.

**Relationship between 11 and 12:** 11 is strategic — what each phase is for and when it is done.
12 is tactical — the ordered, individually-committable tasks that get there. 11 changes rarely;
12 is updated as tasks land.

---

## Related records

| Location | Contains | Authority |
|---|---|---|
| `docs/adr/` | Architecture Decision Records — one file per material decision, with context, decision, alternatives, consequences, and rollback | Authoritative for the decision it records; a spec change must cite its ADR |
| `.claude/memory/ENGINEERING_LOG.md` | The running engineering log — one ten-field entry per completed feature, refactor, or fix | Historical record, not a contract |
| `.claude/memory/PROJECT_STATE.md` | Current phase, what is done, what is next | Working state, not a contract |
| `CHANGELOG.md` | User-visible changes, Keep a Changelog format, ISO dates | Authoritative for what shipped in a release |
| `.claude/CLAUDE.md` | Condensed always-on ruleset | Subordinate to these specs |

---

## How to change a spec

1. **Material changes require an ADR.** A change is material if it alters the public API, the
   layering rules, the extras matrix, the auth scheme, the versioning or release policy, a quality
   gate, or the scope boundary. Write the ADR in `docs/adr/` first, using the standard sections
   (context, decision, alternatives considered, consequences, rollback). Reference the ADR from the
   spec section it changes.
2. **Editorial changes need no ADR.** Fixing a typo, clarifying wording without changing meaning,
   or repairing a broken link may land on its own.
3. **The spec and the code change in the same PR.** A spec that describes unbuilt behaviour is a
   plan, not a spec; a code change that contradicts a spec is a defect. Neither may merge alone.
   The only exception is a spec written ahead of implementation for a phase not yet started — such
   a section MUST be explicitly labelled with the phase that will deliver it.
4. **Do not duplicate.** Each fact lives in exactly one spec. Cross-reference with a relative link
   rather than restating; a copied fact will drift.
5. **Keep the index current.** Adding or retiring a spec means updating the table above in the same
   PR.
