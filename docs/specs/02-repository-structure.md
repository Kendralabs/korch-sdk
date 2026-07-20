# 02 — Repository Structure

**Purpose:** Define the authoritative layout of the `korch-sdk` repository — every top-level entry,
every package directory, the naming conventions, the root file inventory, and the two manifests
(`pyproject.toml`, `.pre-commit-config.yaml`) that govern building and committing.

**Read this when:** you are adding a file, creating a module, placing a test, adding a dependency or
an extra, or reviewing a PR that introduces new paths.

Related: [03-architecture.md](03-architecture.md) for *why* the layers are ordered this way,
[05-modules-and-data-models.md](05-modules-and-data-models.md) for what each module contains,
[09-testing-and-quality.md](09-testing-and-quality.md) for the test strategy behind the `tests/`
layout, and [10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) for the workflow
files under `.github/`.

---

## 1. Authoritative layout

```text
korch-sdk/                             THIS repository — self-contained, independently publishable
├── src/                               Python source root (src-layout; see §2)
│   └── korchestrator/
│       ├── __init__.py                PUBLIC API — the only surface users import (explicit __all__)
│       ├── py.typed                   PEP 561 marker; ships type information to consumers
│       ├── version.py                 SINGLE source of truth for the SemVer version
│       ├── config/                    typed Settings (arg > env > file > default); ONLY place env is read
│       ├── interfaces/                ARI ports + protocols — the contracts everything depends on
│       ├── core/                      FRAMEWORK-FREE Pregel kernel — pydantic + stdlib only
│       ├── models/                    Pydantic domain models (state, agent, plan, routing, results)
│       ├── agents/                    L2 cognitive layer — DSPy agents + compiled signatures ([dspy])
│       ├── taxonomy/                  intent/difficulty classification + agent descriptors
│       ├── routing/                   L2 model routing — strategies behind BaseRouter ([routing])
│       ├── runtime/                   L1 durability adapters implementing IDurableRuntime
│       ├── context/                   L3 Context Compiler, Minimum Viable Context, pruning
│       ├── persistence/               L3 Context Graph client + backends behind GraphRepository
│       ├── providers/                 default ARI implementations (local identity/sandbox, gateways, MockLM)
│       ├── tools/                     L4 Agent Utility Bridge — bridge, registry, connectors
│       ├── mcp/                       L4 MCP client + hierarchical tool registry ([mcp])
│       ├── a2a/                       typed agent-to-agent messaging and handoff transformation
│       ├── governance/                L5 trust scoring, policy engine, HITL controls, audit
│       ├── security/                  L5 Shield — PII redaction, secret handling, sanitization
│       ├── events/                    transport-agnostic event/streaming publisher
│       ├── clients/                   remote HTTP client, re-exported as korchestrator.remote ([remote])
│       ├── services/                  high-level façade (Korch / Swarm / Agent) — the composition root
│       ├── serializers/               object <-> JSON/dict/YAML, deterministic and version-tagged
│       ├── validators/                input, config, response, and runtime-state validation
│       ├── telemetry/                 optional OpenTelemetry metrics + tracing ([otel])
│       ├── logging/                   namespaced, disable-able logger setup
│       ├── exceptions/                the KorchError hierarchy
│       ├── types/                     shared typing aliases, Protocols, TypedDicts
│       └── constants/                 defaults, enums, error codes
├── tests/                             mirrors src/ — unit / integration / e2e / regression / smoke
├── examples/                          executable examples, runnable unmodified on a clean install
├── docs/                              documentation source
│   ├── specs/                         this specification set (authoritative design record)
│   ├── adr/                           Architecture Decision Records
│   └── background/                    superseded source inputs (provenance; excluded from the site)
├── benchmarks/                        performance suites + committed baseline
├── scripts/                           build, validation, and release helper scripts
├── .github/                           workflows, issue and PR templates
├── .claude/                           agent operating manual, memory, hooks, settings
├── pyproject.toml                     authoritative Python manifest (§7)
├── README.md                          front door: what it is, install, quickstart, 0.x caveat
├── LICENSE                            Apache-2.0
├── CHANGELOG.md                       Keep a Changelog, ISO dates
├── CONTRIBUTING.md                    branch/commit/PR/gate expectations for contributors
├── CODE_OF_CONDUCT.md                 community standards and enforcement contact
├── SECURITY.md                        vulnerability reporting channel + supported-version window
├── MANIFEST.in                        sdist inclusion rules (py.typed, LICENSE, README)
├── .gitignore                         build artifacts, caches, virtualenvs, .env, local databases
├── .editorconfig                      charset, line endings, indentation across editors
├── .pre-commit-config.yaml            local gate mirroring CI (§8)
└── mkdocs.yml                         documentation site build configuration
```

