# Architecture Decision Records

**Purpose:** This directory records *why* the Korchestrator SDK is the way it is. Each ADR captures
one material decision, the forces that shaped it, the alternatives that lost, and what reversing it
would cost.

**Read this when:** you are about to make a decision that will outlive the PR making it, you are
reviewing a change that contradicts an existing rule, or you want to know why something is the way
it is before proposing that it be different.

---

## What an ADR is here

An ADR is a short, immutable record of a decision — not a design document, not a tutorial, and not a
status report. It answers one question: *given these forces, what did we decide, and what did it
cost?*

Three records, three jobs. Do not blur them:

| Record | Answers | Mutability |
|---|---|---|
| `docs/adr/` (here) | **Why** we decided something, and what we rejected | Immutable once Accepted — supersede, never edit |
| `docs/specs/` | **What** the resulting design is | Living; changes with the code, in the same PR |
| `.claude/memory/ENGINEERING_LOG.md` | **What was actually built**, when, by whom | Append-only history |

A spec section that records a material decision must cite the ADR that made it. An ADR that has no
corresponding spec change has decided something nobody implemented.

---

## When an ADR is REQUIRED

Write an ADR before merging any change that:

- **Alters a public API contract** — anything in `korchestrator.__all__`, an ARI port, a documented
  model, or the remote contract in `docs/specs/`. This includes renames and signature changes, not
  only removals.
- **Adds, removes, or renames a dependency or an extra** — the base install is `pydantic` only, and
  extras names are part of the public contract (ADR 0004).
- **Changes a boundary or the layering rules** — what may import what, where a concern lives, or the
  introduction of a new port or abstraction layer.
- **Deviates from `docs/specs/`** in any structural way. If the spec says one thing and you are
  about to do another, the ADR is how you make that legitimate. Doing it without one is a defect.
- **Sets or changes a security-relevant default** — authentication, credential handling, redaction,
  fail-open versus fail-closed behaviour, tenant scoping.
- **Is a breaking change** of any kind. Per `.claude/CLAUDE.md` §8, a breaking change requires an
  ADR plus a migration note and a major-bump plan.

**No ADR needed for:** bug fixes that restore documented behaviour, refactors that preserve the
public surface and the layering, added tests, documentation edits, or dependency version bumps
within an already-declared range.

**When in doubt, write one.** A short ADR that turns out to have been unnecessary costs twenty
minutes. An undocumented decision costs an argument every six months, forever.

---

## Numbering

- Zero-padded four digits: `0001`, `0002`, … `0042`.
- **Monotonic.** Each new ADR takes the next unused number.
- **Never reused.** A number is permanently bound to its decision, including if that decision is
  later superseded or rejected. A superseded ADR stays in the directory with its original number and
  content — the history is the point.
- Filename: `NNNN-kebab-case-title.md`. The title in the filename should match the `# ADR NNNN —`
  heading inside.
- `0000-template.md` is the template and is not a decision.

If two PRs claim the same number concurrently, the second to merge renumbers. Check the directory
listing, not your memory.

---

## Status lifecycle

```
Proposed  ──approved in PR──▶  Accepted  ──replaced by a later ADR──▶  Superseded
    │
    └──rejected in PR──▶  Rejected (kept in the directory, number retained)
```

- **Proposed** — written, under review, not yet binding.
- **Accepted** — merged and binding. **The file is now immutable.** The only permitted edit is
  filling in the `Superseded by` field.
- **Superseded** — a later ADR replaced it. Both files record the relationship: the old one names
  its successor, the new one names what it supersedes.
- **Rejected** — considered and declined. Kept, because "we thought about that and here is why not"
  is worth as much as a yes.

**You supersede; you never edit.** Editing an Accepted ADR destroys the record of what was believed
at the time, which is the only thing an ADR is for. If the decision was right but the wording is
wrong, fix the spec. If the decision was wrong, supersede it.

---

