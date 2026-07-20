# 09 — Testing and Quality

**Purpose:** Define what must be tested, how, where it lives, what must never appear in a test, the
coverage policy, the determinism guarantees the suite locks in, the quality gates that block a
merge, and what a reviewer is accountable for checking.

**Read this when:** you are writing or reviewing tests, adding a quality gate, changing the kernel or
serialization, or judging whether a change is done.

Related: [02-repository-structure.md](02-repository-structure.md) §4 for the `tests/` layout,
[06-execution-model.md](06-execution-model.md) for the determinism rules these tests enforce, and
[10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) for where each gate runs in
CI.

---

## 1. Principle

**A capability with no test is not delivered.** Behaviour is defined by the tests that lock it, not
by the implementation that happens to produce it. Every phase in
[11-build-phase-plan.md](11-build-phase-plan.md) lands its behaviour together with the tests that
define it.

Two corollaries govern every decision below:

- **Test at the lowest layer that proves the behaviour.** A rule about reducer associativity is a
  unit property test, not an end-to-end swarm run. Pushing a test upward makes it slower, flakier,
  and worse at localising the defect.
- **Determinism is a tested feature, not an aspiration.** The kernel's value proposition is that the
  same graph produces the same result across runs, processes, and Temporal replays. That claim is
  only true because §5 enforces it.

---

## 2. The test pyramid and the six test types

```
                    smoke        (a handful; proves the install works)
                  ─────────
                 e2e            (few; a full run through the façade)
               ─────────────
             integration        (some; two or more real components)
           ─────────────────────
         unit + property        (many; one module, all collaborators doubled)
       ─────────────────────────────
```

Regression and performance tests cut across the pyramid: a regression test lives at whatever layer
reproduces its defect most cheaply; performance tests live outside the blocking gate entirely.

| Type | Proves | Lives in | Runtime budget | CI trigger |
|---|---|---|---|---|
| **Unit** | One module behaves correctly in isolation, including its failure paths and boundaries | `tests/unit/` mirroring `src/` | < 50 ms per test; whole suite < 60 s | Every push and PR, on the full Python matrix |
| **Integration** | Two or more real SDK components agree at their seam — runtime swap, routing selection, tool invocation, governance pause | `tests/integration/` | < 500 ms per test; suite < 120 s | Every push and PR |
| **E2E** | A complete objective runs through the public façade to a `RunResult`, on a real runtime adapter, under MockLM | `tests/e2e/` | < 5 s per test; suite < 120 s | Every PR; the `[temporal]` subset only on the job that installs that extra |
| **Regression** | A specific fixed defect stays fixed; the test failed on the pre-fix code | `tests/regression/` | Same as its layer | Every push and PR |
| **Performance** | Parallelism, import time, and memory stay within the committed baseline | `benchmarks/` | Unbounded; runs alone | Manual dispatch and release branches only — **never blocking** |
| **Smoke** | A freshly installed artifact imports, reports its version, and completes the Tier-1 one-liner | `tests/smoke/` | < 10 s total | Post-build against the built wheel in a clean environment; again after publish |

**Every test type MUST exist and be green before a release.** A phase that ships behaviour without
its integration or e2e coverage is not complete.

---

## 3. Hard rules

These are absolute. A test violating any of them fails review regardless of what it covers.

| Rule | Rationale |
|---|---|
| **NEVER touch the network.** No HTTP, no DNS, no sockets. Remote-client tests use a mocked transport (`respx`). | Tests must pass offline, in CI, and on a laptop on a train. Network access makes failures meaningless. |
| **NEVER call a real model.** MockLM is the default gateway everywhere. | Non-deterministic, costly, and requires credentials CI must not hold. |
| **NEVER `sleep`.** No `time.sleep`, no `asyncio.sleep` as a synchronisation device. Use events, deterministic scheduling, or a fake clock. | A sleep is either wasted time or a race condition waiting to fail. |
| **NEVER read the wall clock.** No `datetime.now()`, `time.time()`, or `date.today()` in a test or in the code path it exercises. Inject the fake clock. | Time-dependent tests fail at midnight, across timezones, and on slow machines. |
| **NEVER depend on shared developer state.** No writes outside `tmp_path`, no reliance on a developer's `~/.config`, no reading the ambient environment. | Tests must be reproducible on any machine, in any order. |
| **NEVER depend on test order.** Each test sets up and tears down everything it needs. Module-level mutable state is prohibited. | Order dependence hides real coupling and breaks parallel execution. |
| **NEVER require an API key or a running service.** Every extra's tests double the external system. | The suite must run on a clean checkout with `pip install -e '.[dev]'` and nothing else. |
| **NEVER assert only that code ran.** Every test asserts an observable outcome — a returned value, a raised error with its code, an emitted event, a recorded call. | See §7 on coverage being necessary but not sufficient. |