**There is no `clients/typescript/` directory.** The TypeScript client is deferred: it is specified
for parity in [04-public-api.md](04-public-api.md) but is **not built in Phases 0–12**, and there is
no npm publish job in the initial CI/CD. When it is approved, it slots in as a top-level
`clients/typescript/` directory with its own manifest, its own SemVer line, and an additional
publish job in `release.yml` — see
[10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) §7.

### 1.1 Package directory rules

| Rule | Requirement |
|---|---|
| Every package directory has `__init__.py` | MUST — no implicit namespace packages inside `korchestrator` |
| A package `__init__.py` re-exports its own public names only | MUST — with an explicit `__all__`; it MUST NOT import from sibling feature packages |
| `core/` imports | MUST be limited to `interfaces/`, `models/`, stdlib, and `pydantic` |
| Heavy third-party imports | MUST be lazy (inside the function that needs them) and confined to their owning package: `dspy`→`agents/`, `temporalio`→`runtime/temporal_runtime.py`, `httpx`→`clients/`, OTel→`telemetry/` |
| Sideways imports between sibling feature packages | MUST NOT exist; siblings meet at `interfaces/` and `models/` |
| `os.environ` / `os.getenv` | MUST appear only under `config/` |
| Module size | SHOULD stay under ~500 lines; a function SHOULD stay under ~50 lines |

---

## 2. Why `src/` layout

The package lives at `src/korchestrator/`, not `korchestrator/` at the repository root. This is not
stylistic.

- **Imports resolve from the installation, not the working directory.** With a root-level package,
  `import korchestrator` in a test run from the repository root picks up the source tree whether or
  not the package is installed. With `src/`, it can only resolve through an installed distribution
  (editable or built).
- **It catches packaging bugs at test time.** A module or data file omitted from the wheel fails
  immediately in the test suite instead of on a user's first `pip install`. This is the same
  property the clean-environment install smoke test relies on
  ([09-testing-and-quality.md](09-testing-and-quality.md) §9).
- **It removes root-directory shadowing.** `tests/`, `docs/`, `scripts/`, and `benchmarks/` cannot
  accidentally become importable top-level packages.

Consequence: **tests MUST import the package as an installed distribution** (`import korchestrator`),
never by relative path manipulation, and `sys.path` MUST NOT be mutated in tests or `conftest.py`.

---

## 3. File and naming conventions

| Kind | Convention | Example |
|---|---|---|
| Module / package name | `lower_snake_case`, singular where it names a concern | `model_gateway.py`, `routing/` |
| Class | `PascalCase` | `PregelRunner`, `AgentState`, `RunResult` |
| ARI port / protocol interface | `I` + `PascalCase` | `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway`, `IDurableRuntime` |
| Non-ARI protocol | `PascalCase` without the `I` prefix | `GraphRepository`, `BaseRouter`, `AUBConnector` |
| Function / method / variable | `lower_snake_case` | `run_superstep`, `select_model` |
| Constant / enum member | `UPPER_SNAKE_CASE` | `DEFAULT_MAX_SUPERSTEPS`, `RunStatus.COMPLETED` |
| Private name | leading underscore; never exported in `__all__` | `_apply_reducers` |
| Environment variable | `UPPER_SNAKE_CASE`, read only in `config/` | `KORCH_RUNTIME`, `MOCK_LLM` |
| Test module | `test_<module>.py`, mirroring the source module name | `tests/unit/core/test_pregel.py` |
| Test function | `test_<behaviour>_<condition>` | `test_superstep_zero_activates_all_nodes` |
| Fixture | `lower_snake_case`, noun-shaped | `mock_gateway`, `fake_clock` |
| Benchmark module | `bench_<subject>.py` | `benchmarks/bench_superstep.py` |
| ADR file | `NNNN-kebab-title.md`, zero-padded, monotonic | `docs/adr/0003-extras-matrix.md` |
| Example script | `NN_kebab_topic.py`, ordered by difficulty | `examples/01_one_liner.py` |

