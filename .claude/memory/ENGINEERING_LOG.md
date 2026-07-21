
# Engineering Log — Korchestrator SDK

The project's chronological record. **Append a new entry (newest at top) whenever a
feature/fix/refactor/architectural change is completed — BEFORE committing** (CLAUDE.md §8). Each
entry is self-contained: a reader should understand the change without the git diff. The blank
template is at the bottom of this file.

---

<!-- ⬇️ NEW ENTRIES GO HERE (newest first) ⬇️ -->

## 2026-07-21 · [P2.4] AgentGraph and topology validation — v0.1.0

**Type:** feature · **Phase:** P2 · **Author:** Claude (agent)

**What.** Implemented `core/graph.py`: `Node` (an `AgentConfig` plus its bound compute callable),
`Edge` (`source -> target`), the `AgentCallable` type, and `AgentGraph` with topology validation and
deterministic adjacency accessors (`node_ids`, `nodes`, `edges`, `outbound`, `has_edge`, `has_node`,
`get_node`). Re-exported from `korchestrator.core` (the Tier-3 surface). Tests lock valid
construction, all validation failures, cycles-allowed, and orphan-allowed.

**Why.** The kernel runs a directed agent graph; cycles are first-class (that is why it is Pregel,
not a DAG runner). Validation must happen once, before superstep 0 (spec 06 §4).

**Design decisions.** `Node`/`Edge` are frozen dataclasses (not pydantic models) because a node holds
a live callable, which is not serialisable — the graph's topology, not its callables, is what serde
(P8.5) will persist. Validation raises `ValidationError` (the kernel may import `exceptions`) for an
empty graph, duplicate ids, dangling edge endpoints, and disallowed self-edges; cycles are allowed
with no check. **Orphan nodes are legal** (spec 06 §4 lists no orphan check) — superstep 0 activates
every node, so an orphan runs once and deactivates; this resolves the ambiguous "orphan" item in the
spec 12 P2.4 list in favour of the spec-06 rule. Adjacency is stored sorted for stable, deterministic
routing regardless of edge input order.

**Architecture changes.** `core/graph.py` imports only `models` and `exceptions` (both legal for the
kernel). No framework, no optional dependency. Import contracts 3 kept, 0 broken.

**Files/modules affected.** `src/korchestrator/core/graph.py`, `core/__init__.py`,
`tests/unit/core/test_graph.py`.

**Breaking changes.** None (new Tier-3 surface).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** 8 graph tests pass; graph doctest passes; `ruff`, `ruff format`, `mypy --strict`
clean on 49 source files; import contracts 3 kept, 0 broken.

**Known limitations / future improvements.** The graph is topology + callables only; the superstep
runner that drives it (activation, barrier, halting) and message routing land in P2.5/P2.6.

---

## 2026-07-21 · [P2.1–P2.2] Reducers with algebraic laws — v0.1.0

**Type:** feature · **Phase:** P2 · **Author:** Claude (agent)

**What.** Implemented `core/reducers.py` — the four channel reducers (`LastValue`, `Append`,
`UniqueAppend`, `MergeDict`) plus the `Reducer` protocol and the `Delta` type — and proved their
algebraic laws with Hypothesis property tests (`tests/unit/core/test_reducers.py`). Each reducer
merges a channel's current value with one superstep's `(agent_id, value)` deltas. Registered a
Hypothesis test profile in `tests/conftest.py`.

**Why.** Reducers are the barrier's merge mechanism; if they are not associative and
order-independent, `asyncio.gather` completion order or Temporal's replay interleaving could change
the result and corrupt a replay (spec 06 §3). This is the deterministic heart the whole kernel rests
on, so the laws are property-tested, not example-tested.

**Design decisions.** Deltas are `(agent_id, value)` pairs and each reducer **sorts by `agent_id`
internally**, so it is a genuinely order-independent pure function. This adds the `agent_id` key to
spec 06 §3's illustrative `Sequence[T]` signature — deliberately, because the order-independence the
spec mandates for `LastValue`/`Append` needs a total order over the deltas, and `agent_id` (unique
per node) is exactly that order. A reducer is applied **once per channel per superstep** (collect →
sort → apply), not folded incrementally; incremental folding with re-sorting would break `Append`'s
result, so the operative guarantee is order-independence of the whole delta set, matching spec 06
§3's "sorts deltas by agent_id before folding". `MergeDict` deep-merges with conflicting leaves
resolved by highest `agent_id` (LastValue) and raises `ValidationError` on a non-mapping delta. Two
CI-plumbing corrections: `tests/conftest.py` registers a Hypothesis profile (`max_examples=50`,
`deadline=None`, suppress `too_slow`) so property tests are deterministic and robust on slow machines
(no wall-clock decides a test — spec 09 §3); and the base-install CI job now installs `hypothesis`
(a test tool, not a package runtime dependency — the kernel imports only pydantic/stdlib, and the
"optional deps absent" check still guards the real extras).