### 3.1 Skips and expected failures

- Every `skip`, `skipif`, and `xfail` MUST carry a specific `reason=` naming **what** is missing and
  **who** owns it, in the form `reason="<what> — owner: <handle> — <tracking ref>"`.
- `xfail` is **strict** (`--xfail-strict` is set in `pyproject.toml`): a test marked `xfail` that
  passes is a failure. A behaviour that starts working must have its marker removed in the same PR.
- A bare `@pytest.mark.skip` with no reason fails review.
- `skipif` on an optional extra MUST test for the extra's importability, never for an environment
  variable a developer might set.

```python
pytest.importorskip("temporalio", reason="requires the [temporal] extra")
```

---

## 4. Fixtures and test doubles

Doubles live in `tests/fixtures/` and are exposed through `tests/conftest.py`. There is **one**
double per boundary — a second MockLM or a second in-memory repository is the same anti-pattern as a
second router in the source.

| Boundary | Double | Behaviour | Use for |
|---|---|---|---|
| `IModelGateway` | **MockLM** | Deterministic: the same prompt always yields the same completion; supports scripted per-agent responses and a recorded call log | Every test that reaches the reasoning layer. This is the default gateway. |
| `IDurableRuntime` | `LocalRuntime` (real) | The in-process adapter is fast and deterministic enough to use directly | Unit, integration, and e2e tests that do not specifically exercise durability |
| `IDurableRuntime` (durable) | Temporal test environment | Time-skipping test server; no external Temporal cluster | Replay tests and durability tests, marked `temporal` |
| `GraphRepository` | In-memory repository | Full protocol implementation backed by dicts; tenant-scoped like the real one | Persistence and context-graph tests without Neo4j or Postgres |
| Clock | **FakeClock** | Monotonic, manually advanced, injected wherever time is needed | Anything with a timeout, a TTL, a cache expiry, or a timestamp |
| `IIdentityProvider` | Local identity provider (real) | Deterministic synthetic DIDs | Identity propagation tests |
| `IExecutionSandbox` | Stub sandbox | Records invocations, returns scripted results, never spawns a process | Tool and sandbox-boundary tests |
| `AUBConnector` | Stub connector | Scripted `ToolResult`s including error codes | Tool-bridge, registry, and governance-denial tests |
| HTTP transport (remote client) | `respx` mock router | Asserts method, path, headers (including the `Authorization` header), and body; returns canned responses | Every `korchestrator.remote` test |
| MCP server | Stub MCP server | In-process; serves a fixed tool manifest | MCP client and registry tests |

**Rules for doubles.** A double MUST implement the same interface as the real component — never a
looser one. If a double drifts from its interface, `mypy --strict` over `tests/` catches it, which is
why the type check covers the test tree. Monkeypatching internal functions instead of injecting a
double is prohibited; if a test needs to patch a private name, the design is missing a seam.

---

## 5. Determinism testing (first-class)

Determinism is the kernel's central guarantee. Any change to `core/`, `runtime/`, `models/`, or
`serializers/` MUST land with the relevant tests below. These are not optional extras on top of the
unit suite — they are the suite's most important category.

### 5.1 Repeatability

The same graph, the same seed, and the same MockLM script MUST produce a byte-identical result.

```python
def test_run_is_repeatable(canonical_graph, mock_gateway, fake_clock):
    first = run_to_completion(canonical_graph, mock_gateway, fake_clock, seed=1234)
    second = run_to_completion(canonical_graph, mock_gateway, fake_clock, seed=1234)
    assert first.model_dump_json() == second.model_dump_json()
```

The assertion is on the **serialized** form, not on object equality — that catches ordering
differences inside collections that `==` would hide.

Repeatability MUST also hold **across processes**: the suite runs the same scenario in a subprocess
and compares the serialized result, which catches dependence on hash randomisation
(`PYTHONHASHSEED`).

### 5.2 Reducer algebraic laws (property-based)

Reducers are the barrier's merge mechanism. If they are not associative and order-independent, the
barrier's result depends on the order agents happen to finish — which is nondeterministic. These
laws are verified with Hypothesis over generated update sequences, not with hand-picked examples.