## Process

1. **Copy `0000-template.md`** to `NNNN-your-title.md` using the next unused number. Set Status to
   `Proposed`.
2. **Fill in every section.** An empty section is a defect. The Alternatives table must contain the
   strongest real alternative and its honest trade-off — a strawman means the decision was not
   actually made, only rationalised.
3. **Land the ADR in the same PR as the change it justifies.** An ADR merged alone is a plan; a
   change merged alone is unjustified. The only exception is a decision that genuinely precedes any
   code, such as the Phase 0 set below.
4. **Get reviewer sign-off in the PR.** Security-relevant and breaking-change ADRs require a
   designated owner's approval per `.claude/rules/git-and-review.md`.
5. **Set Status to `Accepted` on merge.** After that the file is immutable.
6. **Cite it.** Reference the ADR from the spec section it governs, and from the engineering-log
   entry for the work.

---

## Index

| # | Title | Status | Summary |
|---|---|---|---|
| [0001](0001-package-naming-and-client-class.md) | Package naming and client class | Accepted | Distribution and import name `korchestrator`; the remote client ships as the `korchestrator.remote` submodule, not a separate distribution; the class is `KorchestratorClient` everywhere; method vocabulary is `run`/`run_swarm`/`run_and_wait` with camelCase equivalents in TypeScript. |
| [0002](0002-single-authoritative-version.md) | Single authoritative version | Accepted | `src/korchestrator/version.py` is the only version literal; `pyproject.toml` reads it dynamically via hatchling and everything else derives; a `version-validate` CI job fails on any disagreement; starts at `0.1.0`. |
| [0003](0003-license-apache-2-0.md) | License: Apache-2.0 | Accepted | Apache-2.0 for its express patent grant, which enterprise procurement and OEM embedding require; applied to `LICENSE`, package metadata, `NOTICE`, and an SPDX header convention, with a CI license-compatibility check. |
| [0004](0004-dependency-extras-matrix.md) | Dependency extras matrix | Accepted | Base install is `pydantic` alone; capabilities ship as independently installable extras (`dspy`, `temporal`, `routing`, `mcp`, `remote`, `otel`, `all`, `dev`) with heavy dependencies lazy-imported so `import korchestrator` never pulls one. |
| [0005](0005-remote-auth-bearer-token.md) | Remote auth: Bearer token | Accepted | `Authorization: Bearer <api-key \| KIAM JWT>` is the single scheme in every client, so migrating from keys to SSO needs no second code path; 401/403/402 map to `AuthError`/`AuthError`/`QuotaExceededError`; credentials are never logged, stored, or disclosed. |
| [0006](0006-runtime-split-local-and-temporal.md) | Runtime split: local and Temporal | Accepted | Two adapters behind `IDurableRuntime` — zero-infrastructure `local_runtime` (the default) and `temporal_runtime` using one `SuperstepActivity` per superstep to keep 100+ agents off Temporal's event-history hot path, trading per-agent retry granularity for scale. |
| [0007](0007-external-backend-boundary.md) | External backend boundary | Accepted | The SDK imports nothing from `backend.*`/`apps.*`/`services.*`/`frontend`, depends on no hosted service, and is never versioned against one; any engine is a downstream consumer of the published SDK, enforced by the import-isolation gate in CI and the pre-commit hook. |
| [0008](0008-typescript-client-deferred.md) | TypeScript client deferred | Accepted | `@kendralabs/korchestrator-sdk` is specified but not built in Phases 0–12; `clients/typescript/` does not exist and there is no npm publish job. Re-entry requires a named consumer **and** a remote contract stable across at least one minor release. |

---

## Related

- [`docs/specs/README.md`](../specs/README.md) — the specification set and how to change it.
- [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) — the condensed always-on ruleset, subordinate to
  the specs.
- [`CHANGELOG.md`](../../CHANGELOG.md) — what shipped, in Keep a Changelog format.