**One test module per source module.** Every non-private module under `src/korchestrator/` MUST have
a corresponding `test_<module>.py` under `tests/unit/` at the mirrored path. A source module with no
test module fails review. Cross-module behaviour gets an *additional* test in `tests/integration/`;
it does not substitute for the unit module.

The remote client class is `KorchestratorClient` — in code, docstrings, README, and docs. No other
casing or spelling is acceptable.

---

## 4. `tests/` layout

`tests/` mirrors `src/korchestrator/` beneath each test-type directory.

```text
tests/
├── conftest.py                        shared fixtures ONLY; no sys.path manipulation
├── fixtures/                          reusable test doubles and data
│   ├── mock_lm.py                     the deterministic MockLM gateway used by default
│   ├── fake_clock.py                  injectable deterministic clock
│   ├── in_memory_persistence.py       in-memory GraphRepository double
│   └── graphs.py                      canonical AgentGraph fixtures
├── unit/                              one module per source module, mirrored path
│   ├── core/test_pregel.py
│   ├── core/test_reducers.py
│   ├── core/test_graph.py
│   ├── models/test_state.py
│   ├── routing/test_router.py
│   └── ...
├── integration/                       two or more real SDK components together
│   ├── test_runtime_swap.py
│   ├── test_routing_end_to_end.py
│   ├── test_tools_and_mcp.py
│   └── test_governance_pause_resume.py
├── e2e/                               a full swarm run through the façade
│   ├── test_local_swarm.py
│   └── test_temporal_swarm.py         requires the [temporal] extra
├── regression/                        one locked test per fixed defect
│   └── test_issue_0042_reducer_order.py
└── smoke/                             import + one-liner against a clean install
    └── test_import_and_one_liner.py
```

| Directory | Contains | Excludes |
|---|---|---|
| `tests/unit/` | One source module in isolation; all collaborators are doubles | Anything crossing a module boundary for real |
| `tests/integration/` | Two or more real SDK components wired together; external systems still doubled | Real network, real models, real databases |
| `tests/e2e/` | A complete run through the public façade, on a real runtime adapter | Real model providers (MockLM only) |
| `tests/regression/` | One test per fixed defect, named for the issue, failing on the pre-fix code | Anything not tied to a specific historical defect |
| `tests/smoke/` | The minimum that proves an install works: import, `__version__`, the one-liner | Anything requiring an optional extra |

Test runtime budgets, determinism-test requirements, and the coverage floors are defined in
[09-testing-and-quality.md](09-testing-and-quality.md).

---

## 5. Supporting directories

### 5.1 `examples/`

Every script MUST run unmodified on a clean install with no network access and no API key, defaulting
to MockLM. Each declares in a header comment which extras it needs. CI executes them.

| File | Demonstrates |
|---|---|
| `01_one_liner.py` | Tier 1 — `Korch().run(...)` |
| `02_typed_swarm.py` | Tier 2 — the `Swarm`/`Agent` builder with a fan-in topology |
| `03_custom_agent.py` | A user-defined agent with its own signature |
| `04_custom_tool.py` | Registering an `AUBConnector` |
| `05_custom_router.py` | Plugging a `BaseRouter` in by config |
| `06_mcp_server.py` | Mounting tools from an MCP server |
| `07_hitl_pause_resume.py` | Governance pause, inspect, resume |
| `08_streaming.py` | Subscribing to the event stream |
| `09_remote_client.py` | Tier 4 — `KorchestratorClient` against a mocked transport |
| `10_kernel_direct.py` | Tier 3 — embedding `PregelRunner` directly |

### 5.2 `docs/`

| Path | Contents |
|---|---|
| `docs/specs/` | This specification set — the authoritative design record |
| `docs/adr/` | ADRs, `NNNN-kebab-title.md`, each with context, decision, alternatives, consequences, rollback |
| `docs/background/` | Superseded source inputs kept for provenance. Never build from these. **Excluded from the site build** — publishing a superseded spec beside the current one is how readers build the wrong thing. |
| `docs/index.md` | Documentation site landing page |
| `docs/installation.md`, `docs/quickstart.md` | Getting started |
| `docs/tutorials/` | Swarm, custom agent, custom tool, MCP, custom router, HITL, streaming |
| `docs/reference/` | Auto-generated API reference |
| `docs/architecture.md` | Narrative architecture guide for users |
| `docs/versioning.md`, `docs/releases.md`, `docs/deployment.md` | User-facing derivations of spec 10 |
| `docs/migration.md`, `docs/faq.md`, `docs/troubleshooting.md` | Adoption support |