| Law | Statement | Applies to |
|---|---|---|
| Associativity | `r(r(a, b), c) == r(a, r(b, c))` | All reducers |
| Order independence | For any permutation `p` of updates, `fold(r, p(updates)) == fold(r, updates)` | `MergeDict`, `UniqueAppend` |
| Identity | `r(identity, a) == a` | All reducers |
| Idempotence | `r(a, a) == a` | `UniqueAppend`, `LastValue` |
| Determinism | Repeated folds of the same input yield equal output | All reducers |

`Append` is order-*preserving* by definition and therefore **not** order-independent; the barrier
MUST feed it updates in a canonical order (sorted by agent id) and a test MUST lock that ordering
rule explicitly. Documenting the exception is part of the requirement — a reducer whose law set is
not stated cannot be reviewed.

### 5.3 Temporal replay

Temporal replays workflow code from event history. Any nondeterminism in workflow scope — wall clock,
randomness, iteration over an unordered set, a changed code path — corrupts the replay.

- A **replay test** MUST run recorded workflow histories through the replayer and assert no
  nondeterminism error. Histories are committed as fixtures.
- Adding a superstep-affecting change to the workflow path MUST add a new history fixture and keep
  the old ones passing, or gate the change behind a `patched()` marker.
- A **crash-recovery test** MUST force a failure mid-run and assert the run resumes from the last
  completed superstep with no duplicated agent work.

These tests are marked `temporal` and run in the CI job that installs the `[temporal]` extra.

### 5.4 Serialization stability

Round-tripping MUST be lossless and the on-the-wire form MUST be stable.

| Test | Asserts |
|---|---|
| Round-trip | `from_json(to_json(x)) == x` for `AgentState`, `AgentGraph`, `ExecutionPlan`, `ModelCard`, `RunResult` |
| Canonical form | Serializing the same object twice yields identical bytes; key order is deterministic, not dict-insertion-dependent |
| Version tagging | Every serialized payload carries a schema version field |
| Forward compatibility | A payload written by the previous release deserializes on the current one; committed golden files, one per released schema version, are asserted against |
| Rejection | A payload with an unknown or newer schema version raises a `ValidationError` with an actionable message, never a silent partial parse |

Golden files live in `tests/fixtures/serde/` and are **append-only**. Modifying an existing golden
file is a breaking change requiring an ADR and a version bump per
[10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) §1.

---

## 6. The base-install test

**The kernel suite MUST pass with only `pydantic` installed.** This is the load-bearing test of the
architecture: it is what proves `core/` is genuinely framework-free and that heavy dependencies are
truly lazy.

CI runs a dedicated job that:

1. Creates a clean virtual environment.
2. Installs the package with **no extras**, plus `pytest` and `pytest-asyncio` only.
3. Asserts `dspy`, `temporalio`, `httpx`, `mcp`, and the OpenTelemetry packages are **not**
   importable.
4. Runs `pytest tests/unit/core tests/unit/models tests/smoke`.
5. Runs the Tier-1 one-liner end to end under MockLM.

A module-level `import dspy` anywhere on the import path of `korchestrator/__init__.py` fails this
job immediately — which is exactly its purpose. Tests in this subset MUST NOT import a fixture module
that transitively pulls in an extra.

### 6.1 Extras matrix testing

| Job | Installs | Runs |
|---|---|---|
| `base` | no extras (+ pytest) | Kernel, models, smoke; asserts extras are absent |
| `full` | `[dev]` (implies `[all]`) | The complete suite on every Python version in the matrix |
| `temporal` | `[temporal]` + pytest | `tests/e2e -m temporal`, replay and crash-recovery tests |
| `remote` | `[remote]` + `respx` | `tests/unit/clients`, remote integration tests |
| `import-cost` | no extras | Asserts `import korchestrator` does not import any optional dependency, by inspecting `sys.modules` after import |

The `import-cost` job is cheap and catches the most common architectural regression — a convenience
import at module top level that silently makes an extra mandatory.

---

## 7. Coverage policy

| Scope | Floor | Enforcement |
|---|---|---|
| Global (`korchestrator`) | **80%** | `fail_under = 80` in `pyproject.toml`; CI fails the build below it |
| `korchestrator/core/` | **95%** | Per-package check in the coverage gate |
| `korchestrator/models/` | **95%** | Per-package check in the coverage gate |

