# ADR 0004 — Dependency extras matrix

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

The capability surface in spec §2.5 spans DSPy reasoning, Temporal durability, embedding-based
routing, MCP tooling, an HTTP client, and OpenTelemetry. Taken together those dependencies are
enormous: `dspy` pulls a scientific stack, `temporalio` pulls a Rust-backed core, embedding routing
pulls `sentence-transformers` and therefore a deep-learning runtime.

If all of that is a hard dependency, three things break at once. Install time and image size become
hostile. The dependency-conflict surface becomes large enough that the SDK cannot be installed
alongside an arbitrary application — which kills the embedding use case the product depends on. And
`import korchestrator` becomes slow enough to be noticeable in a CLI or a serverless cold start.

Two golden rules constrain the answer. Spec §5.2 and §10.6 mandate a `pydantic`-only core with the
rest as optional extras. Spec §12 Phase 2 requires the kernel test suite to pass with *only*
`pydantic` installed — which is only meaningful if the base install genuinely cannot reach a heavy
dependency, not merely that it avoids one by convention.

## Decision

**The base install depends on `pydantic` alone.** Nothing else is a required runtime dependency.

**The extras matrix:**

| Extra | Enables | Confined to |
|---|---|---|
| `[dspy]` | Cognitive layer — compiled signatures, `WorkerAgent`, `ArchitectAgent`, taxonomy | `agents/`, `taxonomy/` |
| `[temporal]` | Durable runtime — `PregelMaster` workflow, superstep activity, HITL signals | `runtime/temporal_runtime.py` |
| `[routing]` | Semantic/embedding routing strategies and the ModelCard database | `routing/` |
| `[mcp]` | MCP client and tool registry | `mcp/` |
| `[remote]` | `httpx`-based `korchestrator.remote.KorchestratorClient` (ADR 0001) | `clients/` |
| `[otel]` | OpenTelemetry metrics and tracing | `telemetry/` |
| `[all]` | Union of the capability extras above | — |
| `[dev]` | Test, lint, type-check, build, and docs tooling; lockfile-pinned | not shipped |

**Heavy dependencies are lazy-imported inside the function that needs them** — never at module top
level, never in a package `__init__`. `import korchestrator` must not import `dspy`, `temporalio`,
`httpx`, `sentence-transformers`, or OpenTelemetry, directly or transitively, under any
configuration.

**Two invariants make this real rather than aspirational:**

1. Every extra is independently installable. `pip install korchestrator[temporal]` must work without
   `[dspy]`, and each pairwise and single-extra combination is exercised in CI.
2. The base install passes the kernel test suite with only `pydantic` present.