`docs/specs/` and `docs/adr/` are the engineering record; the rest is the published user
documentation site built by `mkdocs build --strict`.

### 5.3 `scripts/`

Small, dependency-light, individually runnable helpers invoked by CI and by developers. Each MUST be
runnable from the repository root and MUST exit non-zero on failure.

| Script | Responsibility |
|---|---|
| `scripts/check_isolation.sh` | The import-isolation gate — fails if the package imports `backend`/`apps`/`services`/`frontend` |
| `scripts/validate_version.py` | Asserts `version.py`, installed distribution metadata, and (on a tag build) the git tag all agree |
| `scripts/check_env_reads.py` | Fails if `os.getenv`/`os.environ` appears outside `config/` |
| `scripts/smoke_install.sh` | Installs the built wheel into a clean virtual environment and imports it |

Scripts MUST NOT be a second toolchain. Anything a standard tool already does (`ruff`, `mypy`,
`pytest`, `build`) is invoked directly, not wrapped.

### 5.4 `benchmarks/`

Performance suites plus a committed baseline file. Benchmarks are **not** part of the blocking test
run; they are executed on demand and on release branches. See
[09-testing-and-quality.md](09-testing-and-quality.md) §8.

### 5.5 `.github/`

| Path | Contents |
|---|---|
| `.github/workflows/ci.yml` | Lint, format, types, tests + coverage across the Python matrix, security scans, isolation gate, version-validate, build, install smoke, docs build |
| `.github/workflows/release.yml` | Tag-triggered build, artifact verification, SBOM, checksums, PyPI Trusted Publishing, GitHub release |
| `.github/workflows/docs.yml` | Documentation build and GitHub Pages deployment |
| `.github/ISSUE_TEMPLATE/` | Bug report and feature request templates |
| `.github/PULL_REQUEST_TEMPLATE.md` | Intent, risk, test evidence, compatibility impact, rollback |
| `.github/dependabot.yml` | Dependency update schedule for pip and GitHub Actions |

There is **no** npm publish job, no container build job, and no deployment job. See
[10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) §9.

### 5.6 `.claude/`

| Path | Contents |
|---|---|
| `.claude/CLAUDE.md` | Condensed always-on ruleset; subordinate to `docs/specs/` |
| `.claude/settings.json` | Permissions, the pre-commit hook wiring, and offline defaults |
| `.claude/hooks/pre-commit-check.sh` | Isolation gate + engineering-log requirement, run before every commit |
| `.claude/memory/ENGINEERING_LOG.md` | Ten-field entry per completed unit of work |
| `.claude/memory/PROJECT_STATE.md` | Current phase and status |

---

## 6. Root file inventory

| File | Responsibility |
|---|---|
| `pyproject.toml` | The authoritative manifest: package metadata, `requires-python >=3.10`, the `pydantic`-only core dependency, the extras matrix, and the configuration for `ruff`, `mypy`, `pytest`, and `coverage`. Build backend is `hatchling`. |
| `README.md` | What the SDK is, why it exists, install command, the Tier-1 quickstart, the extras table, a link to the docs site, and the explicit `0.x` compatibility caveat |
| `LICENSE` | Apache-2.0, full text, unmodified |
| `CHANGELOG.md` | Keep a Changelog format with ISO dates; every user-visible change lands with its entry in the same PR |
| `CONTRIBUTING.md` | Branch naming, Conventional Commits with phase tags, the local gate sequence, PR expectations, and the ADR requirement |
| `CODE_OF_CONDUCT.md` | Community standards and the enforcement contact |
| `SECURITY.md` | Private vulnerability reporting channel, response-time expectation, and the supported-version window |
| `MANIFEST.in` | Ensures `py.typed`, `LICENSE`, and `README.md` are present in the sdist |
| `.gitignore` | Excludes `dist/`, `build/`, `*.egg-info/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage*`, `site/`, `.env`, `*.db`, `*.sqlite3` |
| `.editorconfig` | UTF-8, LF line endings, final newline, 4-space Python indentation, 2-space YAML/JSON |
| `.pre-commit-config.yaml` | The local gate, mirroring CI (§8) |
| `mkdocs.yml` | MkDocs Material configuration, navigation, and strict-mode link checking |

---

## 7. What MUST NEVER appear in this repository