**The ratchet rule.** Floors move **up, never down**. When sustained coverage exceeds a floor by five
points or more, raise the floor in a `chore` PR. Lowering a floor — or adding `# pragma: no cover` to
make a build pass — requires an ADR stating what is untestable and why, with an owner and a removal
plan. "The gate was red" is never a reason.

**Coverage is necessary but not sufficient.** A line executed by a test with no assertion about it is
not covered in any meaningful sense. Reviewers MUST evaluate assertion quality, not the percentage.
Specifically:

- Every public function needs at least one test of its **failure** path, asserting the specific
  `KorchError` subclass and its error code — not merely that "an exception" was raised.
- Every boundary condition gets an explicit test: empty collections, a single element, the maximum,
  one past the maximum, `None` where optional.
- Every validation rule gets a test that trips it and asserts the message is actionable.
- Tenant isolation, authorization, and governance-denial paths get explicit tests. These are never
  covered incidentally.
- A test whose only assertion is `assert result is not None` does not count as coverage of that
  behaviour.

Coverage is measured with branch coverage enabled. Line coverage alone hides untested conditionals.

---

## 8. Benchmarks

`benchmarks/` holds performance suites and a **committed baseline** (`benchmarks/baseline.json`)
recording the measurements from a named reference environment. Benchmarks are informational: they
run on manual dispatch and on release branches, and they **never block a merge**. A performance
regression is triaged as a defect, not as a broken build, because benchmark numbers on shared CI
runners are too noisy to gate on.

| Benchmark | Measures | What good looks like |
|---|---|---|
| `bench_superstep.py` | Wall time of one superstep with N agents, N ∈ {1, 5, 25, 100}, under MockLM with a fixed per-call delay | Time scales roughly **~1×**, not ~N× — the agents genuinely run concurrently. Sub-linear scaling is the point of the BSP design; linear scaling means the fan-out is broken. |
| `bench_import.py` | `python -X importtime -c "import korchestrator"` on a base install | Import cost stays flat as the package grows; a step change means a new eager dependency |
| `bench_memory.py` | Peak resident memory for a run of M supersteps with N agents | Memory grows with retained state, not per superstep; a per-superstep leak shows as linear growth in M |
| `bench_serde.py` | Serialize/deserialize throughput for `AgentState` at representative sizes | No order-of-magnitude regressions across releases |

Rules: each benchmark states its environment and its parameters; results are recorded with the commit
SHA; the baseline is updated in a deliberate PR that explains the change. Benchmarks MUST NOT be
cited as evidence of absolute performance in user-facing documentation — they compare this repository
against its own history, on one machine, under MockLM.

---

## 9. Quality gates

Every gate below runs in CI. Blocking gates must be green before a PR may merge; a blocking gate is
never bypassed, disabled, or made advisory to land a change.

| # | Gate | Command | Blocking |
|---|---|---|---|
| 1 | Lint | `ruff check src/korchestrator tests examples benchmarks` | Yes |
| 2 | Format | `ruff format --check src/korchestrator tests examples benchmarks` | Yes |
| 3 | Types | `mypy --strict src/korchestrator` | Yes |
| 4 | Tests + coverage | `pytest tests --cov=korchestrator --cov-report=term-missing --cov-report=xml` | Yes |
| 5 | Base-install kernel suite | clean env, no extras, `pytest tests/unit/core tests/unit/models tests/smoke` | Yes |
| 6 | Static security scan | `bandit -c pyproject.toml -r src/korchestrator` | Yes |
| 7 | Dependency audit | `pip-audit --strict` | Yes |
| 8 | Secret scan | `gitleaks detect --no-banner --redact` | Yes |
| 9 | Import-isolation gate | `scripts/check_isolation.sh` — MUST print `OK` | Yes |
| 10 | Env-read confinement | `python scripts/check_env_reads.py` | Yes |
| 11 | Version single-sourcing | `python scripts/validate_version.py` | Yes |
| 12 | Build | `python -m build` | Yes |
| 13 | Clean-env install smoke | install the built **wheel** in a fresh venv, import, run the one-liner | Yes |
| 14 | Docs build | `mkdocs build --strict` | Yes |
| 15 | Examples run | execute every script in `examples/` under MockLM | Yes |
| 16 | Benchmarks | `pytest benchmarks -m benchmark` | **No** — informational |

Gate 9's exact form, since it is the one most often paraphrased incorrectly:

```bash
grep -RnE "from (backend|apps|services|frontend)\.|import (backend|apps|services|frontend)\." \
  src/korchestrator && echo "ISOLATION VIOLATION" || echo "OK"
```