**A missing extra produces an actionable error, not an `ImportError` traceback.** The lazy import
site catches the failure and raises a `KorchError` subclass whose message names the extra to install
— for example, "Temporal runtime requires the `[temporal]` extra: `pip install
korchestrator[temporal]`".

**Rule for adding any new dependency.** All six must hold, and the PR must say so explicitly:

1. **Necessary** — the capability cannot be delivered adequately with the standard library or an
   existing dependency.
2. **Maintained** — active upstream, a release within a reasonable window, a real issue tracker.
3. **Licensed compatibly** — passes the Apache-2.0 compatibility check in ADR 0003.
4. **Pinned** — a lower bound and a compatible upper bound in `pyproject.toml`; exactly pinned in
   the dev lockfile for reproducible CI.
5. **Scanned** — clears `pip-audit` and the license scan.
6. **Removable** — placed behind an extra and lazily imported unless it is `pydantic`. Nothing joins
   the base install without a superseding ADR.

## Alternatives considered

| Option | Why rejected |
|---|---|
| A single fat dependency set — no extras, everything required | Simplest possible mental model, one install command, no combinatorial CI matrix, and no lazy-import discipline to enforce. Rejected on three counts, any one of which is disqualifying: import time and install size become hostile to CLI and serverless use; the transitive conflict surface makes the SDK uninstallable next to many real applications, which destroys the embedding use case that is the whole point of an SDK (spec §2.7); and it makes the pydantic-only kernel guarantee untestable. |
| Separate distributions per capability (`korchestrator-core`, `korchestrator-temporal`, …) | Gives the strictest possible isolation and lets each capability version independently — the correct answer for a much larger ecosystem. Rejected at this size for the same reason as the client split in ADR 0001: N release pipelines, an N×N version-skew compatibility matrix to document and test, and poor discoverability, since users must learn which distributions exist before they can use the product. Extras achieve ~90% of the isolation for a small fraction of the operational cost. |
| Extras but eager imports (import the extra's dependency at module import time, guarded by try/except) | Much simpler to write and read than threading lazy imports through call sites. Rejected because it defeats the purpose: a top-level guarded import still pays the import-time cost whenever the extra happens to be installed, so a user who installs `[all]` for one feature pays for all of them on every `import korchestrator`. It also makes the "base install never touches a heavy dep" property depend on what is coincidentally absent from the environment rather than on the code. |
| `[all]` includes `[dev]` | Convenient for contributors, and one fewer thing to explain. Rejected because it would put test and lint tooling into a user-facing install path, inflating the dependency tree for anyone who reaches for `[all]` and blurring the line between shipped and non-shipped dependencies. |

## Consequences

**Positive**

- `pip install korchestrator` is small and fast, and `import korchestrator` stays cheap — the SDK is
  embeddable in applications with their own dependency constraints.
- The kernel's framework-freedom (spec §4) is mechanically verifiable, not a stated intention: the
  base-install test job cannot pass if a heavy import leaks into `core/`.
- Users pay only for the capabilities they use, and the extras names are self-documenting.

**Negative**

- Real complexity moves into CI: the install matrix must cover base, each extra alone, and `[all]`,
  which is more jobs and more minutes.
- Lazy imports are less readable than top-level imports and are easy to regress — a single
  convenience import at module scope silently breaks the guarantee. This is why the import-time
  check below is a blocking gate rather than a lint suggestion.
- Users hit "capability not installed" errors at runtime rather than install time. Mitigated by
  making the error message name the exact `pip install` command.

**Neutral**

- `[all]` deliberately excludes `[dev]`. Contributors install `.[all,dev]`.
- Extras are additive; nothing prevents a user from installing every extra and getting the fat
  install by choice. The decision is about the default, not about capability.

## Compliance

- **Base-install job** (`ci.yml`): installs the distribution with no extras into a clean environment
  and runs the kernel test suite. It also asserts `pip freeze` contains no heavy dependency beyond
  `pydantic` and its own transitive set.
- **Import-purity test** (`tests/unit/test_import_purity.py`): imports `korchestrator` in a
  subprocess, then asserts that `sys.modules` contains none of `dspy`, `temporalio`, `httpx`,
  `sentence_transformers`, or `opentelemetry`. This is the gate that catches a stray top-level
  import; it runs in every CI configuration, including `[all]`.
- **Extras matrix job:** installs each extra individually and asserts its capability imports and its
  targeted tests pass, proving independent installability.
- **Missing-extra ergonomics:** `tests/unit/test_missing_extra_errors.py` asserts that reaching a
  gated capability without its extra raises a `KorchError` subclass whose message contains the
  correct `pip install` command — never a bare `ModuleNotFoundError`.
- **New dependencies:** reviewer checklist. A PR adding a dependency must state the six criteria
  above; `pip-audit` and the ADR 0003 license scan enforce criteria 3 and 5 automatically. Criteria
  1, 2, and 6 are reviewer judgement and are not automatable.

## Rollback

Adding an extra is backward compatible and cheap. **Removing** an extra, or promoting a dependency
from an extra into the base install, is user-visible: the former breaks installs that name it, the
latter silently enlarges every consumer's dependency tree and can introduce conflicts in
environments that previously resolved.

**Point of no return:** the first published release that documents an extra name. From then on, an
extra name is part of the public contract under spec §10.7 — removing or renaming one requires a
major bump, a deprecation period during which the old name remains installable as an alias, and a
migration note.