**Architecture changes.** `core/` gains its first real module. It imports only
`korchestrator.exceptions` and `korchestrator.types` (both legal for the kernel per spec 05); no
framework, no optional dependency. Import contracts still 3 kept, 0 broken.

**Files/modules affected.** `src/korchestrator/core/reducers.py`, `core/__init__.py`,
`tests/unit/core/test_reducers.py`, `tests/conftest.py`, `.github/workflows/ci.yml`.

**Breaking changes.** None (new internal surface).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** 15 property/behaviour tests pass (Hypothesis: order-independence for all four,
idempotence for `LastValue`/`UniqueAppend`/`MergeDict`, explicit non-idempotence for `Append`,
totality on empty deltas); 4 reducer doctests pass; `ruff`, `ruff format`, `mypy --strict` clean on
the kernel (`JSONValue` isinstance narrowing holds under strict); import contracts 3 kept, 0 broken.

**Known limitations / future improvements.** Channel→reducer binding, the barrier Reduce step, and
frozen-snapshot enforcement land in P2.3; the graph in P2.4; the superstep runner in P2.5.

---

## 2026-07-21 · [P1 review] Fix defects found in the P0+P1 review — v0.1.0

**Type:** fix · **Phase:** P1 · **Author:** Claude (agent)

**What.** Addressed the findings from the pre-merge review (boundary-auditor: clean; api-reviewer: 2
defects + 1 defect/hygiene + 3 suggestions). Fixed:
- **`Agent.__init__` now wraps pydantic's error** — it catches `pydantic.ValidationError` and raises
  `korchestrator.ValidationError` (code `KORCH_VALIDATION_FAILED`) with `... from exc`, so only
  `KorchError` subclasses cross the Tier-2 façade boundary (API rule A5; spec 08 §2.2/§7). The
  façade test now asserts the wrapped `KorchError`, its code, and the preserved `__cause__`.
- **CHANGELOG** gained an `### Added` block covering the entire P1 surface (exception tree, models,
  ARI ports/protocols, façade, the 27-name public API) — it previously documented only P0.
- **Docstring examples are now CI-enforced** — added a `pytest --doctest-modules src/korchestrator`
  step to the CI `static` job (9 examples, all offline). Rewrote the `Settings.from_env` example to
  stop mutating `os.environ` (it now uses bare `Settings()` for defaults and an explicit override for
  precedence — deterministic regardless of ambient env).
- **`Settings.from_env(**overrides: Any)`** gained an inline justification comment for the `Any`
  (per python-standards).