| Forbidden | Why |
|---|---|
| Backend or frontend application code (`app/`, `api/`, `web/`, a FastAPI app, a React app) | This repository is one product: the installable SDK. A service that consumes the published SDK lives in its own repository. |
| Service deployment manifests (Dockerfile for a server, Helm charts, `docker-compose.yml` for a hosted stack, K8s YAML) | The SDK is deployed by publishing artifacts, not by running a service |
| Infrastructure-as-code for another platform (Terraform, Pulumi, CloudFormation) | Infrastructure the SDK may connect to is the consumer's to operate |
| Any import of `backend.*`, `apps.*`, `services.*`, `frontend.*` | Breaks self-containment; blocked by the isolation gate and the pre-commit hook |
| Generated artifacts (`dist/`, `build/`, `site/`, `*.egg-info/`, coverage HTML) | Reproducible from source; noise in review |
| `.env` files, credentials, tokens, private keys, `*.pem` | Secrets never enter source control; only `.env.example` with inert values is tracked |
| Local databases, caches, or fixtures with real data (`*.db`, `*.sqlite3`, dumps) | Non-reproducible, potentially sensitive |
| Vendored copies of another repository's source | The SDK implements the smallest contract it needs in `interfaces/` and injects an implementation |
| A second implementation of a cross-cutting concern (a second router, PII redactor, error base, or config source) | One canonical implementation per concern; variation is a strategy behind one interface |

---

## 8. `pyproject.toml`

The complete, authoritative manifest. Version is **not** duplicated here — it is read dynamically
from `src/korchestrator/version.py` by `hatchling`, which is what makes single-sourcing enforceable
(see [10-release-versioning-and-cicd.md](10-release-versioning-and-cicd.md) §3).

```toml
[build-system]
requires = ["hatchling>=1.24"]
build-backend = "hatchling.build"

[project]
name = "korchestrator"
dynamic = ["version"]
description = "Durable multi-agent execution kernel: Pregel BSP supersteps, Temporal durability, typed compiled signatures."
readme = "README.md"
license = "Apache-2.0"
license-files = ["LICENSE"]
requires-python = ">=3.10"
authors = [{ name = "Kendra Laboratories Limited" }]
keywords = ["agents", "orchestration", "multi-agent", "temporal", "pregel", "llm"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: Apache Software License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Typing :: Typed",
]
dependencies = ["pydantic>=2.7,<3"]

[project.optional-dependencies]
dspy = ["dspy-ai>=2.5,<3"]
temporal = ["temporalio>=1.7,<2"]
routing = ["sentence-transformers>=3.0,<4", "numpy>=1.26"]
mcp = ["mcp>=1.2,<2"]
remote = ["httpx>=0.27,<1"]
otel = [
  "opentelemetry-api>=1.25",
  "opentelemetry-sdk>=1.25",
]
all = [
  "korchestrator[dspy]",
  "korchestrator[temporal]",
  "korchestrator[routing]",
  "korchestrator[mcp]",
  "korchestrator[remote]",
  "korchestrator[otel]",
]
dev = [
  "korchestrator[all]",
  "build>=1.2",
  "bandit>=1.7",
  "hypothesis>=6.100",
  "mypy>=1.10",
  "mkdocs-material>=9.5",
  "mkdocstrings[python]>=0.25",
  "pip-audit>=2.7",
  "pre-commit>=3.7",
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "respx>=0.21",
  "ruff>=0.5",
]

[project.urls]
Homepage = "https://github.com/kendralabs/korch-sdk"
Documentation = "https://kendralabs.github.io/korch-sdk"
Changelog = "https://github.com/kendralabs/korch-sdk/blob/main/CHANGELOG.md"
Issues = "https://github.com/kendralabs/korch-sdk/issues"

# --- build -----------------------------------------------------------------

[tool.hatch.version]
path = "src/korchestrator/version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/korchestrator"]

[tool.hatch.build.targets.sdist]
include = ["src/korchestrator", "tests", "README.md", "LICENSE", "CHANGELOG.md"]

# --- lint / format ---------------------------------------------------------

[tool.ruff]
line-length = 100
target-version = "py310"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "SIM", "TID", "PTH", "RUF", "D", "ANN", "S"]
ignore = ["D203", "D213", "ANN401"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D", "ANN", "S101"]
"benchmarks/**" = ["D", "ANN"]
"examples/**" = ["D", "ANN", "T201"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"backend".msg = "The SDK must not import from application repositories."
"apps".msg = "The SDK must not import from application repositories."
"services".msg = "The SDK must not import from application repositories."
"frontend".msg = "The SDK must not import from application repositories."

# --- types -----------------------------------------------------------------

[tool.mypy]
python_version = "3.10"
strict = true
files = ["src/korchestrator"]
plugins = ["pydantic.mypy"]
warn_unreachable = true
disallow_any_generics = true
no_implicit_reexport = true

[[tool.mypy.overrides]]
module = ["dspy.*", "temporalio.*", "mcp.*", "sentence_transformers.*"]
ignore_missing_imports = true

# --- tests -----------------------------------------------------------------

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config --xfail-strict"
asyncio_mode = "auto"
markers = [
  "slow: takes more than one second; excluded from the fast unit run",
  "temporal: requires the [temporal] extra and a Temporal test environment",
  "benchmark: performance measurement; never part of the blocking gate",
]
filterwarnings = ["error", "default::DeprecationWarning:korchestrator.*"]

# --- coverage --------------------------------------------------------------

[tool.coverage.run]
source = ["korchestrator"]
branch = true
parallel = true

[tool.coverage.report]
fail_under = 80
show_missing = true
skip_covered = true
exclude_lines = [
  "pragma: no cover",
  "if TYPE_CHECKING:",
  "raise NotImplementedError",
  "@overload",
]

[tool.bandit]
exclude_dirs = ["tests", "benchmarks", "examples"]
```