Gates 1–4 and 9–11 also run locally via `.pre-commit-config.yaml`
([02-repository-structure.md](02-repository-structure.md) §9), and gates 9 plus the engineering-log
requirement run via `.claude/hooks/pre-commit-check.sh` before every commit. Local hooks are a fast
mirror of CI, never a replacement for it.

### 9.1 Security-scan suppressions

A `bandit` or `pip-audit` suppression requires, inline and in the PR description: the **owner**, the
**reason**, an **expiry date** (ISO), and the **compensating control**. A suppression without all
four fails review. Suppressions are reviewed at each release; an expired one blocks the release.

```python
# nosec B310 — owner: @maintainer — expires 2026-12-31 — URL scheme is validated
# against an allowlist in validators/url.py before this call.
```

---

## 10. Code review expectations

A reviewer is accountable for the following. Approving without checking them is a review defect.

**A reviewer MUST check:**

| Area | Question |
|---|---|
| Scope | Is this in scope per [01-scope-and-principles.md](01-scope-and-principles.md)? Does the diff stay narrowly on the stated intent? |
| Layering | Does every new import point inward? Is `core/` still free of frameworks? Are heavy imports still lazy and confined? |
| Public surface | Does anything in `__all__` change? If so, is it additive, documented, and consistent with [04-public-api.md](04-public-api.md)? |
| Determinism | Does workflow-path code read the clock or use randomness? Are new reducers associative and order-independent, with tests? |
| Tests | Does a new test fail without the change? Does a bug fix ship a regression test that failed on the old code? Are the assertions meaningful? |
| Failure paths | Is every new failure path deliberate, wrapped in a `KorchError` subclass with `raise ... from exc`, and tested? |
| Trust boundaries | Are identity and tenant scope carried through? Is validation at the boundary, with typed contracts? Does the security path fail closed? |
| Secrets and logs | Are logs structured, free of credentials and personal data? No `print()`? No root-logger mutation? |
| Configuration | Is every environment read inside `config/`? No hardcoded URL, key, model, or path? |
| Docs and changelog | Is the docstring present with a runnable offline example? Does a user-visible change carry its CHANGELOG entry in the same PR? |
| Engineering log | For any `src/` change, is there a ten-field entry in `.claude/memory/ENGINEERING_LOG.md`? |
| Evidence | Does the PR state which gates ran and what was verified? Unrun checks are reported as unrun, never as passed. |

**Hard-no anti-patterns — reject on sight:**

| Anti-pattern | Why it is rejected |
|---|---|
| A second implementation of a cross-cutting concern (router, PII redactor, error base, config source, logger) | One canonical implementation per concern; variation is a strategy behind one interface |
| A framework import inside `core/` (FastAPI, HTTP, Temporal, DSPy) | Destroys embeddability and import speed; breaks the base-install gate |
| A top-level import of an optional dependency | Silently promotes an extra to a hard requirement |
| A sideways import between sibling feature packages, or any import cycle | Siblings meet at `interfaces/`/`models/` |
| `os.getenv` or a hardcoded endpoint, key, model, or path outside `config/` | Config has one source with one precedence order |
| Any import from `backend`, `apps`, `services`, or `frontend` | Breaks self-containment; blocked by the isolation gate |
| A God file (>~500 lines) or God function (>~50 lines) | Cohesion failure; will not be reviewable or testable |
| A raw `temporalio`, `httpx`, `dspy`, or `mcp` exception escaping the public API | Users must be able to catch `KorchError` |
| A swallowed exception, a bare `except:`, or a fabricated success return | Hides defects and produces wrong results silently |
| A test with no meaningful assertion, or one that only raises coverage | Coverage theatre |
| Lowering a coverage floor, adding `# pragma: no cover`, or marking a test `skip` to make CI green | Gate erosion; requires an ADR if genuinely warranted |
| `git commit --no-verify`, or a force-push to a shared branch | Bypasses the gates the whole process depends on |
| A speculative abstraction with a single forever-implementation | An interface requires a demonstrated second implementation |
| A behaviour change with no test, or a bug fix with no regression test | Undelivered by definition |

**Reviewers cite concrete paths and distinguish severity.** A comment MUST state whether it is a
defect (blocking), a risk (must be answered), or a suggestion (non-blocking). Correctness and trust
boundaries are reviewed before style; style is `ruff`'s job, not a human's.
