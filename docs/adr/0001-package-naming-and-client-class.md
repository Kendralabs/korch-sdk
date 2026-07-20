# ADR 0001 — Package naming and client class

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** SDK maintainers
- **Phase:** P0
- **Supersedes / Superseded by:** —

## Context

The source material for this repository uses at least four spellings of the product — Korchestrator,
KOrchestrator, Kendra Orchestrator, and korch — and two competing method vocabularies for the remote
surface (`launch`/`launchSwarm` versus `run`/`run_swarm`). Naming drift is cheap to prevent now and
expensive later: the distribution name is permanent once published to a registry, the import name
appears in every user file, and the client class name appears in every docstring, README snippet,
tutorial, and error message.

Spec §2.9 and §2.10 require this to be settled in Phase 0 before any code exists. Three separate
questions are entangled and are answered together here, because answering them apart is what
produces the drift:

1. What is the Python distribution and import name, and what is the repository called?
2. Does the thin HTTP client ship inside that distribution or beside it?
3. What is the client class called, and what are its methods called across languages?

There is currently no consumer of the remote client other than this repository's own examples and
tests, and no TypeScript implementation exists (see ADR 0008).

## Decision

**Distribution and import name: `korchestrator`.** One name for both. The repository is `korch-sdk`
— the repository name and the package name are deliberately allowed to differ, because the
repository holds more than the package (docs, examples, benchmarks, CI).

**The remote client ships as `korchestrator.remote`,** a submodule of the same distribution, gated
behind the `[remote]` extra (ADR 0004). It is not a separate distribution. If it is ever split out,
the new distribution is named `korchestrator-client` and is versioned independently from that point
forward; the split itself is a breaking change for import paths and requires its own ADR.

**The client class is `KorchestratorClient` — everywhere.** In code, docstrings, README, tutorials,
API reference, error messages, and the TypeScript twin. `KOrchestratorClient` (capital O),
`Kendra OrchestratorClient`, and `KorchClient` are forbidden spellings; a review that lets one
through is a defect.

**Method vocabulary is `run` / `run_swarm` / `run_and_wait`** in Python, snake_case per PEP 8. The
future TypeScript twin uses the same vocabulary in language-idiomatic casing: `run` / `runSwarm` /
`runAndWait`. The rule is *same words, native casing* — never a different verb in a different
language. `launch` is not used as a public method name anywhere.

The local façade (`Korch`, `Swarm`, `Agent`) uses the same `run` verb, so a developer moving from
Tier 1 to Tier 4 (spec §8) keeps the same vocabulary.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Ship `korchestrator-client` as a separate distribution from day one | This is the right end state *if* the client grows independent consumers and an independent release cadence. Today it has neither. Splitting now buys a smaller install for remote-only users — which the `[remote]` extra already buys — at the cost of two release pipelines, two changelogs, and a version-skew surface between client and kernel that must be documented and tested. Deferred, not rejected on principle; the split path and the name are recorded above so the future move is mechanical. |
| `korch` as the package name | Short and matches the roadmap CLI verb, but it is ambiguous (it names neither the product nor the company), reads as an abbreviation of something the reader has not yet met, and is a plausible collision on PyPI and in users' local namespaces. The CLI may still be `korch`; the importable package is not. |
| `kendra-orchestrator` / import `kendra_orchestrator` | Accurate and unambiguous, but long enough that users will alias it on every import, which reintroduces naming variance in exactly the place we are trying to eliminate it. It also couples the package name to the parent brand, which complicates OEM/white-label embedding (spec §2.6, platform reference §1.2). |
| `launch` / `launchSwarm` as the remote vocabulary | A defensible choice — it distinguishes "start a remote run" from "run locally". Rejected because that distinction is already carried by the class and module (`korchestrator.remote.KorchestratorClient`), and a second verb for the same concept forces every doc and tutorial to explain which one applies where. |

## Consequences

**Positive**

- One name to search for, install, import, and support. Docs, error messages, and code agree by
  construction.
- Remote and local surfaces read alike, so the Tier 1 → Tier 4 migration in spec §8 is a change of
  import, not a change of vocabulary.
- A single distribution means a single version number for the whole Python surface, which makes
  ADR 0002 (single authoritative version) enforceable without a cross-package matrix.

**Negative**

- Remote-only users install a distribution whose name implies the full kernel. Mitigated by the
  extras matrix — the base install is `pydantic` only — but the perception cost is real.
- If the client later needs its own release cadence, the split is a breaking import-path change,
  not a repackaging. We have chosen to pay that later rather than pay for two pipelines now.

**Neutral**

- Repository name (`korch-sdk`) and package name (`korchestrator`) differ. This is normal and
  documented, but it does mean `git clone` and `pip install` use different strings.
- The name `korchestrator-client` is reserved by decision, not by registration. If squatting is a
  concern, registering a placeholder on the registry is a follow-up task, not part of this ADR.

## Compliance

- **Distribution/import name:** `pyproject.toml` `[project].name` must equal `korchestrator`; the
  package directory must be `src/korchestrator/`. The `version-validate` CI job (ADR 0002) reads
  both and fails on mismatch.
- **Client class spelling:** CI runs a repository-wide grep for the forbidden spellings across
  `src/`, `docs/`, `examples/`, `README.md`, and `clients/` and fails the build on any hit:
  `grep -RnE "KOrchestratorClient|Kendra ?OrchestratorClient|KorchClient" src docs examples README.md`
  must produce no matches.
- **Method vocabulary:** the remote client's public surface is asserted in
  `tests/unit/test_remote_surface.py`, which checks that `run`, `run_swarm`, and `run_and_wait`
  exist and that no public method named `launch*` exists.
- **Parity:** the parity matrix in the docs (ADR 0008) lists the Python name and the TS name side by
  side; a docs test asserts each row's names differ only by casing convention.

## Rollback

Renaming the import name after the first publish is a major-version breaking change: it invalidates
every user import, requires a shim distribution that re-exports under the old name for at least one
minor release, and requires a migration guide per spec §10.7. Renaming the client class is the same
class of break, though a deprecated alias is cheap to maintain.

**Point of no return:** the first publish of `korchestrator` to the configured registry. Before that
tag, all three names are free to change for the cost of a find-and-replace. After it, only the
`korchestrator-client` split remains a low-cost move, and only because it was designed for here.