### 8.1 The extras matrix

| Extra | Adds | Enables | Required by |
|---|---|---|---|
| *(none)* | `pydantic` only | The Pregel kernel, models, local runtime, façade, MockLM, in-memory persistence | The Tier-1 one-liner and the entire kernel test suite |
| `[dspy]` | `dspy-ai` | `agents/` — compiled signatures, worker and architect agents | Tier 2 with real reasoning |
| `[temporal]` | `temporalio` | `runtime/temporal_runtime.py` — durable execution, replay, HITL signals | Durable mode |
| `[routing]` | `sentence-transformers`, `numpy` | Semantic and algorithmic routing strategies | Non-explicit routing |
| `[mcp]` | `mcp` | `mcp/` — MCP client and tool registry | Mounting MCP servers |
| `[remote]` | `httpx` | `clients/` — `korchestrator.remote.KorchestratorClient` | Tier 4 |
| `[otel]` | OpenTelemetry API + SDK | `telemetry/` — metrics and traces | Observability export |
| `[all]` | All of the above | Everything | Full-matrix testing |
| `[dev]` | `[all]` + the toolchain | Lint, types, tests, security scans, docs, build | Contributors and CI |

**The base install MUST remain `pydantic`-only.** Adding a runtime dependency to the core requires an
ADR. The kernel test suite runs against the base install in CI — see
[09-testing-and-quality.md](09-testing-and-quality.md) §6.

---

## 9. `.pre-commit-config.yaml`

The local gate mirrors CI so failures surface before the push, not after. It is installed once with
`pre-commit install`.

```yaml
default_language_version:
  python: python3.12

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
        args: ["--maxkb=512"]
      - id: check-merge-conflict
      - id: check-toml
      - id: check-yaml
      - id: end-of-file-fixer
      - id: mixed-line-ending
        args: ["--fix=lf"]
      - id: trailing-whitespace
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.7
    hooks:
      - id: ruff
        args: ["--fix", "--exit-non-zero-on-fix"]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.1
    hooks:
      - id: mypy
        args: ["--strict"]
        files: ^src/korchestrator/
        additional_dependencies: ["pydantic>=2.7"]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.9
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        files: ^src/korchestrator/
        additional_dependencies: ["bandit[toml]"]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks

  - repo: local
    hooks:
      - id: import-isolation
        name: import-isolation gate
        entry: scripts/check_isolation.sh
        language: system
        pass_filenames: false

      - id: env-reads-confined
        name: environment reads confined to config/
        entry: python scripts/check_env_reads.py
        language: system
        pass_filenames: false

      - id: version-single-source
        name: version single-sourcing
        entry: python scripts/validate_version.py
        language: system
        pass_filenames: false
```

`pre-commit` is complementary to, not a substitute for, the Claude Code hook in
`.claude/hooks/pre-commit-check.sh`, which additionally enforces the engineering-log requirement.
Neither may be bypassed: `git commit --no-verify` is denied.