Two review items were **deferred by design** and recorded in `PROJECT_STATE.md` §6: the
`ConfigurationError`/`ValidationError` overlap (ADR before P8's `configure()`), and `ToolError`'s
specific default code (revisit at the P6 tool bridge). Both have no call site yet.

**Why.** The `Agent` exception leak and the missing CHANGELOG are cheap now but would each be a MAJOR
fix after `0.1.0` ships (changing a boundary exception type; missing user-facing paperwork). Fixing
before the P0/P1 merge keeps the frozen surface correct from the first release.

**Design decisions.** Tier-3 users constructing `AgentConfig`/`AgentPersona` directly still get raw
pydantic errors (documented, intended); only the curated Tier-2 `Agent` façade wraps. Doctest
enforcement lives in the single-Python `static` job to avoid 4× matrix redundancy.

**Architecture changes.** None — `services/agent.py` now imports `korchestrator.exceptions`
(façade may import leaf utilities). Import contracts unchanged: 3 kept, 0 broken.

**Files/modules affected.** `src/korchestrator/services/agent.py`, `src/korchestrator/config/settings.py`,
`tests/unit/services/test_facade.py`, `CHANGELOG.md`, `.github/workflows/ci.yml`,
`.claude/memory/PROJECT_STATE.md`.

**Breaking changes.** None (pre-release; this corrects the surface before it is first frozen in a
release).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** Façade test asserts the wrapped `KorchError` + cause + code;
`pytest --doctest-modules src/korchestrator` green (9 examples); full suite + `ruff`/`mypy --strict`
re-confirmed.

**Known limitations / future improvements.** See the two deferred items above (P6, P8).

---

## 2026-07-21 · [P1.5–P1.6] Freeze the public façade and the surface guard — v0.1.0

**Type:** feature · **Phase:** P1 · **Author:** Claude (agent)

**What.** Froze the public surface. `services/` defines the Tier-1/2 façade: `Agent` (validates into
an `AgentConfig`), `Swarm` (fluent builder — `add`/`edges`/`size` functional, `run` raises
`NotImplementedError`), and `Korch` (composition root — `run` raises `NotImplementedError`). The
top-level `korchestrator/__init__.py` re-exports the curated 27-name `__all__`. `tests/unit/
test_public_surface.py` locks the surface against a golden file (`public_surface.json`) and carries
the spec-04 Tier 1/2/3 examples as `xfail(strict=True)` tests; `tests/unit/services/test_facade.py`
locks the current façade behaviour.

**Why.** This is the anti-rework crux: the surface users import is frozen before implementation
(spec 12 P1.5/P1.6; spec 04). The golden snapshot makes any future change to `__all__` a deliberate,
reviewed act; the xfail-strict examples force the markers off the moment behaviour lands.

**Design decisions.** (1) The P1 `__all__` is spec 04 §6's list **minus** `configure`,
`enable_logging`, `from_json`, `to_json` — those come from the config/logging/serializers work in P8,
and spec 04 §6 explicitly says the list "grows in P8". So P1 freezes 27 names; P8 adds the four
(each a MINOR that updates the golden file). `TimeoutError` is intentionally not top-level (would
shadow the builtin under `import *`); `ConfigurationError` is likewise internal-only per spec 04 §6.
(2) Builders are functional data-collection so the topology surface is real and type-checks (`Self`
via `typing_extensions` for 3.10); only execution (`run`) is deferred to P4.9, its
`NotImplementedError` line coverage-excluded. (3) Docstring examples that would execute the deferred
path carry `# doctest: +SKIP`; the authoritative offline examples live as xfail-strict tests. (4) The
`Agent(id=...)` parameter keeps the public name `id` (matching `AgentConfig.id` and spec 04), with a
scoped `# noqa: A002`.

**Architecture changes.** `services/` is the composition root and the only module that imports across
layers (config, interfaces, models, its own submodules) — legal per spec 05. Import contracts remain
3 kept, 0 broken.

**Files/modules affected.** `src/korchestrator/services/{agent,swarm,korch}.py`, `services/__init__.py`,
`src/korchestrator/__init__.py`, `tests/unit/services/test_facade.py`,
`tests/unit/test_public_surface.py`, `tests/unit/public_surface.json`.

**Breaking changes.** None (initial public surface; frozen — any change now needs an ADR + CHANGELOG +
version decision + golden-file update in the same PR).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** `from korchestrator import Korch, Swarm, Agent` works; snapshot test passes; the
three tier examples xfail-strict; façade behaviour locked; `import korchestrator` pulls in no optional
dependency (base-install lazy check green); `ruff`, `ruff format`, `mypy --strict` clean on 47 source
files; import contracts 3 kept, 0 broken. **P1 Definition of Done met.**

**Known limitations / future improvements.** `Korch.run`/`Swarm.run` execute against the kernel in
P4.9 (removing the xfail markers). The top-level `__all__` grows by four names in P8. The
async surface (`A8` sync-wrapper detail) is settled when the kernel lands.

---

## 2026-07-21 · [P1.3–P1.4] Freeze the ARI ports and supporting protocols — v0.1.0

**Type:** feature · **Phase:** P1 · **Author:** Claude (agent)

**What.** Defined the interface contracts as `runtime_checkable` Protocols, re-exported from
`korchestrator.interfaces`: the three ARI ports — `IModelGateway` (spec 03 §4 verbatim),
`IIdentityProvider`, `IExecutionSandbox` — and the supporting protocols `IDurableRuntime`,
`GraphRepository`, `TenantStore`, `BaseRouter`, `AUBConnector`. Each docstring states its
implementations, concurrency expectations, and (for the ARI ports) the default implementation.
Structural-conformance tests lock the shape (exports, `isinstance` for conforming fakes, rejection
of non-conforming classes).

**Why.** These are the seams the whole SDK depends on; they must be frozen before any implementation
(spec 12 P1.3/P1.4; spec 03 §4). A port exists only because it has >1 real implementation.

**Design decisions.** Three points of note. (1) **`IDurableRuntime.run` takes `AgentState`, not an
`AgentGraph`** — `AgentGraph` lives in `core/` (P2.4) and `interfaces/` must not import outward, so
the graph/gateway/clock are injected into the concrete runtime at construction and `run` references
`models` only. (2) **The identity, sandbox, tenant, and connector method shapes are intentionally
minimal** and use only defined models (`ToolResult`, `AgentState`) plus primitives — spec 03 §4/§4.1
give these in prose without exact signatures; they are the P1 contract and may be enriched via an ADR
when their implementations land (P4.2, P6, P7). (3) `BaseRouter.select_model(context: RoutingContext)`
uses the `RoutingContext` model (whose docstring is literally "everything a select_model call may
consider"), rather than spec 11's shorthand `(task, models)`.

**Two contract corrections made here (each was a spec bug that blocked a green gate):**
- **import-linter `layers` order.** Spec 03 §9 listed `models` above `interfaces`, which forbids
  `interfaces → models`. But the ARI ports must import model types (the spec's own `IModelGateway`
  imports `Message`/`ModelCard`; spec 05 §1 lists `models` as an allowed import for `interfaces`).
  import-linter forbids a lower layer importing a higher one, so `interfaces` is now placed **above**
  `models`. Verified: 3 contracts kept, 0 broken.
- **coverage `exclude_lines`.** Added `^\s*\.\.\.$` so Protocol stub bodies (`...`) are not counted as
  uncovered executable code — the same treatment `@overload` and `if TYPE_CHECKING:` already get. No
  floor is lowered; only non-executable placeholders are excluded (measured before/after).

**Architecture changes.** `interfaces/` now depends inward on `models/` only, as spec 05 allows; the
layers contract reflects the real (and spec-05-sanctioned) `interfaces → models` edge.

**Files/modules affected.** `src/korchestrator/interfaces/{model_gateway,identity,sandbox,runtime,
repository,router,connector}.py`, `interfaces/__init__.py`, `tests/unit/interfaces/test_protocols.py`,
`.importlinter`, `pyproject.toml` (coverage exclude).

**Breaking changes.** None (new surface; frozen from here — changes need an ADR).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** Interface conformance tests pass; `ruff`, `ruff format`, `mypy --strict` clean on
44 source files; import contracts 3 kept, 0 broken; full suite + coverage floors re-confirmed.

**Known limitations / future improvements.** The minimal identity/sandbox/tenant/connector shapes
(see design note 2) are the most likely P1 contracts to be revisited (with an ADR) as
implementations land.

---

## 2026-07-21 · [P1.2] Define the model contracts — v0.1.0

**Type:** feature · **Phase:** P1 · **Author:** Claude (agent)

**What.** Defined the frozen Pydantic domain models (fields = the contract; behaviour lands in P2):
`types.JSONValue`; `models/state.py` (`MessageRole`, `Performative`, `RunStatus`, `Message`,
`StateUpdate`, `AgentState`); `models/agent.py` (`AgentPersona`, `AgentConfig`, `AgentDescriptor`);
`models/plan.py` (`TaskDecomposition`, `ExecutionPlan`); `models/routing.py` (`ModelCard`,
`TaskSemantics`, `RoutingContext`, `RoutingResult`); `models/result.py` (`RunResult`);
`models/tool.py` (`ToolResult`); all re-exported from `korchestrator.models`. Every model is
`frozen=True, extra="forbid"`. Contract tests (one module per source module) lock construction,
defaults, field constraints (ranges, patterns, min-length, enum membership), frozen enforcement, and
nested-JSON acceptance.

**Why.** The models are contracts referenced by the interfaces (P1.3/P1.4) and the façade; they must
be frozen before implementation (spec 12 P1.2; spec 05 §3). Frozen + `extra="forbid"` is what makes
the frozen-snapshot determinism rule real (spec 05 §5).

**Design decisions.** Two mechanism-level deviations from the spec 05 §3 listings, each required to
make the intended types actually work; the field contracts are unchanged. (1) **`JSONValue` uses
`TypeAliasType`** (PEP 695, via `typing_extensions`, a base-install pydantic dependency) rather than
the spec's inline `str | ... | list["JSONValue"] | dict[...]` alias — pydantic v2 resolves a *named*
recursive alias but recurses infinitely building a schema from an inline recursive union (reproduced,
then fixed). The resulting type is identical. (2) **`Mapping` is imported from `collections.abc`**,
not `typing` (spec's import), to satisfy ruff `UP035`. Field definitions, constraints, and defaults
follow spec 05 §3 exactly, including `protected_namespaces=()` on the models with a `model` /
`model_name` field.

**Architecture changes.** `models/` (contract layer) depends inward on `types/` only; intra-package
model imports (`plan`←`agent`, `result`←`state`, `tool`/`state`←`types`) are within the package and
legal. No sibling feature imports.

**Files/modules affected.** `src/korchestrator/types/__init__.py`,
`src/korchestrator/models/{state,agent,plan,routing,result,tool}.py`,
`src/korchestrator/models/__init__.py`, `tests/unit/models/test_{state,agent,plan,routing,result,tool}.py`.

**Breaking changes.** None (new surface; frozen from here — changes need an ADR).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** 88 model/exception/constant tests pass; `ruff`, `ruff format`, `mypy --strict`
clean on 37 source files; recursive `JSONValue` verified constructing and JSON round-tripping nested
data. `models/` coverage meets the 95% floor.

**Known limitations / future improvements.** No behaviour yet: reducer channel binding,
`Message.id`/`valid_time` derivation, and `RunResult.final_answer` derivation land in P2. Serde
round-trip/version-tag stability tests are P8.5. Models are not yet re-exported at the top level (the
frozen `__all__` is P1.5).

---

## 2026-07-21 · [P1.1] Freeze the KorchError hierarchy — v0.1.0

**Type:** feature · **Phase:** P1 · **Author:** Claude (agent)

**What.** Froze the exception hierarchy. `constants/error_codes.py` holds the stable code strings
(compatibility surface). `exceptions/errors.py` defines `KorchError` (message + stable `code` +
string `context`) and its subclasses — `ConfigurationError`, `ValidationError`, `AuthError`,
`NetworkError`, `TimeoutError`, `RateLimitError`, `QuotaExceededError`, `ProviderError`,
`RoutingError`, `ToolError`, `GovernanceHaltError`, `RunFailedError`, `RunTimeoutError`,
`MissingExtraError` — re-exported from `korchestrator.exceptions`. Tests lock subclassing, default
codes, message/code/context storage, the deliberate-but-not-builtin `TimeoutError`, cause
preservation, and the code-string snapshot.

**Why.** Everything catchable in the SDK is a `KorchError`; the tree and its codes are a contract
that must be frozen before any layer raises (spec 12 P1.1; spec 08 §2). Codes are part of the
compatibility surface and are snapshot-locked.

**Design decisions.** The hierarchy is the **union** of two specs that disagreed: spec 08 §2.1's tree
adds `ConfigurationError`; the P1.1 task list and `.claude/rules` add `MissingExtraError`. Both are
included so no raiser is left without its class. `KORCH_MISSING_EXTRA` is a new code (absent from the
spec 08 tree) for `MissingExtraError`, matching the optional-dependency contract. `KorchError.__init__`
follows spec 08 §2.1 verbatim (`message`, keyword-only `code`, `**context: str`). `TimeoutError`
deliberately shadows the builtin (spec 08 §2.1) and subclasses `KorchError` only; the two import sites
carry `# noqa: A004` with the reason. Code strings live in `constants/error_codes.py` and the classes
reference them, so a code exists once.

**Architecture changes.** `exceptions/` (leaf) now depends inward on `constants/` only, as spec 05
allows. No behaviour beyond construction.

**Files/modules affected.** `src/korchestrator/constants/error_codes.py`,
`src/korchestrator/exceptions/errors.py`, `src/korchestrator/exceptions/__init__.py`,
`tests/unit/exceptions/test_errors.py`, `tests/unit/constants/test_error_codes.py`.

**Breaking changes.** None (new surface, frozen from here per P1 DoD — changes now need an ADR).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** 40 exception/constant tests pass; `ruff`, `ruff format`, `mypy --strict` clean on
31 source files; import contracts 3 kept, 0 broken. Full suite + coverage floor re-confirmed.

**Known limitations / future improvements.** These classes are not yet re-exported at the top level —
that lands with the frozen `__all__` in P1.5. Error-wrapping boundary tests (asserting only
`KorchError` escapes each public entry point) arrive with the code that raises, audited in P8.4.

---

## 2026-07-21 · [P0.5–P0.8] Quality net, import contracts, and CI/CD skeletons — v0.1.0

**Type:** ci · **Phase:** P0 · **Author:** Claude (agent)

**What.** Landed the local quality net and the CI/CD skeletons (the plan groups these four tasks
under one commit):

- **P0.5** — `.pre-commit-config.yaml` (spec 02 §9 verbatim) and the `scripts/` helpers:
  `check_isolation.sh` (isolation gate, prints `OK`), `validate_version.py` (spec 10 §3.1),
  `check_env_reads.py` (env-confinement gate), and `smoke_install.sh` (clean-env wheel smoke).
- **P0.6** — `.importlinter` with the three enforceable contracts from spec 03 §9
  (kernel-is-framework-free `forbidden`, inward-only `layers`, feature `independence`); added
  `import-linter` to the `[dev]` extra.
- **P0.7** — `.github/workflows/ci.yml`: static (lint/format/mypy/import-linter/isolation/env-reads/
  version-validate), test matrix 3.10–3.13 with coverage + per-package floors, the pydantic-only
  base-install job, security (bandit/pip-audit/gitleaks), build + clean-env wheel smoke, examples,
  and docs. Added a P0 smoke test (`tests/smoke/test_import_and_one_liner.py`) and placeholder
  `tests/unit/core` / `tests/unit/models` directories so the base-install job's pytest path is valid
  now. `.github/dependabot.yml` completes the inventory.
- **P0.8** — `.github/workflows/release.yml` (tag-triggered build + artifact verification; publish
  deferred to P12), `.github/workflows/docs.yml` (spec 10 §7), `mkdocs.yml` (Material, `specs/`/`adr/`/
  `background/` excluded from the site), and a stub `docs/index.md` so the strict docs build passes.

**Why.** The isolation gate, version single-sourcing, import contracts, and CI must be active and
blocking before code volume grows (spec 11 P0 DoD; spec 03 §9; spec 09 §9).

**Design decisions.** Three deliberate, documented deviations from the literal spec, each to make a
mandated gate real: (1) `import-linter` was added to the `[dev]` extra — spec 02 §8's dev list omits
it, but P0.6/P0.7 and spec 03 §9 require the contracts and the CI step that runs them. (2) The
`[importlinter]` config sets `include_external_packages = True`, which import-linter requires whenever
a `forbidden` contract names external modules (the spec's §9 snippet omitted it, so the contracts
would not load without it). Import-linter has no standalone "no cycles" contract type; D4 (no cycles)
is enforced by the `layers` contract, exactly as spec 03 §9's own enforcement table maps it. (3) Two
small CI accommodations keep every job green during scaffolding without weakening any gate: the
examples loop uses `shopt -s nullglob` so it is a no-op until examples land in P11, and a stub
`docs/index.md` plus `exclude_docs` let `mkdocs build --strict` pass now; both jobs become substantive
as their phase lands.

**Architecture changes.** None to `src/`. The enforcement machinery (isolation, env-confinement,
version-validate, import contracts) is now wired into pre-commit and CI.

**Files/modules affected.** `.pre-commit-config.yaml`, `scripts/{check_isolation.sh,validate_version.py,
check_env_reads.py,smoke_install.sh}`, `.importlinter`, `pyproject.toml` (dev extra),
`.github/workflows/{ci,release,docs}.yml`, `.github/dependabot.yml`, `mkdocs.yml`, `docs/index.md`,
`tests/smoke/test_import_and_one_liner.py`, `tests/unit/{core,models}/.gitkeep`.

**Breaking changes.** None.

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** Locally verified: `check_isolation.sh` prints `OK`; `validate_version.py` prints
`version-validate OK: 0.1.0`; `check_env_reads.py` passes; `lint-imports` reports 3 contracts kept, 0
broken; the base-install pytest path (`tests/unit/core tests/unit/models tests/smoke`) collects and
passes 2 smoke tests; `python -m build` + clean-env wheel install imports `0.1.0` with pydantic only;
`mkdocs build --strict` succeeds. The full CI matrix and the security scans run in GitHub Actions once
pushed.

**Known limitations / future improvements.** The `examples` CI job is a no-op until P11 adds runnable
examples; the docs site is a stub until P11; `release.yml` builds and verifies but does not publish
until P12 wires Trusted Publishing.

---

## 2026-07-21 · [P0.4] OSS-readiness files — v0.1.0

**Type:** docs · **Phase:** P0 · **Author:** Claude (agent)

**What.** Added the open-source readiness set: Apache-2.0 `LICENSE` (full unmodified text) and
`NOTICE`; `CONTRIBUTING.md` (branch/commit/gate/PR/ADR expectations derived from the repo rules);
`CODE_OF_CONDUCT.md` (Contributor Covenant 2.1); `SECURITY.md` (private reporting channel, response
window, `0.x` supported-version policy); `CHANGELOG.md` (Keep a Changelog with the verbatim `0.x`
notice and a `## [0.1.0]` working section); `.editorconfig`; and `.github/` templates
(`ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`, `config.yml`, `PULL_REQUEST_TEMPLATE.md`).

**Why.** These files make the repository publishable and set contributor expectations before code
volume grows (spec 11 P0 build item 4; spec 02 §6).

**Design decisions.** `CHANGELOG.md`'s working section is titled `## [0.1.0] - Unreleased` rather than
`## [Unreleased]`, because `scripts/validate_version.py` (spec 10 §3.1) unconditionally requires a
`## [0.1.0]` section for the current source version; the substring satisfies the gate while
"Unreleased" stays honest until P12 stamps the date. Enforcement/security contacts use org-consistent
`kendralabs.com` addresses matching the repository URLs already in `pyproject.toml`; maintainers
should confirm these mailboxes exist. `README.md` was left unchanged — its full refresh belongs to
P11; its current "source does not exist yet" note is superseded by the P0 scaffold and will be
rewritten there.

**Architecture changes.** None.

**Files/modules affected.** `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
`SECURITY.md`, `CHANGELOG.md`, `.editorconfig`, `.github/ISSUE_TEMPLATE/*`,
`.github/PULL_REQUEST_TEMPLATE.md`.

**Breaking changes.** None.

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** Not executable code; `LICENSE` presence unblocks the `python -m build` acceptance
run (verified at phase close). No behaviour change.

**Known limitations / future improvements.** `README.md` refresh and the full docs site are P11;
`kendralabs.com` contact addresses need maintainer confirmation.

---

## 2026-07-21 · [P0.3] Minimal typed Settings — v0.1.0

**Type:** feature · **Phase:** P0 · **Author:** Claude (agent)

**What.** Added `config/settings.py` with the `Settings` model carrying the three fields Phases 0-3
need — `mock_llm` (default `True`), `korch_runtime` (`local`/`temporal`, default `local`),
`persistence_backend` (`none`/`memory`/`kcg`, default `memory`) — plus `Settings.from_env()`, the one
place the package reads the environment. Exported `Settings` from `korchestrator.config`. Landed
`tests/unit/config/test_settings.py` (defaults, env reading, argument precedence, invalid-value
rejection, immutability) and `tests/unit/test_module_contract.py` (every spec-05 package has an
explicit `__all__` and a layer-naming docstring). Recorded [ADR 0009](../../docs/adr/0009-settings-on-pydantic-core-no-pydantic-settings.md).

**Why.** P3 selects the runtime by config and P5 selects the router by config, so a minimal typed
`Settings` is needed before Phase 8 (spec 12, sequencing correction 1). The env-read-only-in-`config/`
rule applies from here on.

**Design decisions.** **ADR 0009**: `Settings` is built on `pydantic.BaseModel` and reads `os.environ`
directly inside `config/`, rather than on `pydantic-settings`. Spec 05/P0.3 name `pydantic-settings`,
but `config/` has no extra and sits on the base-install one-liner path, so importing it would make it
a base dependency — which ADR 0004 and golden rule 3 forbid without a superseding ADR. Preserving the
flagship pydantic-only base install won out over the minor convenience of the library for three scalar
fields; richer `.env`/secret handling is revisited in P8. Bare `Settings()` performs no environment
access (pure, test-friendly); `Settings.from_env(**overrides)` applies precedence argument > env >
default. `frozen=True` + `extra="forbid"`. The module-contract test doubles as the coverage vehicle
that keeps the empty skeleton stubs meaningfully exercised at P0.

**Architecture changes.** Establishes `config/` as the single environment reader; no other module
reads env. Boundaries note updated in `config/__init__.py`.

**Files/modules affected.** `src/korchestrator/config/settings.py`, `src/korchestrator/config/__init__.py`,
`tests/unit/config/test_settings.py`, `tests/unit/test_module_contract.py`, `docs/adr/0009-*.md`.

**Breaking changes.** None (new surface).

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** 65 tests pass; total coverage 100%; `ruff check`, `ruff format --check`, and
`mypy --strict` clean on 29 source files. `Settings` construction and `from_env` precedence, env
reading, invalid-value rejection, and immutability are all locked; the module contract is locked.

**Known limitations / future improvements.** No `.env` file support and no `SecretStr` fields yet
(P8). No `configure()` / `get_settings()` process-default accessor yet (P8). The conditional
`mock_llm` default (off when a gateway key is present) arrives with the gateway fields in P8.

---

## 2026-07-21 · [P0.2] Authoritative pyproject manifest — v0.1.0

**Type:** foundation · **Phase:** P0 · **Author:** Claude (agent)

**What.** Added the authoritative `pyproject.toml` verbatim from spec 02 §8: `hatchling` build
backend with the dynamic version sourced from `src/korchestrator/version.py`; requires-python
`>=3.10`; the single core dependency `pydantic>=2.7,<3`; the full extras matrix
(`dspy`/`temporal`/`routing`/`mcp`/`remote`/`otel`/`all`/`dev`); and the ruff, mypy, pytest, coverage
and bandit configuration.

**Why.** The manifest is the single authoritative build/metadata/toolchain contract; every gate reads
its configuration from here, and the dynamic version keeps `version.py` the single source of truth
(spec 12, P0.2; ADR 0002, ADR 0004).

**Design decisions.** Copied the manifest exactly as specified so tool config and the extras matrix
match the design record with no drift, with **one necessary correction**: the spec's
`addopts = "... --xfail-strict"` names a pytest CLI flag that does not exist (pytest errors with
"unrecognized arguments: --xfail-strict", blocking the entire test run). The intent — strict xfail,
required by P1.6 — is expressed by the pytest ini option `xfail_strict = true`, which this manifest
uses instead. Spec 09 §3.1 confirms the intent ("`xfail` is strict"); only the mechanism was wrong.
**MANIFEST.in was deliberately not created**: spec 02 §6 lists
it (a setuptools-era artifact), but the build backend is `hatchling`, which ignores MANIFEST.in and
instead takes sdist/wheel contents from `[tool.hatch.build.targets.*]` — already configured to ship
`src/korchestrator` (incl. `py.typed`), `README.md`, `LICENSE`, and `CHANGELOG.md`. Adding an inert
MANIFEST.in would be misleading. `import-linter` is not yet in the `[dev]` extra; it is added in P0.6
where the contracts land.

**Architecture changes.** None (build/metadata configuration only).

**Files/modules affected.** `pyproject.toml`.

**Breaking changes.** None.

**Feature version / revision.** `0.1.0`.

**Migration notes.** N/A.

**Testing status.** `tomllib` parses the manifest; `pip install -e .` succeeds; installed
distribution metadata reports `0.1.0` (dynamic version resolves from `version.py`). Full
`python -m build` wheel verification runs at phase acceptance once `LICENSE` lands (P0.4).

**Known limitations / future improvements.** The `[dev]` extra pulls in the heavy `[all]` stack
(dspy, temporalio, sentence-transformers, mcp, httpx, otel); Phase 0 gates are run against a targeted
tool subset locally, with the full matrix delegated to CI.

---

## 2026-07-21 · [P0.1] Package skeleton — v0.1.0

**Type:** foundation · **Phase:** P0 · **Author:** Claude (agent)

**What.** Created the `src/korchestrator/` package skeleton: the top-level `__init__.py` exposing
only `__version__`; `version.py` pinned to `0.1.0` as the single source of truth; the `py.typed`
PEP 561 marker; and all 26 module directories from spec 05 §1 (`config`, `interfaces`, `models`,
`core`, `agents`, `taxonomy`, `routing`, `runtime`, `context`, `persistence`, `providers`, `tools`,
`mcp`, `a2a`, `governance`, `security`, `events`, `clients`, `services`, `serializers`, `validators`,
`telemetry`, `logging`, `exceptions`, `types`, `constants`). Every package `__init__.py` carries a
docstring naming its layer and allowed imports and an explicit `__all__: list[str] = []`.

**Why.** Every downstream phase places code into these layers; the skeleton fixes the layer map and
the single-version source before any behaviour exists (spec 12, P0.1).

**Design decisions.** Module docstrings lifted verbatim (layer + allowed-imports) from the spec 05 §1
catalogue so the layer contract is legible at each package root. `__all__` is explicit and empty —
names are added only as real symbols land. `version.py` content matches spec 10 §3 exactly and is
created via the shell because `.claude/settings.json` denies the `Edit` tool on it (bump guard); this
is the mandated initial creation, not a bump.

**Architecture changes.** Establishes the layer directories; no behaviour, no cross-module imports yet.

**Files/modules affected.** `src/korchestrator/__init__.py`, `version.py`, `py.typed`, and
`src/korchestrator/<26 modules>/__init__.py`.

**Breaking changes.** None (initial creation).

**Feature version / revision.** `0.1.0` (pre-release; 0.x MINOR may break per policy).

**Migration notes.** N/A.

**Testing status.** `import korchestrator` returns `0.1.0`; base install pulls in no optional
dependency; `ruff check`, `ruff format --check`, and `mypy --strict` are clean on all 28 files. No
behaviour tests yet (kernel lands in P2).

**Known limitations / future improvements.** Every module is an empty stub; the public façade and the
frozen `__all__` land in P1; `pyproject.toml` and the quality net land in the following P0 tasks.

---

<!--
============================  ENTRY TEMPLATE (copy this)  ============================
Copy the block below to the top of the log for each completed change. Fill every field;
write N/A where a field genuinely doesn't apply. Keep it concise but self-contained.

## YYYY-MM-DD · [P<phase>] <short imperative title> — v<version>

**Type:** feature | fix | refactor | arch | perf | security | docs
**Phase:** P<n> · **Author:** <name/agent>

**What.**              <what was implemented, concretely>
**Why.**               <the motivation / requirement it satisfies>
**Design decisions.**  <notable choices + rationale; link any ADR>
**Architecture changes.** <structure/boundary/contract changes; did you update boundaries? y/n/n-a>
**Files/modules affected.** <list>
**Breaking changes.**  <none — or the break + migration note + major-bump plan>
**Feature version / revision.** <SemVer this lands under>
**Migration notes.**   <N/A — or steps for consumers>
**Testing status.**    <behaviors locked; test types; coverage; determinism/replay if kernel>
**Known limitations / future improvements.** <honest gaps / deferred work>
=====================================================================================
-->
