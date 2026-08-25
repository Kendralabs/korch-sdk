# Korchestrator — Master Technical Documentation

**Repository:** `Kendralabs/korch-sdk` (private) · **Remote:** `git@github.com:Kendralabs/korch-sdk.git`
**Branches reviewed:** `dev`, `staging`, `main` (all three carry the same content as of this review)
**Document date:** compiled from a full repository review; treat as a point-in-time snapshot, not a live source
**Methodology:** every claim below was verified by reading the actual file(s) cited next to it — source code, configuration, CI workflow files, Dockerfiles, IaC JSON, tests, and committed documentation. No external network calls, cloud API calls, or infrastructure probes were made while compiling this document (per the operating rules governing this review). Anything that could not be verified from repository contents is explicitly labeled **"Not found / requires verification."** No secret values were read or are reproduced anywhere in this document — only variable *names* and *where they're configured*.

> **Read this first — the repository actually contains two different products.**
> 1. **The `korchestrator` SDK** (`src/korchestrator/`) — an installable Python library. This is the repository's *declared* purpose; its own operating rules (`.claude/CLAUDE.md`, `docs/specs/`) state in golden-rule terms that this repository ships **one product, the SDK, and will never contain a frontend, backend, or hosted service.**
> 2. **The Korchestrator Dashboard** (`dashboard/`) — a full React/TypeScript frontend **and** a FastAPI Python backend, with Docker images, a docker-compose stack, and reviewable AWS Fargate/ECS deployment artifacts. This is a real, deployable web application living inside the same repository.
>
> These two facts are in direct tension: the dashboard is exactly the class of artifact (`frontend/dashboard/UI`, `HTTP server`, `deployment manifests for a hosted service`) that the SDK's own rules list as **permanently out of scope**. This is not an inference — it is documented in this review's findings below (§19) with exact citations. Both products are documented in full here because both exist and are committed to every long-lived branch; this document does not silently omit the dashboard, but it also does not pretend the repository matches its own stated single-product rule.

---

## Table of contents

1. [Product Overview](#1-product-overview)
2. [Repository Documentation](#2-repository-documentation)
3. [Application Architecture](#3-application-architecture)
4. [Infrastructure and Servers](#4-infrastructure-and-servers)
5. [Deployment Architecture](#5-deployment-architecture)
6. [CI/CD Pipeline](#6-cicd-pipeline)
7. [URLs, Domains, and Access](#7-urls-domains-and-access)
8. [Authentication and Authorization](#8-authentication-and-authorization)
9. [Security](#9-security)
10. [Database](#10-database)
11. [APIs and Integrations](#11-apis-and-integrations)
12. [Configuration and Environment Variables](#12-configuration-and-environment-variables)
13. [Operations and Maintenance](#13-operations-and-maintenance)
14. [Monitoring, Logging, and Observability](#14-monitoring-logging-and-observability)
15. [Testing and Quality](#15-testing-and-quality)
16. [Complete Deployment Inventory](#16-complete-deployment-inventory)
17. [End-to-End Workflows](#17-end-to-end-workflows)
18. [How to Reproduce the Entire System](#18-how-to-reproduce-the-entire-system)
19. [Current Implementation vs Missing/Recommended Work](#19-current-implementation-vs-missingrecommended-work)
20. [Source References](#20-source-references)

---

## 1. Product Overview

### 1.1 The Korchestrator SDK

**What it is.** `korchestrator` is an installable Python library (`pip install korchestrator`, `src/` layout) implementing a **durable, deterministic, multi-agent execution kernel**. It combines three infrastructure ideas:

- **Temporal.io** for durable, replayable workflow execution (every "superstep" is checkpointed; a crash resumes rather than restarts).
- **Pregel-style Bulk Synchronous Parallel (BSP)** computation for deterministic parallel agent execution (agents compute against a frozen state snapshot; a synchronization barrier merges their outputs through order-independent "reducers").
- **DSPy compiled signatures** for typed, versioned, model-agnostic reasoning (as opposed to hand-written prompt strings).

**Purpose / use cases.** Running "swarms" — directed graphs of LLM-backed agents — with durability (resume after crash), determinism (identical results across repeated runs and Temporal replays), real parallelism (100+ agents per superstep, each optionally on a different model/provider), and governance (trust-scoring, human-in-the-loop pause/resume, PII/secret redaction). It positions itself against ad-hoc frameworks (LangChain/CrewAI/AutoGen-style) whose failure model is in-memory-only and whose concurrency model is not deterministic. Source: `README.md`, `docs/specs/00-overview.md`.

**Major components.** 26 single-responsibility subpackages under `src/korchestrator/` — kernel (`core/`), cognitive layer (`agents/`, `routing/`, `taxonomy/`), runtime adapters (`runtime/` — local and Temporal), integration (`tools/`, `mcp/`, `a2a/`), governance (`governance/`, `security/`), persistence (`persistence/`), the public façade (`services/` — `Korch`/`Swarm`/`Agent`), and leaf utilities (`config/`, `exceptions/`, `logging/`, `telemetry/`, `serializers/`, `validators/`, `types/`, `constants/`). Full catalogue with allowed imports: `llms.txt` §4 (root of this repo), verified against actual source by this review (§20, item SDK-1).

**Architecture in one line.** Dependencies point strictly inward: `services` (composition root) → `agents` → `core` (framework-free — only `pydantic` + stdlib) → `interfaces`/`models`. Feature modules never import each other. Heavy dependencies (`dspy`, `temporalio`, `httpx`, OpenTelemetry) are optional extras, lazily imported inside the one module that owns each. Source: `docs/specs/03-architecture.md`, `.claude/rules/architecture-boundaries.md`, confirmed against `src/korchestrator/__init__.py` and the actual directory listing by this review.

**Technology stack (SDK).** Python ≥3.10 (3.10–3.13 CI-tested); core runtime dependency is `pydantic>=2.7,<3` only; optional extras add `dspy` (reasoning), `temporalio` (durable runtime), `httpx` (remote HTTP client), `mcp` (Model Context Protocol client), `sentence-transformers`/`transformers`/`numpy` (semantic routing), OpenTelemetry (`otel` extra). Build backend: `hatchling`. Source: `pyproject.toml`.

**Current version:** `0.1.0` — `src/korchestrator/version.py:10`. A matching git tag `v0.1.0` exists in this repository (confirmed via `git tag -l`), though `CHANGELOG.md` and `.claude/memory/PROJECT_STATE.md` both still describe the release as "in progress"/"tag pending" — that framing is stale by roughly a day relative to the actual git state (see §19).

### 1.2 The Korchestrator Dashboard

**What it is.** A separate, full-stack web application living under `dashboard/` — a React 18 + TypeScript + Vite single-page frontend, and a FastAPI (Python) backend that imports the `korchestrator` SDK as an installed/editable library and drives real swarm executions on the user's behalf. It is explicitly framed (`dashboard/README.md`, `dashboard_spec.md`) as a **client application of the SDK**, kept in its own folder specifically so it doesn't modify the SDK core.

**Purpose / use cases.** A demo/testing/reference UI that lets a user run pre-built multi-agent scenarios against real or offline (mock) LLMs, watch execution progress stream live (via Server-Sent Events), and interact with a human-in-the-loop approval gate. Three concrete, currently-implemented scenarios (routers), each independently deployable as its own SSE-backed run:

| Router (backend) | UI panel (frontend) | What it demonstrates |
|---|---|---|
| `researcher_router.py` | `ResearcherDemo.tsx` | Simplest possible swarm: one agent, no tools, no topology, no HITL — a single question/answer. |
| `support_escalation_router.py` | `SupportEscalationDemo.tsx` | A 4-agent sequential pipeline (triage → researcher → resolver → reviewer), one agent with a real tool call, per-agent model overrides. |
| `fincrime_router.py` | `InvestigationConsole.tsx` | A 6-agent fan-out/fan-in financial-crime investigation swarm (5 parallel investigators → 1 reconciler), each investigator using 2–4 mock domain tools, with a human-in-the-loop sign-off gate before the reconciler runs, using entirely synthetic/fictional KYC/AML data (`fincrime_data.py`). |

There is also an older, separate code path in `main.py` (`/api/runs/start`, scenarios `scenario1`–`scenario4`) implementing the four scenarios described in `dashboard_spec.md` (Architect auto-plan, explicit Swarm designer, tool-augmented execution, HITL/governance) — this code exists and is mounted, but **the current frontend does not call it** (see §3.2 and §19); the three routers above are what the shipped UI actually drives.

**Major components.** FastAPI backend (`dashboard/backend/main.py` + 3 domain routers + a multi-provider LLM gateway `gateway.py` + two optional tracing integrations `tracing.py`/`kcg_tracing.py`); React/Vite frontend (`dashboard/frontend/src/` — 4 source files, no router library, no state-management library, three tab-switched demo panels); a docker-compose stack for one-command local spin-up; reviewable (not applied) AWS Fargate/ECS + IAM + CloudFront/S3 deployment artifacts under `dashboard/aws/`.

**Technology stack (Dashboard).**

| Layer | Technology | Source |
|---|---|---|
| Frontend framework | React 18.2, TypeScript 5.2, Vite 5.1 | `dashboard/frontend/package.json` |
| Frontend build | `tsc && vite build` | `dashboard/frontend/package.json` |
| Frontend serving (containerized) | nginx 1.27-alpine, reverse-proxying `/api/*` | `dashboard/frontend/Dockerfile`, `nginx.conf.template` |
| Backend framework | FastAPI, Uvicorn (ASGI) | `dashboard/backend/requirements.txt` |
| Backend base image | `python:3.11-slim` | `dashboard/backend/Dockerfile` |
| LLM abstraction | `litellm` (multi-provider), `boto3` (direct Bedrock bearer-token calls) | `dashboard/backend/gateway.py`, `requirements.txt` |
| Optional tracing | LangSmith (`langsmith` SDK), a custom "KCG" (Kendra Context Graph) HTTP exporter | `dashboard/backend/tracing.py`, `kcg_tracing.py` |
| Local orchestration | Docker Compose (2 services: `backend`, `frontend`) | `dashboard/docker-compose.yml` |
| Cloud target (reviewable, unapplied) | AWS Fargate (ECS) behind an ALB, S3 + CloudFront for the frontend, Secrets Manager, CloudWatch Logs, Bedrock | `dashboard/aws/*` |
| E2E testing | Playwright (TypeScript) | `dashboard/playwright.config.ts`, `dashboard/e2e/*.spec.ts` |

**LLM providers supported.** OpenAI, Anthropic, and AWS Bedrock (default model `us.anthropic.claude-sonnet-4-20250514-v1:0`, configurable via `BEDROCK_MODEL_ID`) — see §11.3.

### 1.3 How the two products interact

The dashboard is a **pure consumer** of the SDK's public API — it does not modify SDK source, and it imports `korchestrator` the same way an external user would (`pip install -e '.[all]'` at the repo root, then `from korchestrator import Agent, Swarm, Korch` in `dashboard/backend/main.py`). One piece of SDK-side wiring (`before_superstep`/`after_superstep` hook propagation for `GovernanceHaltError`, in `korchestrator.core.pregel`/`korchestrator.services.hooks`) was added specifically to support the dashboard's HITL-reject flow — this is documented in `dashboard/README.md` and is the one place the dashboard's requirements shaped SDK internals (through the SDK's normal extension mechanism, not a special-cased hack).

---

## 2. Repository Documentation

### 2.1 Top-level layout

```text
korch-sdk/
├── src/korchestrator/        The SDK — 26 subpackages, see §1.1 and llms.txt §4
├── tests/                    SDK test suite (unit/integration/e2e/regression/smoke), mirrors src/
├── examples/                 8 runnable, offline example scripts (01_one_liner.py … 08_support_escalation_swarm.py)
├── benchmarks/                Performance suites + committed baseline.json (informational only, never blocks CI)
├── scripts/                   Build/validation/release helper scripts (see §6.5)
├── docs/                      Documentation source: specs/ (00-12, authoritative design), adr/ (decisions), reference (mkdocs site), background/ (superseded inputs)
├── .github/workflows/         ci.yml, release.yml, docs.yml — see §6
├── .claude/                   Claude Code operating manual, memory (PROJECT_STATE.md, ENGINEERING_LOG.md), hooks, rules
├── dashboard/                 THE DASHBOARD APP — see §2.2 below
├── dashboard_spec.md          Root-level design spec for the dashboard app (321 lines)
├── pyproject.toml             SDK's Python package manifest (deps, extras, ruff/mypy/pytest/coverage/bandit config)
├── .importlinter               Import-layering contracts (enforces the architecture rules mechanically)
├── .pre-commit-config.yaml     Local git-hook mirror of CI's fast checks
├── README.md, CONTRIBUTING.md, CHANGELOG.md, LICENSE (Apache-2.0), CODE_OF_CONDUCT.md, SECURITY.md, NOTICE
├── llms.txt                    Single-file, comprehensive machine-readable index of the SDK's design (see note below)
├── mkdocs.yml                  Documentation site build config
└── .env.example                 Inert-value example for SDK-level env vars (SDK itself defines very few — see §12)
```

Source: repository root directory listing (`ls -la`), `docs/specs/02-repository-structure.md`.

> **Note on `llms.txt`.** This file (repository root) is a separate, previously-produced comprehensive index of the **SDK's** design, aimed at LLM/coding-agent consumption. It does **not** cover the `dashboard/` application at all. This document (`MASTER_DOCUMENTATION.md`) is the broader one: it covers both the SDK and the dashboard, and documents operational/infrastructure/deployment detail that `llms.txt` does not.

### 2.2 `dashboard/` layout

```text
dashboard/
├── backend/
│   ├── main.py                    FastAPI app: CORS, /api/config, /api/runs/* (scenario1-4), mounts 3 routers
│   ├── gateway.py                  LiteLLMGateway — multi-provider IModelGateway implementation
│   ├── tracing.py                  Optional LangSmith gateway-wrapper
│   ├── kcg_tracing.py               Optional "KCG" (Kendra Context Graph) HTTP trace/decision exporter
│   ├── fincrime_router.py           /api/swarm/fincrime/* — 6-agent investigation swarm + HITL
│   ├── fincrime_data.py             Synthetic KYC/AML fixture data (fictional, no real PII)
│   ├── researcher_router.py         /api/swarm/researcher/* — 1-agent Q&A swarm
│   ├── support_escalation_router.py /api/swarm/support-escalation/* — 4-agent pipeline swarm
│   ├── requirements.txt             Backend's own deps (FastAPI, uvicorn, litellm, boto3, httpx, langsmith, python-dotenv)
│   ├── Dockerfile                   Single-stage python:3.11-slim image (see §5.4 — has a verified startup bug)
│   ├── .env.example                 Documents expected env vars (not readable by this review's tooling; see §12)
│   ├── .env                          Local, gitignored, real credentials — NOT tracked in git (verified §9.1)
│   └── tests/                        5 pytest files — see §15.1
├── frontend/
│   ├── src/
│   │   ├── main.tsx                 Entry point
│   │   ├── App.tsx                   Shell: topbar, tab switcher between 3 demo panels, fetches /api/config once
│   │   ├── InvestigationConsole.tsx  Fincrime swarm UI (~342 lines)
│   │   ├── SupportEscalationDemo.tsx Support-escalation swarm UI
│   │   ├── ResearcherDemo.tsx        Researcher swarm UI
│   │   ├── index.css                 602-line hand-rolled "Premium Dark Theme" design system
│   │   └── vite-env.d.ts             Declares VITE_API_BASE / VITE_BEDROCK_MODEL env types
│   ├── package.json, tsconfig.json, vite.config.ts, index.html
│   ├── Dockerfile                    2-stage: node:20-alpine build → nginx:1.27-alpine serve
│   ├── nginx.conf.template           /api/* reverse proxy (SSE-safe: buffering off, 3600s read timeout)
│   ├── .env.example
│   └── dist/                         Committed(?) build output — see §2.3 caveat below
├── aws/
│   ├── ecs-task-definition.json     Fargate task def for the backend container (reviewable, not applied)
│   ├── iam-execution-role-policy.json
│   ├── iam-task-role-policy.json
│   └── README.md                     Ordered manual setup runbook
├── e2e/
│   ├── dashboard.spec.ts             7 Playwright tests — target a UI that no longer exists (see §15.2, §19)
│   ├── debug-sse.spec.ts, debug-sse2.spec.ts   Manual SSE debugging scripts, not real assertions
├── docker-compose.yml                One-command local spin-up (2 services)
├── playwright.config.ts              baseURL defaults to a specific AWS ALB DNS name (see §7)
├── package.json, package-lock.json    Root dashboard/ npm manifest (Playwright + deps for e2e)
└── README.md                         Dashboard quick-start
```

Source: `find dashboard -maxdepth 4 -type f`, `git ls-files dashboard` (44 tracked files).

> **Caveat on `dashboard/frontend/dist/`.** The directory listing shows built assets (`dist/assets/index-*.js`, `dist/index.html`) present on disk. `dashboard/frontend/.dockerignore` and the root `.gitignore` both exclude `dashboard/frontend/dist/` from version control, so this is very likely a local, untracked build artifact left over from a manual `npm run build` — **not found/requires verification**: this review did not exhaustively confirm `dist/` is absent from `git ls-files` (the 44-file dashboard tracked-file count in §1's SDK-verification pass is consistent with `dist/` being untracked, but this specific claim wasn't independently re-checked file-by-file).

### 2.3 Branching strategy and environments

**Three long-lived branches, forward-only promotion**, documented authoritatively in `.claude/rules/branching-and-promotion.md`:

```
<type>/<slug>  →  dev  →  staging  →  main
```

| Branch | Role | Receives from | Notes |
|---|---|---|---|
| `dev` | Integration — everything lands here first | Short-lived work branches (`feat/`, `fix/`, `docs/`, etc.) | Never committed to directly |
| `staging` | Release-candidate verification | `dev` | Never committed to directly |
| `main` | Released; the repository's GitHub default branch; the only branch tags are cut from | `staging` | Never committed to directly |

Rules (verbatim intent, source `.claude/rules/branching-and-promotion.md`): work branches off `dev` as `<type>/p<phase>-<slug>`; PRs target `dev` (GitHub's default-branch proposal of `main` is explicitly called out as wrong for feature work); promotion is a PR merged `--no-ff`, one stage at a time, never skipped, never cherry-picked, and only after the source branch is green on the full CI matrix; `src/korchestrator/version.py` is edited only in the `staging → main` release PR; a hotfix is the one exception (branches off `main`, PRs back to `main`, then is immediately back-merged `main → staging → dev`).

There is **no separate "environment" concept for the dashboard app** documented anywhere (no `dashboard`-specific branch, no environment-specific config file naming a "staging" or "production" dashboard deployment) beyond the generic AWS artifacts in `dashboard/aws/`, which describe a single, unnamed target environment. **Not found / requires verification**: whether the dashboard is deployed per-branch, or only ever manually from whatever branch a maintainer chooses.

### 2.4 How developers should work with the repository

For the **SDK**: standing workflow is documented in `.claude/CLAUDE.md` §10 — find the task in `docs/specs/12-implementation-plan.md`, design the public API surface first, place code in the correct architectural layer, write tests that lock the behavior, run all quality gates, update docstrings/docs/CHANGELOG, update `.claude/memory/ENGINEERING_LOG.md` **before committing** (a commit hook blocks `src/` changes without a fresh log entry — `.claude/hooks/pre-commit-check.sh`), then commit with Conventional Commits and a phase tag, and open a PR into `dev`.

For the **dashboard**: no equivalent formal workflow document exists (no `dashboard/CONTRIBUTING.md`, no dashboard-specific engineering-log requirement, no dashboard-specific CI gate — see §6, §19). Development is effectively: edit files under `dashboard/backend/` or `dashboard/frontend/src/`, run locally per `dashboard/README.md`, and commit — subject only to the repository's generic root-level pre-commit hooks (ruff/mypy/bandit are scoped to `src/korchestrator`, per `.pre-commit-config.yaml`'s `files:` filters, so they **do not** run against `dashboard/backend/*.py`).

### 2.5 Important commands

**SDK — development, testing, building** (source: `README.md`, `CONTRIBUTING.md`):

```bash
git clone <repository-url> && cd korch-sdk
pip install -e '.[dev]'                                        # base install is pydantic-only; [dev] pulls every extra + tooling
python -c "import korchestrator; print(korchestrator.__version__)"
python examples/01_one_liner.py                                 # first offline run, MockLM

ruff check src/korchestrator tests examples benchmarks
ruff format --check src/korchestrator tests examples benchmarks
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing       # coverage floor 90% global / 97% core/ / 99% models/
bash scripts/check_isolation.sh                                  # must print OK
python scripts/check_env_reads.py
python scripts/validate_version.py

mkdocs build --strict
mkdocs serve                                                       # → http://127.0.0.1:8000
```

**SDK — building & releasing** (source: `docs/releases.md`, `scripts/cut_release.py`):

```bash
# from staging:
python scripts/cut_release.py prepare --bump patch   # or minor / major / --version X.Y.Z
# after that PR merges into main:
python scripts/cut_release.py tag                     # tags main, triggers release.yml
```

**Dashboard backend — development** (source: `dashboard/README.md`):

```powershell
pip install -e '.[all]'
cd dashboard/backend
pip install -r requirements.txt
Copy-Item .env.example .env      # then edit with real credentials
python -m uvicorn main:app --reload --port 8000
```

**Dashboard frontend — development** (source: `dashboard/README.md`):

```powershell
cd dashboard/frontend
npm install
npm run dev            # → http://localhost:5173
```

**Dashboard — one-command local full stack** (source: `dashboard/docker-compose.yml`, `dashboard/README.md`):

```bash
# from the repository root, after creating dashboard/backend/.env
docker compose -f dashboard/docker-compose.yml up --build
# → http://localhost:8080 (frontend, nginx-proxied); http://localhost:8000 (backend, direct, for debugging)
```

**Dashboard — E2E tests** (source: `dashboard/playwright.config.ts`, `dashboard/package.json` — exact npm script name not confirmed, inferred standard Playwright invocation):

```bash
cd dashboard
npx playwright test                 # defaults to baseURL in playwright.config.ts (a specific AWS ALB — see §7)
DASHBOARD_URL=http://localhost:8080 npx playwright test   # override to target a local stack
```

**Dashboard backend — tests:**

```bash
cd dashboard/backend
pytest tests/ -v
```

### 2.6 Important dependencies and why

**SDK (core + extras)** — see the full pinned table in §12.4 and `pyproject.toml`. One-line rationale per extra: `dspy` — typed/compiled reasoning; `temporalio` — durable workflow runtime; `httpx` — remote HTTP client (`[remote]` extra only); `mcp` — Model Context Protocol tool discovery; `sentence-transformers`/`transformers`/`numpy` — semantic model routing; OpenTelemetry — optional tracing/metrics.

**Dashboard backend** (`dashboard/backend/requirements.txt`): `fastapi` (web framework), `uvicorn` (ASGI server), `litellm` (multi-provider LLM completion abstraction — the core of `gateway.py`), `boto3` (direct AWS Bedrock bearer-token `converse()` calls), `pydantic` (request/response models, pinned to match the SDK's own v2 requirement), `python-multipart` (FastAPI form-data dependency, no multipart route observed), `python-dotenv` (`.env` loading), `httpx` (used by `kcg_tracing.py`'s HTTP export and by tests), `langsmith` (`tracing.py`'s LangSmith client). Note: **`korchestrator` itself is not in this file** — it's installed separately from source (`pip install -e '.[all]'` or the Dockerfile's own `pip install '.[all]'` step); the SDK is also published to PyPI as of [ADR 0021](docs/adr/0021-repository-goes-public-pypi-trusted-publishing.md), but this dashboard's own build predates that and still installs from source.

**Dashboard frontend** (`dashboard/frontend/package.json`): `react`/`react-dom` 18.2, `reactflow` 11.10 (**declared but not imported anywhere in current source — dead dependency**, see §19), `lucide-react` 0.344 (**same — declared but unused**), dev-only: `typescript`, `vite`, `@vitejs/plugin-react`, `@types/react*`.

---

## 3. Application Architecture

### 3.1 SDK architecture

Full detail in `llms.txt` §3 (repository root) and `docs/specs/03-architecture.md`; summary:

```
services/  (façade / composition root — Korch, Swarm, Agent builders; the ONLY wiring site)
  → agents/  (L2 cognitive — DSPy reasoning, compiled signatures)
    → core/  (L1 kernel — Pregel BSP superstep loop; imports ONLY interfaces/, models/, stdlib, pydantic)
      → interfaces/, models/  (the contracts — ARI ports, Pydantic domain models)

feature modules (routing, tools, mcp, a2a, governance, persistence, context, events, runtime, taxonomy)
  → depend inward on interfaces/models only, never on each other

adapters (providers/, runtime/temporal_runtime.py, clients/) implement the interfaces
leaf utilities (config, exceptions, logging, telemetry, serializers, validators, security, types, constants)
  → no upward dependencies
```

Portability runs through exactly three ARI (Agent Runtime Interface) ports, each with a local default and an (unimplemented-here) enterprise alternative: `IModelGateway` (LLM routing — local default `MockLM`), `IExecutionSandbox` (tool/code execution — local default: subprocess), `IIdentityProvider` (agent identity — local default: unsecured local identity). This review verified (§20, item SDK-1) that `src/korchestrator/__init__.py`'s actual `__all__` (31 names) and the 26-directory module catalogue match what `llms.txt` documents exactly, with no drift.

**Execution model.** A run is a sequence of "supersteps": Plan (once, superstep 0) → Compute (all active agents run concurrently against a frozen state snapshot) → Synchronise (barrier) → Reduce (deterministic, order-independent reducer merge) → Checkpoint (durable persistence). Two `IDurableRuntime` implementations exist: `local_runtime` (in-process, zero infrastructure, the default) and `temporal_runtime` (one `SuperstepActivity` per superstep, fanning out via `asyncio.gather`, driven by a single `PregelMaster` Temporal workflow). Full detail: `llms.txt` §7.

### 3.2 Dashboard architecture

**Backend (`dashboard/backend/main.py`).** A single FastAPI app instance (`FastAPI(title="Korchestrator SDK Dashboard API")`). CORS middleware is wide-open (`allow_origins=["*"]`, `allow_credentials=True`) — acceptable for a same-origin-proxied local/demo tool, not hardened for a general multi-tenant deployment. `load_dotenv()` runs at module import, before the SDK import, loading `dashboard/backend/.env`. Three domain routers are mounted via `app.include_router(...)`: `support_escalation_router`, `fincrime_router`, `researcher_router` — each maintains **its own independent in-memory run registry** (a plain Python `dict`), with zero shared state between routers or with `main.py`'s own `active_runs` dict. There is no database anywhere (§10). Source citations: `dashboard/backend/main.py` lines 13, 16-22, 55, 58-68, 71-78.

**Two generations of scenario code coexist in the backend, and the frontend only drives one of them:**

| Code path | Backend routes | Frontend UI that calls it |
|---|---|---|
| `main.py`'s original 4 numbered scenarios (`/api/runs/start`, `/api/runs/{id}/approve`\|`reject`\|`stream`) — implements `dashboard_spec.md`'s Architect auto-plan / Swarm designer / tool use / HITL scenarios | Present, mounted, functional per its own tests-not-observed caveat (§15) | **None** — no component in `dashboard/frontend/src/*.tsx` calls `/api/runs/*` |
| The 3 domain routers (fincrime/support-escalation/researcher) | `/api/swarm/{fincrime,support-escalation,researcher}/*` | `InvestigationConsole.tsx`, `SupportEscalationDemo.tsx`, `ResearcherDemo.tsx` — all 3 |

This is a verified, real divergence (grepped: zero references to `/api/runs/` or `scenario1`..`scenario4` anywhere in `dashboard/frontend/src/`), not a documentation assumption. See §19.

**LLM Gateway (`gateway.py`).** `LiteLLMGateway` implements the SDK's `IModelGateway` port for `main.py`'s 4 scenarios only — routes to OpenAI/Anthropic via `litellm.acompletion`, and to AWS Bedrock either via a direct `boto3` `bedrock-runtime.converse()` call (when `AWS_BEARER_TOKEN_BEDROCK` is present) or via LiteLLM's `bedrock/...` prefix falling back to boto3's standard AWS credential chain (e.g., an ECS task's IAM role, with no bearer token needed). Credentials handed to the constructor are pushed straight into `os.environ` for the process — no secret storage, no persistence to disk. `available_models()` returns a **fixed, hardcoded** catalog of 5 `ModelCard`s regardless of which keys are actually configured (this diverges from `dashboard_spec.md`'s illustrative design, which conditionally builds the catalog — see §19). The three domain routers do **not** use `LiteLLMGateway` — each builds its own simpler gateway (`korchestrator.providers.OpenAIGateway` when `OPENAI_API_KEY` is set, else a deterministic offline stand-in). Source: `dashboard/backend/gateway.py`.

**Optional tracing wrappers.** Both are additive `IModelGateway` decorators, app-level (not SDK-level), no-op when their key is absent, and both swallow (log, never raise) network failures so tracing can never break a demo run:
- `tracing.py` — real LangSmith integration (`langsmith.Client().create_run/update_run`), gated on `LANGSMITH_API_KEY`/`LANGCHAIN_API_KEY`.
- `kcg_tracing.py` — real HTTP calls (via `httpx`, lazily imported) to an external "KCG" (Kendra Context Graph) service, default `http://localhost:8503`, gated on `KCG_API_KEY`. Dual-writes: an OTLP/HTTP-JSON span (`POST {KCG_BASE_URL}/v1/traces`) and a graph "Decision" node (`POST {KCG_BASE_URL}/ingest`, a specific singular `{"node": {...}}` payload shape — the module's own docstring documents this was verified against KCG's actual handler behavior because the batch shape from KCG's public docs silently writes nothing). Includes a fixed placeholder `confidence_score: 0.85`, explicitly documented as not a measured value.

**Streaming (SSE).** Three distinct SSE implementations exist. `main.py` and `support_escalation_router.py` use a genuine push-based `EventPublisher`/subscriber pattern (`korchestrator.events`) — an async queue the SSE generator awaits. `fincrime_router.py` and `researcher_router.py` instead use a **poll-based** design (append to a plain list every event, poll it every 0.15s) — a deliberate, documented workaround (`fincrime_router.py`'s own module docstring) for a real, reproduced SDK-level hang bug when cross-thread `asyncio` signaling collides with a `GovernanceHaltError` unwinding through nested `asyncio.to_thread` calls. All three frame SSE as `data: {json}\n\n` with **no named `event:` line** (deliberately, so `EventSource.onmessage` fires generically). Source: `dashboard/backend/main.py` lines 474-505, `support_escalation_router.py` lines 308-336, `fincrime_router.py` lines 111-125 (docstring) and its poll loop, `researcher_router.py`.

**Frontend (`dashboard/frontend/src/`).** No client-side router, no state-management library — a flat 4-file structure. `App.tsx` holds a local `Swarm` union-type state (`"fincrime" | "support-escalation" | "researcher"`) and renders one of the three demo components based on which tab button was last clicked. `API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000"`. Each demo component: `fetch`-POSTs to start a run, gets back `{ run_id }`, opens a native browser `EventSource` against the matching `/stream/{run_id}` endpoint, `JSON.parse`s each `data:` frame's `{name, payload}` shape, and switches on `name` to update UI state. Streams close on a terminal event or `es.onerror`. Source: `dashboard/frontend/src/App.tsx`, `InvestigationConsole.tsx`, `SupportEscalationDemo.tsx`, `ResearcherDemo.tsx`.

### 3.3 Data flow — user request to final response (dashboard, fincrime scenario as the representative example)

```
1. Browser loads http://localhost:8080 (or an ALB/CloudFront URL in AWS) → nginx serves the built React SPA.
2. User clicks "Fincrime" tab → InvestigationConsole.tsx renders; on "Run" click:
3. Browser: POST {API_BASE}/api/swarm/fincrime/run  { objective?, agent_models }
      → nginx proxies /api/* to the backend container (or same-origin ALB routing in AWS)
4. FastAPI (fincrime_router.py): validates via Pydantic RunRequest, generates a run_id,
      creates an in-memory run-registry entry + empty event log, launches the swarm
      execution in a background asyncio task, returns { run_id } immediately (HTTP 200).
5. Backend (background task): builds a korchestrator.Swarm with 6 Agents (5 investigators
      + 1 reconciler), a gateway (real OpenAIGateway if OPENAI_API_KEY set, else a
      deterministic OfflineGateway), a ConnectorRegistry of mock KYC/AML tools backed by
      fincrime_data.py fixtures, and a _HitlGate Middleware that will halt the run at
      superstep 1 pending human sign-off. Runs via asyncio.to_thread(swarm.run, ...).
6. korchestrator kernel: executes Pregel supersteps — 5 investigator agents reason
      concurrently (each may call its mock tools via the SDK's tool bridge), each emits a
      StateUpdate; the barrier merges them; each event (agent_status, finding, superstep,
      stream tokens, cost) is _publish()-appended to the run's in-memory event log as it
      happens.
7. Browser (meanwhile): GET {API_BASE}/api/swarm/fincrime/stream/{run_id} via EventSource
      → backend polls its event log every 0.15s and streams new frames as
      `data: {"name": "...", "payload": {...}}\n\n` → InvestigationConsole.tsx updates the
      agent grid / findings feed / cost meter live.
8. At superstep 1, _HitlGate.before_superstep raises korchestrator.exceptions.
      GovernanceHaltError → the SDK's kernel halts the run immediately with
      RunStatus.GOVERNANCE_PAUSED → a human_request event streams to the UI, which renders
      the sign-off gate.
9. User clicks Approve/Reject → Browser POSTs {API_BASE}/api/swarm/fincrime/{run_id}/approve
      (or /reject) → backend resumes (or halts) the run accordingly.
10. On completion: reconciler agent produces a deterministic (non-LLM) risk-graded
      assessment from the 5 findings' fixed severities → a final `assessment` event streams,
      then `run_completed` → EventSource closes on both ends.
```

Source citations: `dashboard/backend/fincrime_router.py`, `dashboard/backend/fincrime_data.py`, `dashboard/frontend/src/InvestigationConsole.tsx`, `dashboard/README.md`'s "Scenario 4 (HITL) reject" section, `docs/adr/0019-governance-halt-veto-wired-in-hooks-and-pregel.md`.

### 3.4 Background jobs, queues, workers, schedulers

**No queue system, no worker pool, no scheduler exists anywhere in either the SDK or the dashboard.** Runs are launched as in-process `asyncio.create_task`/`asyncio.to_thread` background tasks within the single FastAPI process — there is no Celery, RQ, Sidekiq, cron, or message broker (no `requirements.txt`/`pyproject.toml` dependency on any of these was found). The only durable, checkpointed execution mechanism is the SDK's own optional Temporal runtime (`[temporal]` extra), which the dashboard does not currently drive for HITL (§1.3, §19). Source: absence confirmed by dependency-file review (§2.6) and by both backend deep-dive passes finding only `asyncio` primitives.

---

## 4. Infrastructure and Servers

**This section documents what infrastructure the repository *describes as reviewable IaC*, and what could not be independently verified as actually provisioned.** No live AWS account, cloud console, or infrastructure API was accessed to compile this document.

### 4.1 Cloud/provider/platform

**Amazon Web Services (AWS)** is the only cloud provider referenced anywhere in the repository, exclusively for the dashboard application. Services named: ECS Fargate, Application Load Balancer (ALB), S3, CloudFront, Secrets Manager, CloudWatch Logs, Bedrock, ECR. Source: `dashboard/aws/README.md`, `dashboard/aws/ecs-task-definition.json`.

**The SDK itself has no cloud infrastructure of any kind** — no root-level Dockerfile, no docker-compose, no deployment manifest exists at the repository root (verified: `find . -maxdepth 1 -iname "Dockerfile*" -o -iname "docker-compose*"` returns nothing except `.dockerignore`). This is consistent with, and required by, the SDK's own golden rule 6 ("Deployment = publishing artifacts, not running a service").

### 4.2 Explicit statement from the repository itself: nothing has been applied

`dashboard/aws/README.md`'s own header states, verbatim: *"These files are the Fargate/ALB deployment shape... written as reviewable configuration for a human to inspect, adapt, and apply through your own change-management process. **Nothing here has been run** — no `aws` CLI command, no Terraform, no live AWS account was touched while producing these files."* Every `<ACCOUNT_ID>`, `<REGION>`, `<TAG>` in the JSON files is an unfilled placeholder.

**However**, one piece of contradicting evidence exists: `dashboard/playwright.config.ts` sets its default `baseURL` to a specific, real-looking AWS ALB DNS name: `http://korchestrator-dashboard-alb-1152581108.eu-west-2.elb.amazonaws.com` (region `eu-west-2`, London). This strongly suggests a deployment *was* stood up at some point (ALB DNS names are auto-generated per-load-balancer by AWS, not guessable/fabricated), even though the IaC README says "nothing has been run." **Not found / requires verification**: whether this ALB (a) currently exists and is live, (b) was a manually-provisioned, temporary environment not tracked by the committed IaC files, or (c) is stale/decommissioned. This review made no network request to that hostname. Source: `dashboard/playwright.config.ts`.

### 4.3 Servers / instances — as described by the (unapplied) IaC

| Resource | Type | Spec | Purpose | Source |
|---|---|---|---|---|
| ECS Fargate service (backend) | Serverless container, `awsvpc` network mode | `cpu: "512"` (0.5 vCPU), `memory: "1024"` (1 GB) | Runs the FastAPI backend container | `dashboard/aws/ecs-task-definition.json` |
| ALB | Application Load Balancer | Not specified (AWS-managed) | Fronts the backend Fargate service; health check `/api/config`; **idle timeout must be raised to ≥3600s** for the SSE stream not to be dropped mid-run (explicitly called out) | `dashboard/aws/README.md` step 5 |
| S3 bucket | Object storage | Not specified | Hosts the built frontend static assets | `dashboard/aws/README.md` step 6 |
| CloudFront distribution | CDN | Not specified | Public entry point: default origin → S3 (static assets), `/api/*` path-pattern origin → ALB, so the browser only ever sees one origin | `dashboard/aws/README.md`, architecture diagram |
| Secrets Manager | 3 named secrets | N/A | `korchestrator-dashboard/bedrock-bearer-token`, `.../openai-api-key`, `.../anthropic-api-key` | `dashboard/aws/README.md` step 2, `ecs-task-definition.json` |
| CloudWatch Logs | Log group `/ecs/korchestrator-dashboard-backend` | N/A | Container stdout/stderr | `ecs-task-definition.json` logConfiguration |
| ECR repository | Container registry | N/A | `korchestrator-dashboard-backend` — holds the backend image | `dashboard/aws/README.md` step 1 |

**Number of servers/instances:** Fargate is serverless (no fixed VM count is declared; ECS service `desiredCount` is **not found / requires verification** — not present in the reviewed `ecs-task-definition.json`, which defines the task shape only, not the service's scaling configuration).

**Number of containers:** 1 backend container per Fargate task (`ecs-task-definition.json`'s `containerDefinitions` array has exactly one entry, `name: "backend"`). Locally (docker-compose): 2 containers (`backend`, `frontend`).

**What runs on each:**
- Backend Fargate container: the FastAPI app (`uvicorn main:app`), port 8000.
- Frontend: **not containerized in the AWS shape** — served statically from S3/CloudFront, not from a container (unlike the local docker-compose setup, which does containerize the frontend behind nginx).

### 4.4 Development / staging / production mapping

**Not found / requires verification.** No file anywhere names distinct "dev", "staging", or "production" AWS environments, accounts, or parameter sets for the dashboard. The single `ecs-task-definition.json`/IAM policy set is generic (placeholder account/region), with no `-dev`/`-staging`/`-prod` naming convention or per-environment override files. The SDK repository's own `dev`/`staging`/`main` git branches (§2.3) govern SDK *code* promotion, not dashboard *deployment* environments — nothing ties a specific dashboard deployment to a specific git branch.

### 4.5 Ports and networking

| Component | Port | Context |
|---|---|---|
| Dashboard backend (uvicorn) | 8000 | Container `EXPOSE`, docker-compose mapping, ECS `containerPort`, direct-debug access in local compose |
| Dashboard frontend (nginx, containerized) | 80 (container) → 8080 (host, local compose) | `dashboard/frontend/Dockerfile`, `docker-compose.yml` |
| Dashboard frontend (Vite dev server) | 5173 (documented) / proxy target 3000 referenced in `vite.config.ts` per frontend review — **minor inconsistency, not independently reconciled by this review** | `dashboard/README.md` says 5173; the frontend deep-dive noted `vite.config.ts` proxies from port 3000 — both cannot be the literal dev-server port simultaneously; treat the discrepancy as unresolved |
| SDK — no ports | N/A | The SDK is a library; it never listens on a port itself |
| Temporal (optional, local dev only) | 7233 (default, `TEMPORAL_ADDRESS`) | `llms.txt` §9 env var table; only relevant if a developer runs `temporal server start-dev` locally — not part of any deployed dashboard environment |

### 4.6 Domains, DNS, reverse proxy, SSL/TLS

**No custom domain is configured or referenced anywhere in the repository.** The only hostname found is the auto-generated ALB DNS name in §4.2 (`*.elb.amazonaws.com`) — no Route53 zone file, no ACM certificate reference, no CloudFront custom domain / alternate domain name (CNAME) configuration exists in any reviewed file. **Not found / requires verification**: production domain, DNS provider, SSL/TLS certificate management.

**Reverse proxy:** two layers, both verified in source:
1. **nginx** (local docker-compose and, per the frontend Dockerfile's reusability, presumably also usable standalone): proxies `/api/*` → backend, with `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 3600s` specifically to keep SSE streams alive and unbuffered (`dashboard/frontend/nginx.conf.template`).
2. **CloudFront** (AWS target shape, unapplied): default origin → S3 static assets; second, path-pattern origin (`/api/*`) → ALB (`dashboard/aws/README.md`).

**TLS:** not addressed in any reviewed dashboard file (no ACM certificate ARN, no HTTPS listener configuration in the ECS task definition or IAM policies, no explicit mention of TLS termination point). CloudFront would typically terminate TLS for the public-facing distribution by default AWS behavior, but this is inferred from AWS's general default posture, not from anything in the repository — **not found / requires verification**.

### 4.7 Firewall / security configuration

No security group definitions, network ACLs, or WAF configuration exist in the repository (the reviewed IaC is limited to a task definition and two IAM policy JSONs — no `SecurityGroup` resource, no VPC/subnet references). **Not found / requires verification.**

### 4.8 Storage and volumes

No persistent volume, EBS, or EFS configuration exists anywhere. The ECS task definition declares no `volumes` block (verified in the read of `ecs-task-definition.json`). All application state (both scenario code paths) is in-process memory, lost on container restart (§10).

### 4.9 Database hosting

**None.** No database of any kind — local, containerized, or managed — exists in either the SDK or the dashboard, despite `dashboard_spec.md`'s architecture diagram naming a "Local persistent storage / SQLite" component that was never implemented. See §10 for full detail.

### 4.10 Third-party infrastructure

- **AWS Bedrock** (LLM inference) — via boto3/IAM role, region-scoped to specific model + cross-region inference-profile ARNs (not `bedrock:*` on `*`) per `dashboard/aws/iam-task-role-policy.json`.
- **OpenAI API**, **Anthropic API** — direct HTTPS API calls via `litellm`, keyed by `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`.
- **LangSmith** (optional, cloud tracing service) — via `langsmith` SDK, keyed by `LANGSMITH_API_KEY`/`LANGCHAIN_API_KEY`.
- **KCG ("Kendra Context Graph") service** — a self-hosted or remote HTTP service (default `http://localhost:8503`), not identified in this repository as a specific managed product; treated as an external dependency reached via `httpx`. **Not found / requires verification**: what actually runs the KCG service, where it's hosted, or whether it's part of this same organization's other infrastructure.

---

## 5. Deployment Architecture

### 5.1 Deployment methodology

**SDK:** publishing versioned build artifacts (wheel + sdist) as **GitHub Releases** and to **PyPI** via Trusted Publishing ([ADR 0021](docs/adr/0021-repository-goes-public-pypi-trusted-publishing.md), superseding ADR 0020's private-only pass). There is no "running service" deployment for the SDK; "deployment" here means only artifact publication. Source: `.github/workflows/release.yml`, `docs/releases.md`.

**Dashboard:** two documented, alternative deployment paths, both manual (no automated CD pipeline exists for either — see §6):
1. **Local**: `docker compose -f dashboard/docker-compose.yml up --build` — one command, two containers.
2. **AWS** (reviewable, unapplied IaC): manually build/push a Docker image to ECR, manually create Secrets Manager secrets, manually create IAM roles, manually register an ECS task definition and stand up a Fargate service behind an ALB, manually build the frontend and sync to S3, manually configure CloudFront. Fully documented as an ordered, human-executed runbook in `dashboard/aws/README.md` — **not automated by any CI/CD workflow** (confirmed: `.github/workflows/*.yml` contains zero references to `dashboard`, `aws`, `ecs`, `docker build`, or `docker push` for the dashboard app — see §6.1).

### 5.2 Branch-to-environment mapping

**SDK:** `main` → the only branch tags are cut from → the only branch a GitHub Release is ever published from. `dev`/`staging` never publish artifacts.

**Dashboard:** **no mapping exists.** No CI/CD workflow deploys the dashboard on any push to any branch (§6.1). Deployment, per the AWS README, is an entirely manual, developer-initiated sequence of `aws`/`docker` CLI commands run from whatever branch checkout the operator has locally — not tied to `dev`/`staging`/`main` in any automated way.

### 5.3 Build process

**SDK:** `python -m build` → wheel + sdist via the `hatchling` backend, version single-sourced from `src/korchestrator/version.py` (`[tool.hatch.version] path = "..."` in `pyproject.toml`).

**Dashboard backend image:** documented in detail in §5.4 below.

**Dashboard frontend image:** `dashboard/frontend/Dockerfile` stage 1 (`node:20-alpine`) — `npm ci` → `tsc && vite build` (per `package.json`'s `build` script), with build args `VITE_API_BASE` (default `""`) and `VITE_BEDROCK_MODEL` (default a specific Bedrock model ID string, though this variable is **declared but never read** by any current frontend source file — dead build arg, see §19) baked in as `ENV` before the build so Vite inlines them at build time (Vite env vars are compile-time, not runtime).

### 5.4 Dashboard backend Dockerfile — build process and a verified defect

`dashboard/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim AS base
# (single stage despite the "AS base" label — no second stage exists)
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir '.[all]'
COPY dashboard/backend/requirements.txt ./dashboard-requirements.txt
RUN pip install --no-cache-dir -r ./dashboard-requirements.txt
COPY dashboard/backend/main.py dashboard/backend/gateway.py ./
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build context must be the repository root** (not `dashboard/backend/`) since it needs `src/` and `pyproject.toml` to install the SDK from source (the SDK isn't published to PyPI). Documented build commands: via `docker-compose` (context `..`), or directly `docker build -f dashboard/backend/Dockerfile -t korchestrator-dashboard-backend .` from the repo root.

**Verified defect (confirmed independently by this review, not just relayed from a subagent).** `main.py` unconditionally imports three router modules at module load time (`main.py` lines 30-49):

```python
try:
    from support_escalation_router import router as support_escalation_router
except ImportError:
    from dashboard.backend.support_escalation_router import (
        router as support_escalation_router,
    )
# (same two-path try/except pattern repeated for fincrime_router and researcher_router)
```

This two-level fallback supports running `main.py` either from inside `dashboard/backend/` (flat import) or from the repository root (`dashboard.backend.X` import) — but **neither path exists inside the built Docker image**, because the `COPY` instruction (line 25) copies only `main.py` and `gateway.py` into the image's flat `/app` directory. `support_escalation_router.py`, `fincrime_router.py`, `researcher_router.py` (and their dependency `fincrime_data.py`, plus `tracing.py`/`kcg_tracing.py`, which `main.py` also imports) are **not present anywhere in the image**. Both `try`/`except ImportError` branches would fail, and the second failure is not caught by anything further — **the container's `uvicorn main:app` process would crash at import time with an uncaught `ImportError` and never successfully start.** This is a real, reproducible break in the documented Docker/docker-compose/AWS deployment path as currently written, not a hypothetical risk. See §19 for remediation guidance.

### 5.5 Deployment process — from `git push` to a running dashboard (as documented, manual)

```
1. Developer edits dashboard/backend/*.py and/or dashboard/frontend/src/*.tsx, commits, pushes
   (subject only to the repo's generic pre-commit hooks — none of which run dashboard-specific
   checks; see §6.4, §19).
2. NO automated CI runs against dashboard/ changes (verified — see §6.1).
3. NO automated deployment triggers on any push.
4. A human, manually, per dashboard/aws/README.md:
   a. docker build -f dashboard/backend/Dockerfile -t <ecr-repo>:<tag> .   (from repo root)
      [would currently fail to start per §5.4's verified defect, once run]
   b. docker push to ECR
   c. aws secretsmanager create-secret ... (x3, from local shell env, one-time/as-needed)
   d. aws ecs register-task-definition --cli-input-json file://dashboard/aws/ecs-task-definition.json
      (after manually filling in <ACCOUNT_ID>/<REGION>/<TAG> placeholders)
   e. Manually create/update the ECS Fargate service behind an ALB (health check /api/config,
      port 8000, idle timeout ≥3600s)
   f. docker build (or plain npm run build) the frontend, `aws s3 sync dist/ s3://<bucket> --delete`
   g. Manually configure/invalidate CloudFront
5. No rollback automation, no blue/green, no canary — none of these are described anywhere.
```

Source: `dashboard/aws/README.md` steps 1-6, confirmed against the CI workflow files' absence of any such steps.

### 5.6 Environment variables and secrets in deployment

Handled three different ways across the three deployment contexts:

| Context | Mechanism |
|---|---|
| Local dev (`uvicorn main:app --reload`) | `dashboard/backend/.env` (gitignored), loaded via `python-dotenv`'s `load_dotenv()` in `main.py` |
| Local docker-compose | `env_file: backend/.env` in `docker-compose.yml` — injected at container start, never baked into the image |
| AWS Fargate | Credential-bearing vars (`AWS_BEARER_TOKEN_BEDROCK`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) sourced from **AWS Secrets Manager** via the task definition's `secrets` array (never plaintext `environment`); non-secret config (`AWS_DEFAULT_REGION`, `BEDROCK_MODEL_ID`) is plain `environment` values in the task definition |

Full variable inventory: §12.

### 5.7 Database migrations

**Not applicable — no database exists** (§10). No migration tooling, migration directory, or schema-versioning mechanism was found for the dashboard. (The SDK has an unrelated, code-level concept of "schema_version" on its serialized domain models — a payload-format versioning scheme, not a database migration system — documented in `llms.txt` §9 "Serialization.")

### 5.8 Static/frontend deployment

Local: served by nginx from within the frontend container (`dashboard/frontend/Dockerfile` stage 2). AWS: `aws s3 sync dashboard/frontend/dist s3://<bucket> --delete`, served via CloudFront. No CDN cache-invalidation step is documented after an S3 sync (a stale-cache risk — see §19).

### 5.9 Backend deployment / process management / health checks

**Local docker-compose:** `restart: unless-stopped` on both services; backend healthcheck is a Python `urllib.request.urlopen('http://localhost:8000/api/config')` call, `interval: 15s, timeout: 5s, retries: 5, start_period: 10s`; frontend's `depends_on: backend: condition: service_healthy` — frontend only starts serving once the backend healthcheck passes.

**AWS ECS:** `healthCheck` in the task definition uses the same `/api/config` endpoint via a `CMD-SHELL` Python urllib check, `interval: 30s, timeout: 5s, retries: 3, startPeriod: 15s`.

**Process management:** `uvicorn` runs as PID 1 in the container (no supervisor/process manager, no `--workers` multi-process flag observed in the `CMD`) — a single-process ASGI server. **No `USER` directive** is set in `dashboard/backend/Dockerfile` — the container runs as root by default (a hardening gap, §19). **No `HEALTHCHECK` instruction** exists in the Dockerfile itself (health checking is delegated entirely to the orchestrator — docker-compose or ECS — not baked into the image).

### 5.10 Rollback strategy, restart procedures, zero-downtime

**None of these are documented or implemented anywhere** for the dashboard. No rollback script, no versioned/tagged-and-pinned deployment strategy beyond "build a new image with a new `<TAG>`," no blue/green or canary configuration in the ECS shape, no documented restart procedure beyond Docker's own `restart: unless-stopped` policy (local) or ECS's default task-replacement behavior on health-check failure (implicit AWS behavior, not explicitly configured). **Not found / requires verification / recommended improvement** — see §19.

---

## 6. CI/CD Pipeline

### 6.1 Critical finding: the dashboard has zero CI/CD coverage

Verified directly by this review: `grep -n "dashboard" .github/workflows/*.yml` returns **no matches** in any of the three workflow files. **No workflow lints, type-checks, tests, builds, or deploys anything under `dashboard/`.** All CI/CD infrastructure in this repository exists exclusively for the SDK (`src/korchestrator/`). This means: the dashboard backend's 5 pytest files (§15.1) never run in CI; the dashboard frontend has no lint/build/type-check step in CI at all; the Docker images are never built in CI (so the verified startup defect in §5.4 would not be caught by any automated check); the Playwright E2E suite is not wired into any workflow.

### 6.2 `.github/workflows/ci.yml` (SDK only)

**Triggers:** `push` to `[main, staging, dev]`; `pull_request` (any branch); `workflow_dispatch`. Concurrency group cancels in-progress runs on the same ref. `permissions: contents: read`.

| Job | Purpose | Python | Blocking? |
|---|---|---|---|
| `static` | ruff check + format, `mypy --strict`, doctest-modules, import-linter, `scripts/check_isolation.sh`, `scripts/check_env_reads.py`, `scripts/validate_version.py` | 3.12 | Yes |
| `test` | `pytest tests -m "not temporal" --cov=korchestrator ...`; enforces `core/`≥97%, `models/`≥99% coverage | 3.10, 3.11, 3.12, 3.13 (matrix) | Yes |
| `temporal` | `pytest tests -m temporal` against a clean `[temporal]`-only install | 3.12 | Yes |
| `base-install` | Asserts `dspy`/`temporalio`/`httpx`/`mcp`/`opentelemetry` are NOT importable on a bare `pip install .`; runs `tests/unit/core tests/unit/models tests/smoke` | 3.12 | Yes |
| `security` | `bandit`, `pip-audit --skip-editable` (one documented, owner-attributed CVE suppression), a locally-downloaded `gitleaks` binary secret scan | 3.12 | Yes |
| `build` | `needs: [static, test]` — `python -m build`, installs the wheel into a throwaway venv, smoke-imports, verifies `py.typed` is packaged | 3.12 | Yes |
| `examples` | Runs every `examples/*.py` offline (`MOCK_LLM=true`); **PR-only** | 3.12 | Yes (on PRs) |
| `docs` | `mkdocs build --strict` | 3.12 | Yes |
| `benchmarks` | `pytest benchmarks -m benchmark` + regression comparison vs. committed baseline; **manual dispatch or push-to-main only**, never PRs | 3.12 | **No** — `continue-on-error: true`, purely informational |

Source: `.github/workflows/ci.yml` (252 lines).

### 6.3 `.github/workflows/release.yml` (SDK only)

**Trigger:** `push` on tags matching `v[0-9]+.[0-9]+.[0-9]+`, or `workflow_dispatch`. Publishes to PyPI via Trusted Publishing (ADR 0021, superseding ADR 0020's private-only pipeline).

| Job | Purpose |
|---|---|
| `build` | Validates the version, builds wheel+sdist, verifies the built artifact (not source tree) in an isolated venv, verifies the sdist installs too, generates `SHA256SUMS` |
| `github-release` | Extracts the matching `## [<version>]` section from `CHANGELOG.md`, publishes a **GitHub Release** (not PyPI) with the wheel, sdist, and checksums attached, via `softprops/action-gh-release@v2` |
| `verify-private-install` | Installs the just-released package directly from the private git tag (authenticated with the run's own `GITHUB_TOKEN`), smoke-imports it |

Source: `.github/workflows/release.yml` (129 lines).

### 6.4 `.github/workflows/docs.yml` (SDK only)

**Triggers:** push to `main` filtered to `docs/**`, `mkdocs.yml`, `src/korchestrator/**`, or the workflow file itself; `workflow_call`; `workflow_dispatch`. Builds with `mkdocs build --strict`, deploys to **GitHub Pages** via `actions/deploy-pages@v4`.

### 6.5 Pre-commit / local git hooks

`.pre-commit-config.yaml` — generic file hygiene (large-file/merge-conflict/YAML-TOML checks, private-key detection), `ruff`/`ruff-format`, `mypy --strict` (scoped to `files: ^src/korchestrator/` — **does not touch `dashboard/`**), `bandit` (same scoping), `gitleaks`, and three local script-backed hooks (`check_isolation.sh`, `check_env_reads.py`, `validate_version.py`).

`.claude/hooks/pre-commit-check.sh` — the **Claude Code** commit-time hook (distinct from the `pre-commit` framework), checks exactly two things and blocks the commit if either fails: (1) the import-isolation gate (same grep pattern as `scripts/check_isolation.sh`, inlined), and (2) that any staged change under `src/` is accompanied by a fresh entry in `.claude/memory/ENGINEERING_LOG.md`. **Neither hook is scoped to or aware of `dashboard/`** — a commit that only touches `dashboard/backend/*.py` triggers neither the mypy/bandit pre-commit hooks (file-path-scoped away) nor the engineering-log requirement (path-scoped to `src/`).

### 6.6 Secrets and credentials in CI

`release.yml`'s `verify-private-install` job uses the workflow run's own scoped `GITHUB_TOKEN` (a GitHub Actions-provided, automatically-rotated credential, not a manually-configured repository secret) to install from the private git tag. No other secret usage was found in any of the three workflow files — no cloud-provider credentials, no LLM API keys, are referenced in CI at all (consistent with the CI suite running entirely offline against `MockLM`/mocked transports, per the SDK's testing rules).

### 6.7 Artifacts

`ci.yml`'s `build` job uploads a `dist` artifact (wheel + sdist) via `actions/upload-artifact`. `release.yml`'s `build` job uploads `release-dist`. `docs.yml` uploads a Pages artifact. No dashboard-related artifact is ever produced by CI (consistent with §6.1).

### 6.8 Failure handling / rollback in CI/CD

CI: any blocking job failing halts the pipeline for that push/PR (standard GitHub Actions behavior — no custom retry/rollback logic beyond `fail-fast: false` on the `test` job's matrix, so one Python version failing doesn't cancel the others). Release: no automated rollback exists if `release.yml` partially fails (e.g., `build` succeeds but `github-release` fails) — a maintainer would need to manually investigate and re-run or manually publish, per the general GitHub Actions re-run mechanism (not a repository-specific script).

### 6.9 Manual vs. automatic steps — summary

| Step | Automatic? |
|---|---|
| SDK lint/type/test/security/build/docs on every push/PR | Automatic (`ci.yml`) |
| SDK release build + GitHub Release publish on tag push | Automatic (`release.yml`) |
| SDK version bump + CHANGELOG update + release PR | Manual, via `scripts/cut_release.py` (human runs the CLI, reviews and merges the PR, then runs `tag`) |
| SDK docs deploy to GitHub Pages | Automatic on push to `main` (`docs.yml`) |
| Dashboard lint/type/test | **Manual only** (`pytest tests/` run by hand — never in CI) |
| Dashboard Docker image build/push | **Fully manual** (`docker build`/`docker push` by hand, per `dashboard/aws/README.md`) |
| Dashboard AWS infrastructure provisioning | **Fully manual** (`aws` CLI commands run by hand) |
| Dashboard frontend deploy to S3/CloudFront | **Fully manual** (`aws s3 sync` by hand) |

---

## 7. URLs, Domains, and Access

| Purpose | URL | Status | Source |
|---|---|---|---|
| Dashboard, local Docker Compose | `http://localhost:8080` (frontend, nginx-proxied) | Verified as documented; not independently started/tested by this review | `dashboard/README.md`, `docker-compose.yml` |
| Dashboard backend, local Docker Compose (debug) | `http://localhost:8000` | Same as above | `dashboard/README.md`, `docker-compose.yml` |
| Dashboard backend, local dev (bare uvicorn) | `http://localhost:8000` | Documented | `dashboard/README.md` |
| Dashboard frontend, local dev (Vite) | `http://localhost:5173` | Documented (see §4.5's port-inconsistency caveat) | `dashboard/README.md` |
| Dashboard E2E test default target | `http://korchestrator-dashboard-alb-1152581108.eu-west-2.elb.amazonaws.com` | **Found in test config; current live/operational status NOT independently verified — no request was made to this host by this review** | `dashboard/playwright.config.ts` |
| Dashboard "production" URL | **Not found / requires verification** | — | No file names a canonical production URL |
| Dashboard staging URL | **Not found / requires verification** | — | — |
| Dashboard admin/dashboard-of-the-dashboard URL | N/A — the dashboard app has no separate admin panel; it is itself the UI | — | — |
| SDK documentation site (built) | Not a fixed public URL captured in-repo; deployed via GitHub Pages per `docs.yml`'s `environment: github-pages` — the actual `page_url` output is runtime-determined by GitHub, not hardcoded anywhere reviewed | Automatically deployed on push to `main` | `.github/workflows/docs.yml` |
| GitHub repository | `https://github.com/Kendralabs/korch-sdk` | Private repo, confirmed via `git remote -v` and `gh repo view` | Git config |
| GitHub Releases (SDK artifact distribution) | `https://github.com/Kendralabs/korch-sdk/releases` (implicit, standard GitHub path) | Automated publish target of `release.yml` | `.github/workflows/release.yml` |
| Security vulnerability reporting | `https://github.com/kendralabs/korch-sdk/security/advisories/new`, or email `security@kendralabs.com` | Documented policy | `SECURITY.md` |
| KCG service (external tracing dependency) | Default `http://localhost:8503`, overridable via `KCG_BASE_URL` | Local/self-hosted by default; production KCG endpoint **not found / requires verification** | `dashboard/backend/kcg_tracing.py` |

**DNS/routing:** as described in §4.6 — no custom domain was found anywhere in the repository; the one discovered hostname is an AWS-auto-generated ALB DNS name.

---

## 8. Authentication and Authorization

### 8.1 Dashboard — verified: no application-level authentication exists

**This is a load-bearing finding for the security assessment (§9).** Every HTTP endpoint in `dashboard/backend/` (all four routers — `main.py`'s scenario endpoints and the three `/api/swarm/*` routers) is **completely unauthenticated**. There is no login flow, no session mechanism, no API-key-gated route, no JWT issuance/validation, no OAuth/SSO integration, and no middleware performing any identity check on inbound requests. This was independently confirmed by this review (grep for `Depends(`, `Security(`, `HTTPBearer`, `OAuth2`, `jwt`, `session` across `dashboard/backend/*.py` — none found in any auth-relevant context) and corroborated by the backend deep-dive.

**What could be mistaken for auth, but isn't:**
- The `api_keys` dict and `GET`/`POST /api/config` endpoints (`main.py` lines 71-75) hold **outbound LLM-provider credentials** (OpenAI/Anthropic/Bedrock) that the dashboard uses to authenticate *itself* to upstream model providers — not credentials that authenticate a *caller* to the dashboard. `POST /api/config` can be called by literally anyone reaching the backend, with no verification of who is calling, and will silently overwrite the process-wide provider credentials.
- The KCG tracing bearer header (`kcg_tracing.py`) is the dashboard authenticating *outbound* to the KCG service — again not inbound auth.

**Network-boundary-only protection:** the only thing standing between an arbitrary network client and full control of the dashboard backend (starting swarm runs, approving/rejecting HITL gates, overwriting LLM credentials) is whatever sits in front of it at the network layer — a home/office network boundary locally, or the ALB/CloudFront + any VPC security groups in the AWS shape (none of which were found configured, per §4.7). **This is consistent with the dashboard's stated purpose as a local/demo/testing tool, not a multi-tenant production service** — but the AWS deployment artifacts (§4, §5) describe internet-facing infrastructure (a public ALB, CloudFront) with no authentication layer added anywhere in that path.

### 8.2 SDK — identity is a port, not a policy

The SDK itself does not implement authentication as a product feature — it defines one ARI port, `IIdentityProvider`, whose **local default implementation is explicitly unsecured** (single-tenant, no real credential check), documented as intended for local development, with an enterprise implementation (KIAM/KACP) as the pluggable alternative for anyone who needs real multi-tenant identity. This is by design (`llms.txt` §1, §3) — the SDK is a library, not a service, so it has no "users" of its own to authenticate; a consuming application (like the dashboard) is responsible for its own auth if it needs any. Source: `docs/specs/00-overview.md` §5, `llms.txt` §3.

Separately, the SDK's optional **remote client** (`korchestrator.remote.KorchestratorClient`, `[remote]` extra) documents a Bearer-token auth *contract* for talking to a hypothetical hosted Korchestrator engine (`Authorization: Bearer <api-key | KIAM JWT>`) — but this describes the client-side contract for a server this repository does not implement or run; it is not authentication *of* anything in this repository. Source: `llms.txt` §6 "Tier 4 — the remote contract."

### 8.3 Roles and permissions

**Dashboard:** none — there is no user/role model at all (no user table, no role field, no permission check anywhere in the code).

**AWS IAM (infrastructure-level, not application-level):** two roles are defined in the reviewable IaC — an execution role (ECR pull + CloudWatch log write + `secretsmanager:GetSecretValue` scoped to exactly the three named dashboard secrets) and a task role (`bedrock:InvokeModel`/`InvokeModelWithResponseStream` scoped to four specific model/inference-profile ARNs, not `bedrock:*` on `*`). These are principle-of-least-privilege scoped for what the *container* is allowed to do against AWS APIs — they have nothing to do with authenticating or authorizing *end users* of the dashboard. Source: `dashboard/aws/iam-execution-role-policy.json`, `iam-task-role-policy.json`.

### 8.4 Logout / session invalidation

Not applicable — there is no login/session to invalidate.

### 8.5 Complete authentication flow, step by step

**There is none to describe.** A request reaches `dashboard/backend/`'s FastAPI app, and every route handler executes unconditionally for any caller who can reach the network endpoint.

---

## 9. Security

### 9.1 Implemented controls (verified)

| Control | Detail | Source |
|---|---|---|
| Secrets never committed to git | `dashboard/backend/.env` exists locally but is **not tracked** (verified: `git ls-files \| grep 'dashboard/backend/\.env$'` returns nothing); root `.gitignore` excludes `.env`, `.env.*`, explicitly re-allowing only `.env.example` | `.gitignore` lines 34-36, verified by this review directly |
| No compiled/cache artifacts committed | `git ls-files dashboard \| grep -E "__pycache__\|\.pyc$"` returns nothing — clean | Verified by this review directly |
| Secrets sourced from AWS Secrets Manager, not plaintext, in the AWS shape | `ecs-task-definition.json`'s `secrets` array (`valueFrom` ARNs) for the 3 credential vars; plain `environment` only for non-secret config | `dashboard/aws/ecs-task-definition.json` |
| Least-privilege IAM scoping | Execution role limited to the 3 named secret ARNs; task role limited to 4 specific Bedrock model/profile ARNs, not wildcard | `dashboard/aws/iam-*-policy.json` |
| Docker build never bakes secrets into the image | Backend Dockerfile copies only `main.py`/`gateway.py` (no `.env`); comment explicitly states this is deliberate even if `.dockerignore` were bypassed | `dashboard/backend/Dockerfile` |
| SDK-level secret typing | Every secret-bearing `Settings` field is typed `SecretStr`; `Settings.__repr__` and serialization render secrets as `**********` | `llms.txt` §9 "Configuration" |
| SDK-level PII/secret redaction | A single consolidated "Shield" redactor (`security/`) masks detected PAN/IBAN/phone/SSN/email/secret patterns to `[MASKED_<TYPE>]`; fails closed for high-sensitivity flows if the redactor/policy engine is unavailable | `llms.txt` §9 "Security" |
| CI secret scanning | `gitleaks` runs in `ci.yml`'s `security` job (downloaded binary, license-cost workaround documented) and again via the `pre-commit` framework's `gitleaks` hook | `.github/workflows/ci.yml`, `.pre-commit-config.yaml` |
| CI static security scan | `bandit -c pyproject.toml -r src/korchestrator` — **scoped only to the SDK**, not `dashboard/` | `.github/workflows/ci.yml` |
| CI dependency vulnerability scan | `pip-audit --skip-editable`, with exactly one documented, owner/reason/expiry/compensating-control suppression (a `diskcache`/pickle CVE in a `[dspy]` transitive dependency) | `.github/workflows/ci.yml` |
| Documented vulnerability disclosure process | Private GitHub Security Advisory form or `security@kendralabs.com` email; 3-business-day acknowledgement SLA, 10-business-day initial-assessment SLA | `SECURITY.md` |
| SDK error-wrapping discipline | No raw `temporalio`/`httpx`/`dspy`/database-driver exception may cross a module boundary; always `raise ... from exc` | `llms.txt` §9 |
| SDK "fail closed" governance default | Redaction/policy/identity provider unavailable → operation denied, never silently allowed through unredacted | `llms.txt` §9 |

### 9.2 Gaps and areas that should be improved (explicitly separated from the above — these are recommendations/risks, not implemented controls)

| Gap | Risk | Recommendation |
|---|---|---|
| **No authentication on any dashboard endpoint** (§8.1) | Anyone who can reach the backend (trivial if the AWS ALB is public-facing with no additional network control) can start arbitrary swarm runs (consuming the operator's LLM spend), overwrite the process-wide LLM provider credentials via `POST /api/config`, and approve/reject HITL gates on other users' runs | Add at minimum a shared API key/bearer-token check in front of state-changing routes before any internet-facing deployment; consider per-run ownership tokens |
| **CORS wide open** (`allow_origins=["*"]`, `allow_credentials=True`) | Combined with no-auth, any web page can script requests against a reachable backend from a victim's browser | Restrict `allow_origins` to the known frontend origin(s) in any non-local deployment |
| **Container runs as root** (no `USER` directive in `dashboard/backend/Dockerfile`) | Standard container-hardening gap — a compromised process has root inside the container | Add a non-root `USER` in the Dockerfile |
| **No security groups / network ACLs found for the AWS shape** | Cannot assess network-layer exposure; if the ALB is deployed in a public subnet with an open security group, the unauthenticated backend is directly internet-reachable | Define and review security groups restricting ALB→ECS traffic and any public ingress before deploying |
| **No TLS/HTTPS configuration found anywhere in the dashboard IaC** | Traffic to/from the ALB (and between ALB and CloudFront, if not using CloudFront's default HTTPS) may be unencrypted unless configured out-of-band | Add an ACM certificate + HTTPS listener to the ALB and confirm CloudFront's viewer protocol policy forces HTTPS |
| **Verified Docker startup defect** (§5.4) means the documented deployment path, if actually run today, would crash — a reliability/availability issue, not confidentiality, but blocks any real deployment from succeeding | Service would fail to start / continuously restart-crash-loop | Fix the Dockerfile's `COPY` list (§19) before attempting any real deployment |
| **No CI coverage for the dashboard at all** (§6.1) | Backend Python code (auth-adjacent logic, credential handling in `gateway.py`, tracing exporters) is never lint/type/security-scanned automatically; a regression (like the Docker defect above) ships silently | Add a dashboard-scoped CI job (lint, type-check, `pytest dashboard/backend/tests`, and ideally a Docker build+smoke-start check) |
| **`fincrime_router.py`'s `_HitlGate`/HITL-reject path has a known, documented SDK-level hang bug** under nested `asyncio.to_thread` + an already-running event loop (one test is explicitly skipped for this reason, with an owner-attributed reason) | A production HITL-reject action could hang the request/worker | Track and fix the underlying SDK hang (referenced but not resolved in the reviewed code) |
| **No rate limiting anywhere** | An unauthenticated caller can launch unbounded concurrent swarm runs, each consuming real LLM API spend | Add request/run rate limiting, especially before exposing the dashboard publicly |
| **`available_models()` in `gateway.py` doesn't verify credentials are actually valid before advertising a model** (it returns a fixed catalog regardless of configured keys) | A user could select a model whose provider key is absent/invalid and only discover the failure at request time | Align `available_models()` with which keys are actually configured (as the original spec intended) |
| **Frontend Playwright tests target markup that doesn't exist in the current UI** (§15.2) | False sense of test coverage; a real regression in the current UI would not be caught by these tests | Rewrite or remove the stale E2E suite |

### 9.3 Scope note

Per `SECURITY.md` itself, the SDK's own security policy explicitly states its scope is "the code in this repository — the published `korchestrator` distribution and its documented public surface," and that infrastructure a consumer operates (a Temporal cluster, a database, a model gateway, MCP servers) is **outside** that policy's coverage and is the operator's responsibility. This document's dashboard-specific findings above (§9.2) fall into that "operator responsibility" zone from the SDK's own policy perspective, but are documented here in full since the dashboard's infrastructure is itself committed to this same repository.

---

## 10. Database

**There is no database anywhere in this repository — neither in the SDK nor in the dashboard.**

### 10.1 SDK

The SDK defines a `GraphRepository` protocol (an ARI-adjacent internal port) for its "bitemporal Context Graph" concept, with exactly one shipped implementation: an **in-memory** backend (`PERSISTENCE_BACKEND=none|memory`, default `memory`). No SQL, NoSQL, or graph-database driver is a dependency of the SDK at any extras tier. External graph/SQL backends are explicitly documented as "post-1.0, interface now, implement minimally" — i.e., deliberately not built yet, not a gap in what's shipped today. Source: `llms.txt` §4, §9 ("Configuration" — `PERSISTENCE_BACKEND` env var).

### 10.2 Dashboard

`dashboard_spec.md`'s own architecture diagram (§2) names a `DB_Store[Local persistent storage / SQLite]` component as part of the intended backend design. **This was never implemented.** Verified directly: zero occurrences of `sqlite`/`SQLite`/`sqlite3` anywhere in `dashboard/backend/*.py`; no ORM (no SQLAlchemy, no Tortoise, etc.) in `requirements.txt`; no `.db`/`.sqlite3` file, no migration directory, no `conftest.py` fixture wiring up a database. All application state — every router's run registry, event log, and `main.py`'s own `active_runs`/`api_keys` — is a plain in-process Python `dict`/`list`, **entirely lost on process restart.** This is a confirmed, direct spec-vs-implementation gap (§19).

### 10.3 Consequences of the in-memory-only design

- No run history survives a backend restart or redeploy.
- No multi-instance/horizontally-scaled deployment is possible without external shared state — running 2+ backend replicas behind the ALB (a natural next step for availability) would silently break, since a `/stream/{run_id}` request could land on a replica that never saw that run started.
- No audit trail persists beyond the life of one process (relevant given the app's HITL/governance demo purpose, which implies an audit-trail-adjacent use case).

---

## 11. APIs and Integrations

### 11.1 Internal APIs — dashboard backend, complete endpoint inventory

All endpoints are unauthenticated (§8.1). Base path varies by router; `main.py` mounts at root (`/api/...`), each domain router has its own prefix.

**`main.py` (no additional prefix beyond what's shown):**

| Method | Path | Purpose | Streaming |
|---|---|---|---|
| GET | `/api/config` | Boolean flags: which credentials/tracing integrations are configured | No |
| POST | `/api/config` | Overwrite in-memory provider credentials (`openai_key`, `anthropic_key`, `bedrock_token`) | No |
| POST | `/api/runs/start` | Launch one of `scenario1`–`scenario4` (Korch/Swarm/tools/HITL demos) | No (async background) |
| POST | `/api/runs/{run_id}/approve` | Resume a HITL-paused run with approval | No |
| POST | `/api/runs/{run_id}/reject` | Resume a HITL-paused run with rejection (raises `GovernanceHaltError`) | No |
| GET | `/api/runs/{run_id}/stream` | SSE event stream for a `/api/runs/start` run | Yes (SSE, push-based) |

**`fincrime_router.py`** (prefix `/api/swarm/fincrime`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/run` | Start the 6-agent investigation swarm |
| GET | `/stream/{run_id}` | SSE stream (poll-based) |
| POST | `/{run_id}/approve` | Approve the HITL sign-off |
| POST | `/{run_id}/reject` | Reject the HITL sign-off |

**`support_escalation_router.py`** (prefix `/api/swarm/support-escalation`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/run` | Start the 4-agent pipeline |
| GET | `/stream/{run_id}` | SSE stream (push-based) |

**`researcher_router.py`** (prefix `/api/swarm/researcher`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/run` | Start the 1-agent Q&A swarm |
| GET | `/stream/{run_id}` | SSE stream (poll-based) |

All request/response bodies are typed Pydantic `BaseModel`s (`RunRequest`/`RunResponse`, `SwarmStartRequest`/`AgentInput`, `KeyConfigRequest`, `SignoffRequest`), giving free 422 validation on malformed input. Full field-level detail: §3.2 and the underlying agent report cited in this document's compilation (source files listed in §20).

### 11.2 External APIs consumed by the dashboard

| Service | Purpose | Auth mechanism | Where configured |
|---|---|---|---|
| OpenAI API | LLM completions | `OPENAI_API_KEY` | `.env` / Secrets Manager |
| Anthropic API | LLM completions | `ANTHROPIC_API_KEY` | `.env` / Secrets Manager |
| AWS Bedrock | LLM completions (Claude via Bedrock) | `AWS_BEARER_TOKEN_BEDROCK`, or boto3's standard AWS credential chain (e.g., ECS task IAM role) | `.env` / Secrets Manager (bearer token) or IAM role (ECS) |
| LangSmith | Optional LLM call tracing | `LANGSMITH_API_KEY` / `LANGCHAIN_API_KEY` | `.env` (not present in the AWS task definition — unconfigured in that environment) |
| KCG service | Optional decision/trace ingestion | `KCG_API_KEY` (bearer header, outbound) | `.env` (not present in the AWS task definition) |

### 11.3 AI/LLM providers and models

| Provider | Default/example model | Configured via |
|---|---|---|
| AWS Bedrock | `us.anthropic.claude-sonnet-4-20250514-v1:0` (cross-region inference profile) | `BEDROCK_MODEL_ID` env var; this is the model the AWS task definition sets as a plain (non-secret) environment value |
| OpenAI | `openai/gpt-4o`, `openai/gpt-4o-mini` (hardcoded in `gateway.py`'s static catalog) | Model name passed per-request; catalog in `gateway.py.available_models()` |
| Anthropic (direct) | `anthropic/claude-3-5-sonnet` (hardcoded in `gateway.py`'s static catalog) | Same |
| Anthropic (via Bedrock, frontend build-time default) | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` (`VITE_BEDROCK_MODEL` Dockerfile default — but see §19: this value is never actually read by any current frontend component) | Frontend Docker build arg (currently dead) |
| MockLM (SDK default, offline) | N/A — deterministic scripted responses | SDK default when no provider key is configured |

### 11.4 Webhooks

**None found.** No webhook receiver endpoint or outbound webhook-sending code exists in the dashboard. (The SDK's *documented, optional* remote-client contract in `llms.txt` §6 describes a webhook concept for a hypothetical hosted engine — not implemented or run by anything in this repository.)

### 11.5 API keys / secrets — where configured (names only, no values; full table in §12)

See §12 for the complete environment-variable inventory including which are secret-bearing.

---

## 12. Configuration and Environment Variables

### 12.1 Dashboard backend — environment variables (names and purpose only; no values read or reproduced)

| Variable | Purpose | Secret? | Consumed by | Configured in AWS as |
|---|---|---|---|---|
| `OPENAI_API_KEY` | OpenAI API authentication | **Yes** | `main.py`, `gateway.py`, `fincrime_router.py`, `researcher_router.py`, `support_escalation_router.py` | Secrets Manager (`korchestrator-dashboard/openai-api-key`) |
| `ANTHROPIC_API_KEY` | Anthropic API authentication | **Yes** | `main.py`, `gateway.py` | Secrets Manager (`korchestrator-dashboard/anthropic-api-key`) |
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock bearer-token authentication | **Yes** | `main.py`, `gateway.py` | Secrets Manager (`korchestrator-dashboard/bedrock-bearer-token`) |
| `AWS_DEFAULT_REGION` | AWS region for Bedrock calls | No | `gateway.py` | Plain `environment` |
| `BEDROCK_MODEL_ID` | Overrides which Bedrock model is called | No | `gateway.py` | Plain `environment` |
| `OPENAI_DEFAULT_MODEL` | Default OpenAI model when unspecified | No | `gateway.py` | Not present in AWS shape (unconfigured there) |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint | No (endpoint, not credential) | `fincrime_router.py`, `researcher_router.py`, `support_escalation_router.py` | Not present in AWS shape |
| `LANGSMITH_API_KEY` | Enables LangSmith tracing | **Yes** | `main.py`, `tracing.py` | Not present in AWS shape — feature is off in that environment |
| `LANGCHAIN_API_KEY` | Alias/alternate for the above | **Yes** | `main.py`, `tracing.py` | Not present in AWS shape |
| `LANGSMITH_PROJECT` | LangSmith project name | No | `tracing.py` | Not present |
| `LANGCHAIN_PROJECT` | Alias for the above | No | `tracing.py` | Not present |
| `KCG_API_KEY` | Enables KCG tracing/decision export | **Yes** | `main.py`, `kcg_tracing.py` | Not present in AWS shape — feature is off in that environment |
| `KCG_BASE_URL` | KCG service endpoint (default `http://localhost:8503`) | No | `kcg_tracing.py` | Not present |
| `KCG_PROJECT_ID` | KCG project scoping | No | `kcg_tracing.py` | Not present |
| `KCG_ORG_ID` | KCG org scoping | No | `kcg_tracing.py` | Not present |

Source: grep of `os.environ`/`os.getenv` across `dashboard/backend/*.py`, cross-referenced against `dashboard/aws/ecs-task-definition.json`'s `environment`/`secrets` arrays.

### 12.2 Dashboard frontend — environment variables

| Variable | Purpose | Consumed? |
|---|---|---|
| `VITE_API_BASE` | Base URL the frontend calls for `/api/*` | **Yes** — `App.tsx` |
| `VITE_BEDROCK_MODEL` | Intended default Bedrock model for the UI | **No — declared in `vite-env.d.ts` and threaded through the Dockerfile, but not read by any current component** (dead/unused build arg) |
| `BACKEND_HOST` | nginx-template-only (not a Vite var); substituted by nginx's `envsubst` entrypoint at container start | Yes, at the nginx-config level |

### 12.3 Dashboard `.env.example` files

`dashboard/backend/.env.example` and `dashboard/frontend/.env.example` both exist and are the intended template for local setup (`dashboard/README.md` step 2: `Copy-Item .env.example .env`). **This review's file-access tooling was denied permission to read either `.env.example` file** (blocked before any content was seen, consistent with a `.env*`-pattern deny rule) — their exact documented variable set could not be independently cross-checked against the grep-derived table above. **Not found / requires verification**: confirm `.env.example` lists the same variables as §12.1/§12.2 and no others.

### 12.4 SDK — environment variables

The SDK defines its own, separate set of environment variables (all read exclusively in `korchestrator.config`, per the SDK's own single-reader architecture rule, enforced by `scripts/check_env_reads.py` and a CI test). Full table (30 variables — `MOCK_LLM`, `KENDRA_AI_GATEWAY_URL`, `GOVERNANCE_TRUST_THRESHOLD`, `PERSISTENCE_BACKEND`, `ROUTING_STRATEGY`, `KORCH_RUNTIME`, `TEMPORAL_ADDRESS`, etc.) is documented exhaustively in `llms.txt` §9 "Configuration" — not duplicated here to avoid drift between two copies; treat `llms.txt` §9 as authoritative for SDK-level config, this document as authoritative for dashboard-level config.

### 12.5 Development / staging / production differences

**Not found / requires verification** beyond what §12.1's "Configured in AWS as" column shows (which variables are wired into the one reviewed AWS environment vs. left unconfigured there). No separate `.env.staging`/`.env.production` file or environment-specific config convention exists anywhere in the repository.

### 12.6 Required configuration for a new deployment

**Minimum to run the dashboard locally:** `dashboard/backend/.env` populated with at least one of `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`AWS_BEARER_TOKEN_BEDROCK`+`AWS_DEFAULT_REGION` (the SDK's own default `MockLM` gateway would technically let scenarios run with zero keys, but `gateway.py`'s `LiteLLMGateway`/the domain routers' `OfflineGateway` fallback is what actually engages when no key is present — real LLM behavior requires at least one real key).

**Minimum to deploy to AWS per the reviewable IaC:** an AWS account, the three Secrets Manager secrets created, the two IAM roles created, `<ACCOUNT_ID>`/`<REGION>`/`<TAG>` placeholders filled into `ecs-task-definition.json`, an ECR repository, an ALB with a ≥3600s idle timeout, an S3 bucket, and a CloudFront distribution — **and the Docker startup defect in §5.4 fixed first**, or the ECS service will never reach a healthy state.

---

## 13. Operations and Maintenance

All commands below are drawn directly from files in this repository; none are inferred/assumed beyond what's documented.

### 13.1 Start / stop / restart

**SDK:** not applicable — it's a library, nothing to start/stop as a service.

**Dashboard, local (bare processes):**
```powershell
# Backend
cd dashboard/backend
python -m uvicorn main:app --reload --port 8000
# Frontend
cd dashboard/frontend
npm run dev
```

**Dashboard, local (Docker Compose):**
```bash
docker compose -f dashboard/docker-compose.yml up --build      # start (foreground)
docker compose -f dashboard/docker-compose.yml up -d --build   # start (detached)
docker compose -f dashboard/docker-compose.yml down             # stop
docker compose -f dashboard/docker-compose.yml restart backend  # restart one service
```
(`docker compose restart` is standard Compose CLI behavior; not a custom script in this repo — included here as the standard operational command given the `docker-compose.yml` that exists.)

### 13.2 View logs

**Local Compose:** `docker compose -f dashboard/docker-compose.yml logs -f backend` / `-f frontend` (standard Compose CLI; the compose file itself defines no custom log driver).

**AWS:** CloudWatch Logs, log group `/ecs/korchestrator-dashboard-backend`, stream prefix `backend` — via the AWS Console or `aws logs tail /ecs/korchestrator-dashboard-backend --follow`. Source: `dashboard/aws/ecs-task-definition.json`'s `logConfiguration`.

**SDK's own logging:** off by default (a `NullHandler` on the `korchestrator` logger); a consuming application enables it via `korchestrator.enable_logging(level="INFO")`. The dashboard backend does not appear to call this (not found in the reviewed `main.py`/router files) — it uses plain Python `logging.basicConfig(level=logging.INFO)` (`main.py` line 52) for its own app-level logs instead.

### 13.3 Monitor resources / check health

**Local Compose:** `docker compose -f dashboard/docker-compose.yml ps` (shows healthcheck status). Manual check: `curl http://localhost:8000/api/config`.

**AWS:** ECS console/CLI (`aws ecs describe-services`), CloudWatch metrics (implicit AWS default metrics for Fargate — CPU/memory utilization — no custom CloudWatch alarms or dashboards were found configured anywhere in the repository).

### 13.4 Debug common failures

No repository-documented runbook exists for common dashboard failure modes. Based on this review's findings, the most likely failure a new operator will hit:
- **Container crash-loops on startup** → almost certainly the verified `ImportError` defect in §5.4 (missing router-module files in the image) until fixed.
- **SSE stream drops mid-run in AWS** → ALB idle timeout not raised to ≥3600s (explicitly called out in `dashboard/aws/README.md`).
- **HITL reject appears to hang** → the documented, known SDK-level hang bug on `fincrime_router.py`'s reject path (test explicitly skipped for this reason).

### 13.5 Update dependencies

**SDK:** version ranges are pinned in `pyproject.toml`; a dependency bump is a normal PR following the standard branch/PR workflow (§2.4), subject to `pip-audit` in CI catching known vulnerabilities.

**Dashboard:** `dashboard/backend/requirements.txt` (Python, no lockfile — plain `>=` minimum-version pins, no upper bounds observed beyond what was read) and `dashboard/frontend/package-lock.json` (npm, pinned). No automated dependency-update tooling (no Dependabot config, no Renovate config) was found anywhere in the repository. **Not found / requires verification / recommended**: add Dependabot/Renovate, especially given `dashboard/backend/requirements.txt` has no upper-bound pins.

### 13.6 Deploy a new version

SDK: §5.1/§6.3 (tag-driven, automated `release.yml`). Dashboard: §5.5 (fully manual, per `dashboard/aws/README.md`).

### 13.7 Roll back a deployment

**SDK:** no automated rollback; a maintainer would need to identify the prior good tag/release and re-point consumers at it (`pip install ...@v<older-version>`), or cut a new patch release reverting the change. **Dashboard:** no rollback mechanism exists at all (§5.10) — a maintainer would need to manually rebuild and redeploy a prior image tag.

### 13.8 Database backup/restore, add/remove services, scale

Not applicable to the dashboard (no database — §10). "Add/remove services" for the dashboard would mean editing `docker-compose.yml` or the ECS task definition's `containerDefinitions` array by hand — no service-generation tooling exists. "Scale" — Fargate's `desiredCount` is not set anywhere reviewed (§4.3); scaling would be a manual `aws ecs update-service --desired-count N` (standard AWS CLI, not a repo-specific script), and per §10.3, horizontal scaling beyond 1 replica would break run continuity given the in-memory-only state design.

---

## 14. Monitoring, Logging, and Observability

### 14.1 Application logs

**SDK:** structured, off-by-default logging via one namespaced logger (`korchestrator`), enabled explicitly by a consuming app; structured fields (`run_id`, `tenant_id`, `superstep`, `agent_id`, `event`, `outcome`, `duration_ms`, `trace_id`) via `extra=`, never string interpolation. Never logs credentials, prompts, or completions. Source: `llms.txt` §9 "Logging."

**Dashboard:** plain `logging.basicConfig(level=logging.INFO)` (`main.py` line 52) — unstructured, standard Python logging, not the org-wide "structured logs with a correlation/trace ID" pattern the SDK itself follows. Error paths use `logger.error(...)` in every background-task exception handler. No correlation ID, tenant ID, or trace ID appears in dashboard log calls per the deep-dive review.

### 14.2 Server / container logs

**Local Compose:** Docker's default `json-file` log driver (no custom driver configured in `docker-compose.yml`), viewable via `docker compose logs`.

**AWS:** `awslogs` driver → CloudWatch Logs, group `/ecs/korchestrator-dashboard-backend` (§13.2).

### 14.3 Error tracking

**No dedicated error-tracking service (Sentry, Rollbar, etc.) is integrated anywhere** — errors surface only through standard Python logging and, for dashboard run failures specifically, through the SSE event stream itself (a `status_change`/`run_completed` event carrying `status: "failed"` and `error: str(exc)`, per §3.2/§17). **Not found / requires verification / recommended improvement.**

### 14.4 Metrics

**SDK:** optional OpenTelemetry metrics (`[otel]` extra, `KORCH_TELEMETRY_ENABLED`, default off) — `korch.run.duration`, `korch.superstep.duration`, `korch.agents.active`, `korch.tool.calls`, `korch.model.tokens`, `korch.run.status`. Per `.claude/memory/PROJECT_STATE.md`'s own "known gaps" section (confirmed by the SDK-verification review pass), **only the outer `agent.run` span and two of these metrics are actually wired to fire** — the finer-grained `agent.superstep`/`agent.plan`/`tool.call`/`gen_ai.call` spans and four more metrics are defined in code but not yet connected to the execution path. This is a genuine, self-documented partial-implementation gap, not a documentation error.

**Dashboard:** no metrics emission of any kind (no Prometheus endpoint, no StatsD, no CloudWatch custom metrics) beyond AWS's own implicit Fargate CPU/memory metrics.

### 14.5 Health checks

Covered in §5.9 — `/api/config` used as the healthcheck target in both docker-compose and the ECS task definition (a slightly unusual choice: it's a general config-status endpoint, not a purpose-built `/healthz`, but it does return 200 with no external dependency, so it functions adequately as a liveness check).

### 14.6 Alerts

**None found anywhere** — no CloudWatch Alarms, no PagerDuty/Opsgenie integration, no alert-routing configuration of any kind in the repository. **Not found / requires verification / recommended improvement.**

### 14.7 AI/LLM tracing

Two real, optional, app-level integrations exist specifically for LLM-call tracing, both detailed in §3.2: **LangSmith** (gated on `LANGSMITH_API_KEY`) and a custom **KCG** HTTP exporter (gated on `KCG_API_KEY`) that dual-writes OTLP-shaped spans and graph "Decision" nodes to an external KCG service. Both are additive gateway-wrapper decorators, not SDK-level telemetry (which is the separate, OpenTelemetry-based mechanism in §14.4). Neither is configured/enabled in the one reviewed AWS deployment shape (§12.1).

### 14.8 Where logs are stored / how to investigate production issues

Given the findings above: locally, in the Docker daemon's log storage (ephemeral, container-lifetime); in AWS, in CloudWatch Logs (durable, per the log group's retention setting — **not found / requires verification**, no explicit retention period is set in the reviewed task definition, which per AWS defaults means logs are retained indefinitely unless a retention policy is separately configured on the log group). Investigating a production dashboard issue today would mean: check CloudWatch Logs for the backend's stdout/stderr (unstructured `logging.error` output), check the ECS service's health-check/task-restart history in the AWS console, and — because there is no database and no error tracker — accept that any run that already completed or crashed before you looked has left no queryable trace beyond whatever scrolled through the log stream.

---

## 15. Testing and Quality

### 15.1 Dashboard backend tests (`dashboard/backend/tests/`, 5 files)

**Never run in CI (§6.1) — must be run manually.**

| File | What it verifies |
|---|---|
| `test_fincrime_router.py` | Full offline HITL-approval run streams the expected event sequence (`run_started`→`human_request`→`resolved`→`assessment`→`run_completed`), exactly 5 findings with expected severities, correct risk grade; `agent_models` override accepted; unknown `run_id` → 404. One test (`test_fincrime_reject_is_acknowledged_promptly`) is `@pytest.mark.skip` with an owner-attributed reason documenting a real, reproduced SDK-level hang bug on the HITL-reject path. |
| `test_kcg_tracing.py` | Regression test locking in a real bug fix in `_extract_agent_id` (correctly skips a DSPy system-message template placeholder rather than misreading it as a real agent role). |
| `test_perf_fincrime_swarm.py` | Concurrency/performance regression test: 5 concurrent offline swarm runs, asserts ≥80% success rate and p95 latency <20s; documents a real regression it previously caught (p95 went from a 20s budget to 67s once `KCG_API_KEY` landed in `.env`, before the fix that forces tracing off during this test). |
| `test_researcher_router.py` | Offline single-agent flow completes and answers; custom `question`/`model` params honored; 404 on unknown `run_id`. |
| `test_support_escalation_router.py` | Offline 4-agent pipeline completes with a non-empty resolution and ≥1 superstep event; `agent_models` override honored; 404 on unknown `run_id`; documents a pytest-asyncio-vs-nested-asyncio.run() harness quirk requiring bare `asyncio.run()` per test. |

All five files explicitly strip `OPENAI_API_KEY`/`LANGSMITH_API_KEY`/`LANGCHAIN_API_KEY`/`KCG_API_KEY` from the environment after `main.py` is imported (since `main.py`'s own `load_dotenv()` would otherwise reload real `.env` values), guaranteeing offline, deterministic, network-free execution regardless of local `.env` contents.

**Command to run:** `cd dashboard/backend && pytest tests/ -v` (inferred standard invocation; no dashboard-specific `pytest.ini`/`pyproject.toml` test config section was found, so the SDK repo root's `pyproject.toml` `[tool.pytest.ini_options]` — scoped to `testpaths = ["tests"]`, the *SDK's* `tests/` directory — does **not** apply to `dashboard/backend/tests/`; running pytest from within `dashboard/backend/` is the safest invocation).

### 15.2 Dashboard frontend / E2E tests — verified stale against current code

`dashboard/e2e/*.spec.ts` (Playwright, TypeScript) target CSS selectors/element IDs (`#scenario-scenario1`, `#run-btn`, `#config-btn`, `.modal-title` containing "API Configuration", `#audit-tab`, `.agent-chip`, `#edges-input`, `.topbar-status`) that **do not exist anywhere in the current `dashboard/frontend/src/*.tsx` source** (verified by grep — zero matches for nearly all of these selectors). Git history shows the frontend was rewritten (commit `36d61a7`, replacing a scenario-based UI with the current "investigation console" tab layout) a full week **before** these Playwright specs were added (commit `10db2e9`) — they appear to have been written against `dashboard_spec.md`'s original design or an older deployed build, and were never reconciled with the rewrite. **These tests should not be treated as verified, passing coverage of the current UI** — treat them as stale/likely-broken until reconciled, per §9.2/§19. `debug-sse.spec.ts` and `debug-sse2.spec.ts` are manual debugging scripts (console-log dumps with a single weak assertion each), not meaningful regression tests regardless of the staleness issue.

**No frontend unit tests** (no Jest/Vitest/React Testing Library configuration or test files) were found anywhere under `dashboard/frontend/`.

### 15.3 SDK testing (full detail: `llms.txt` §10 — not duplicated here)

Summary: six test types (unit/integration/e2e/regression/performance/smoke), hard rules (never touch the network, never call a real model — MockLM is the default gateway everywhere, never `sleep`, never read the wall clock), determinism testing as a first-class category (repeatability, reducer algebraic laws via Hypothesis property-based testing, Temporal replay, serialization stability), a dedicated "base-install" CI job proving the kernel suite passes with only `pydantic` installed, and enforced coverage floors (90% global / 97% `core/` / 99% `models/`, ratcheted up, never down).

### 15.4 Linting / formatting / type-checking / CI checks

**SDK:** `ruff check`/`ruff format --check` (line-length 100, extensive rule set including banned-API rules that forbid importing `backend`/`apps`/`services`/`frontend`), `mypy --strict` (scoped to `src/korchestrator`), `bandit`, `pip-audit`, `gitleaks`, plus three custom architectural gates (`check_isolation.sh`, `check_env_reads.py`, `validate_version.py`) and an `import-linter` contract set (`.importlinter`) mechanically enforcing the layering rules described in §3.1. All of this is CI-blocking (§6.2).

**Dashboard:** none of the above tools are configured to run against `dashboard/` at all (§6.1, §6.5) — no ESLint config was found under `dashboard/frontend/` (no `.eslintrc*`), no `ruff`/`mypy`/`bandit` scope includes `dashboard/backend/`.

### 15.5 How to run every available test suite (commands verified from repo content)

```bash
# SDK — full suite with coverage
pytest tests --cov=korchestrator --cov-report=term-missing

# SDK — base-install kernel suite only
pytest tests/unit/core tests/unit/models tests/smoke

# SDK — one module
pytest tests/unit/core -v

# SDK — Temporal-marked tests (requires [temporal] extra)
pytest tests -m temporal

# SDK — doctest examples in docstrings
pytest --doctest-modules src/korchestrator

# Dashboard backend
cd dashboard/backend && pytest tests/ -v

# Dashboard E2E (targets the AWS ALB by default unless overridden — see §7)
cd dashboard && npx playwright test
DASHBOARD_URL=http://localhost:8080 npx playwright test
```

### 15.6 Results

**Not found / requires verification.** This review did not execute any test suite (no local run of `pytest`, `npm test`, or `playwright test` was performed while compiling this document) — reporting "results" here would misrepresent verified-from-source-code findings as live execution evidence. The CI badges/history on GitHub (`https://github.com/Kendralabs/korch-sdk/actions`) are the authoritative source for actual, current SDK CI pass/fail status; this review did not query that API. The dashboard's test suite has no CI history at all to reference (§6.1).

---

## 16. Complete Deployment Inventory

### 16.1 Environments

| Environment | Server/instance | Container/service | Purpose | URL | Port | Branch | Deployment method | Database | Status |
|---|---|---|---|---|---|---|---|---|---|
| Local dev (bare) | Developer machine | `uvicorn main:app --reload` + `vite dev` | Development | `localhost:8000` (backend), `localhost:5173` (frontend) | 8000, 5173 | any | Manual (`uvicorn`/`npm run dev`) | None (in-memory) | Fully documented, presumed working (not run by this review) |
| Local dev (Compose) | Developer machine | Docker containers `backend`, `frontend` | Development / integration testing | `localhost:8080` (via nginx), `localhost:8000` (direct debug) | 8080→80, 8000→8000 | any | `docker compose up --build` | None (in-memory) | Documented; **would hit the §5.4 Docker defect once containers restart from a fresh image build** if the router files aren't fixed |
| AWS (unnamed, single reviewable shape) | ECS Fargate task (0.5 vCPU / 1GB) | `backend` container | The only cloud deployment target described | ALB DNS (auto-generated, not fixed in repo) + CloudFront for frontend | 8000 (container), ALB/CloudFront handle public ports | Not tied to any specific branch | Fully manual, per `dashboard/aws/README.md` | None (in-memory) | **IaC is "reviewable, not applied" per its own README — yet a specific ALB DNS name appears in `playwright.config.ts`, suggesting a deployment existed at some point; current live status not verified by this review** |
| SDK "deployment" | N/A (no server) | N/A | Artifact publication only | GitHub Releases page | N/A | `main` (tag-triggered) | Automated (`release.yml`) | N/A | Automated and verified against the workflow file's actual logic |

### 16.2 Repositories / services / integrations inventory

| Component | Type | Repo location | CI coverage | Deployment automation |
|---|---|---|---|---|
| `korchestrator` SDK | Python library | `src/korchestrator/` | Full (`ci.yml`, `release.yml`, `docs.yml`) | Automated (tag → GitHub Release) |
| Dashboard backend | FastAPI service | `dashboard/backend/` | **None** | Manual only |
| Dashboard frontend | React SPA | `dashboard/frontend/` | **None** | Manual only |
| Dashboard AWS IaC | JSON (ECS task def, IAM policies) | `dashboard/aws/` | N/A (not code, but also not validated by any CI job, e.g. no `aws cloudformation validate-template`-equivalent check) | Manual (`aws` CLI, per README) |
| OpenAI API | External integration | — | N/A | N/A |
| Anthropic API | External integration | — | N/A | N/A |
| AWS Bedrock | External integration | — | N/A | N/A |
| LangSmith | External integration (optional) | — | N/A | N/A |
| KCG service | External integration (optional) | — | N/A | N/A |

---

## 17. End-to-End Workflows

### 17.1 User opens the dashboard and runs a swarm (fincrime scenario)

See the fully detailed, source-cited version of this workflow in §3.3. Condensed:

1. Browser loads the SPA (served by nginx locally, or S3/CloudFront in AWS).
2. User selects the "Fincrime" tab, enters an objective, clicks Run.
3. Frontend `POST`s to `/api/swarm/fincrime/run`; backend returns a `run_id` immediately and starts the swarm in a background task.
4. Frontend opens an `EventSource` to `/api/swarm/fincrime/stream/{run_id}`.
5. Backend runs 5 investigator agents concurrently (one Pregel superstep), each optionally calling mock KYC/AML tools; results stream live.
6. At superstep 1, execution halts for human sign-off (`_HitlGate` → `GovernanceHaltError` → `RunStatus.GOVERNANCE_PAUSED`).
7. User approves/rejects via a `POST` to `/{run_id}/approve` or `/reject`.
8. On approval, the reconciler agent computes a final (deterministic, non-LLM) risk-graded assessment; a terminal SSE event closes the stream.

### 17.2 User authenticates

**Does not apply** — there is no authentication anywhere in the dashboard (§8).

### 17.3 Deployment workflow (dashboard, to AWS)

See §5.5 for the full, step-by-step manual sequence — build image → push to ECR → create secrets → register task definition → stand up ECS service behind an ALB → build and sync the frontend to S3 → configure CloudFront. **Note again: as currently written, step 1 (image build) produces an image that will crash on container start (§5.4) — this workflow cannot succeed end-to-end without that fix.**

### 17.4 Authentication workflow

**Does not apply** — see §17.2 / §8.

### 17.5 Database migration workflow

**Does not apply — no database exists** (§10).

### 17.6 Failure / recovery workflow

**Local Compose:** `restart: unless-stopped` — Docker restarts a crashed container automatically; since the backend's healthcheck gates the frontend's startup (`depends_on: condition: service_healthy`), a crash-looping backend (e.g., the §5.4 defect) would also prevent the frontend container from ever starting cleanly the first time, though on a Compose `up` where the frontend already started once, it wouldn't automatically stop just because the backend later crashes.

**AWS ECS:** implicit AWS Fargate behavior — a task failing its health check is stopped and (if the service's desired count isn't met) replaced by the ECS service scheduler. No custom failure-recovery logic (retries, backoff, circuit breakers) is defined anywhere for the dashboard beyond this default orchestrator behavior. **The SDK itself**, by contrast, has an extensively documented determinism/durability/retry model (Temporal checkpointing, exponential backoff with jitter, non-retryable error classification) — but none of that applies to the dashboard's *own* process-level failure handling, only to swarm-run-level retries *within* a successfully-running backend process.

---

## 18. How to Reproduce the Entire System

Every step below is drawn directly from files in this repository (cited); none are guessed.

```bash
# 1. Clone
git clone git@github.com:Kendralabs/korch-sdk.git && cd korch-sdk
# (private repo — requires a GitHub credential with read access)

# 2. Install the SDK (editable, every extra) — required before the dashboard backend can import it
pip install -e '.[dev]'

# 3. Verify the SDK installed correctly
python -c "import korchestrator; print(korchestrator.__version__)"   # expect: 0.1.0
python examples/01_one_liner.py                                       # offline smoke test

# 4. Configure dashboard backend environment variables
cd dashboard/backend
pip install -r requirements.txt
Copy-Item .env.example .env         # Windows PowerShell; use `cp .env.example .env` on macOS/Linux
# Edit .env: set at least one of OPENAI_API_KEY / ANTHROPIC_API_KEY /
# (AWS_BEARER_TOKEN_BEDROCK + AWS_DEFAULT_REGION) for real LLM behavior.
# No database setup is needed — there is no database (§10).

# 5. Run the dashboard backend
python -m uvicorn main:app --reload --port 8000
# In a second terminal, verify:
curl http://localhost:8000/api/config

# 6. Configure and run the dashboard frontend (third terminal)
cd ../frontend
npm install
npm run dev
# Open http://localhost:5173 (see §4.5 for a port-numbering caveat between docs and vite.config.ts)

# 7. Run tests
#   SDK:
cd ../..
pytest tests --cov=korchestrator --cov-report=term-missing
#   Dashboard backend:
cd dashboard/backend && pytest tests/ -v
#   Dashboard E2E (point at your local stack, not the default AWS ALB):
cd .. && DASHBOARD_URL=http://localhost:8080 npx playwright test
#   (NOTE per §15.2: these E2E specs are verified stale against the current frontend UI and are
#   expected to fail regardless of environment, until reconciled with the current component tree.)

# 8. Build
python -m build                                    # SDK wheel + sdist
cd dashboard/frontend && npm run build              # frontend static assets → dist/

# 9. Local full-stack via Docker (alternative to steps 5-6)
cd ../..    # repo root
# create dashboard/backend/.env first (step 4)
docker compose -f dashboard/docker-compose.yml up --build
# NOTE per §5.4: as currently written, the backend image build will succeed, but the container
# will crash at startup with an ImportError, because the Dockerfile does not COPY
# support_escalation_router.py / fincrime_router.py / fincrime_data.py / researcher_router.py /
# tracing.py / kcg_tracing.py into the image, even though main.py imports all of them. This must
# be fixed (add those files to the Dockerfile's COPY instruction) before this step will work.

# 10. Deploy to "staging" — NOT APPLICABLE / NOT FOUND
# No distinct staging environment, workflow, or script exists for the dashboard (§4.4, §5.2).
# The SDK's `staging` git branch is a code-promotion stage, not a deployed environment.

# 11. Deploy to "production" — manual, AWS, per dashboard/aws/README.md
aws ecr create-repository --repository-name korchestrator-dashboard-backend
docker build -f dashboard/backend/Dockerfile \
  -t <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/korchestrator-dashboard-backend:<TAG> .
  # ^ fix the Dockerfile's COPY list first (§5.4) or this image will not run
aws ecr get-login-password --region <REGION> | docker login --username AWS \
  --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/korchestrator-dashboard-backend:<TAG>
aws secretsmanager create-secret --name korchestrator-dashboard/bedrock-bearer-token \
  --secret-string "$AWS_BEARER_TOKEN_BEDROCK"
aws secretsmanager create-secret --name korchestrator-dashboard/openai-api-key \
  --secret-string "$OPENAI_API_KEY"
aws secretsmanager create-secret --name korchestrator-dashboard/anthropic-api-key \
  --secret-string "$ANTHROPIC_API_KEY"
# create IAM roles from dashboard/aws/iam-execution-role-policy.json and iam-task-role-policy.json
aws logs create-log-group --log-group-name /ecs/korchestrator-dashboard-backend
aws ecs register-task-definition --cli-input-json file://dashboard/aws/ecs-task-definition.json
# manually create the ECS Fargate service behind an ALB (health check /api/config, port 8000,
# idle timeout >= 3600s)
docker build -f dashboard/frontend/Dockerfile --build-arg VITE_API_BASE="" \
  -t dashboard-frontend-build ./dashboard/frontend
aws s3 sync dashboard/frontend/dist s3://<YOUR_FRONTEND_BUCKET> --delete
# manually configure CloudFront: default origin -> S3 bucket, /api/* origin -> the ALB
```

Sources for every step: `README.md`, `dashboard/README.md`, `dashboard/docker-compose.yml`, `dashboard/backend/Dockerfile`, `dashboard/frontend/Dockerfile`, `dashboard/aws/README.md`, `dashboard/aws/ecs-task-definition.json`, `pyproject.toml`, this document's own §5.4/§15.2 verified findings.

---

## 19. Current Implementation vs Missing/Recommended Work

### 19.1 Implemented and verified

- The `korchestrator` SDK: 26-module architecture, ARI ports, Pregel BSP kernel, local + Temporal runtimes, exception hierarchy (16 error types), public API surface (31 exported names) — all verified byte-for-byte against `src/korchestrator/__init__.py`/`version.py`/`exceptions/`/`services/` (§20, item SDK-1).
- Dashboard backend: 4 FastAPI routers, 11+ distinct HTTP endpoints, 3 SSE streaming mechanisms, multi-provider LLM gateway (OpenAI/Anthropic/Bedrock via litellm+boto3), 2 optional real tracing integrations (LangSmith, KCG), a working (locally, per its own tests) HITL approve/reject flow using a genuine SDK-level `GovernanceHaltError` mechanism added specifically for this purpose.
- Dashboard frontend: 3 working demo UIs (researcher, support-escalation, fincrime/investigation-console), SSE consumption via native `EventSource`, a full custom dark-theme design system.
- CI: comprehensive, blocking, multi-job pipeline for the SDK only (lint/type/test/security/build/docs/base-install-purity), a PyPI + GitHub Releases release pipeline, GitHub Pages docs deploy.
- Git hygiene: `.env` correctly gitignored and confirmed not tracked; no compiled artifacts committed under `dashboard/`.

### 19.2 Partially implemented

- **HITL/governance**: works via a local, in-process mock (`LocalHITLMiddleware`/`_HitlGate`) — the durable, Temporal-backed version described in `dashboard_spec.md` §4.4 does not exist; the SDK's Temporal runtime does not yet drive the `before_superstep`/`after_superstep` hooks the dashboard needs for a real durable HITL pause/resume (explicitly documented in `dashboard/README.md` and `dashboard/aws/README.md`).
- **SDK telemetry**: only the outer `agent.run` span and 2 of 6 documented metrics are actually wired to fire; the rest are defined but unconnected (self-documented in `.claude/memory/PROJECT_STATE.md`'s known-gaps section).
- **`LiteLLMGateway.available_models()`**: returns a fixed catalog rather than one conditioned on which credentials are actually configured, as the original design spec called for.

### 19.3 Configured but not verified (as running/operational)

- The single AWS deployment shape in `dashboard/aws/` — its own README states it has never been applied, yet a specific, real-looking ALB DNS name appears as the default in `dashboard/playwright.config.ts`. Whether this environment currently exists, is healthy, or is stale is **not determinable from repository contents alone.**
- Dashboard `.env.example` files' exact contents (permission-denied to this review's tooling).
- CloudWatch log retention policy, ECS service `desiredCount`/autoscaling configuration, VPC/security-group configuration for the AWS shape — none appear in the reviewed files.

### 19.4 Missing

- **Authentication/authorization anywhere in the dashboard** (§8, §9.2) — the single most significant gap given the AWS shape describes internet-facing infrastructure.
- **A database** — despite being part of the dashboard's own original architecture diagram (§10).
- **CI coverage for the dashboard** — zero lint/type/test/security automation for `dashboard/` (§6.1).
- **A correct Docker build for the dashboard backend** — verified missing `COPY` entries for 6 files the running app requires (§5.4).
- **Any deployment automation for the dashboard** — entirely manual, no CD pipeline (§5, §6.9).
- **Error tracking, alerting, dashboards/CloudWatch alarms** (§14.3, §14.6).
- **Rate limiting** on any dashboard endpoint.
- **A `USER` directive / non-root container hardening** in the backend Dockerfile.
- **A reconciled, current Playwright E2E suite** — the existing one targets a UI generation ago.
- **The "⚙ Config modal"** for client-side LLM-key entry described in `dashboard/README.md` — not present in current frontend source.
- **The "Architect auto-plan"/"Swarm designer" (drag-and-drop) UI** described in `dashboard_spec.md` — superseded by the current 3-tab investigation-console UI; the underlying `main.py` scenario1-4 backend code still exists but nothing in the frontend calls it.

### 19.5 Recommended improvements

Listed in priority order given the findings above:

1. Fix the backend Dockerfile's `COPY` instruction (add the 6 missing files) — nothing else about the AWS deployment path can be validated until the image can actually start.
2. Add authentication (even a simple shared bearer token) before any internet-facing deployment of the dashboard.
3. Add a dashboard-scoped CI job (ruff/mypy for the backend if desired, ESLint/`tsc` for the frontend, `pytest dashboard/backend/tests`, and a Docker build+smoke-start check that would have caught #1 automatically).
4. Reconcile or remove the stale Playwright E2E suite.
5. Decide and document: is the `main.py` scenario1-4 code path (Architect/Swarm-designer/tools/HITL, matching the original spec) still intended to ship, or should it — and its now-orphaned frontend concept — be formally retired? Currently it's neither removed nor reachable from the UI.
6. Reconsider whether `dashboard/` belongs in this repository at all, given the SDK's own explicit, repeatedly-stated golden rule against shipping any frontend/backend/service from this repository (§19.6 below) — or, if the decision is to keep it, update `.claude/CLAUDE.md`/`docs/specs/01-scope-and-principles.md` to formally carve out an explicit, documented exception rather than leaving the contradiction implicit.
7. Add dependency-update automation (Dependabot/Renovate) for `dashboard/backend/requirements.txt`, which currently has no upper version bounds and no automated vulnerability scanning.
8. Add basic operational tooling for the dashboard: error tracking, at least one CloudWatch alarm (e.g., on ECS task restart count), and a documented rollback procedure.

### 19.6 Potential technical/security risks — consolidated

| Risk | Severity (qualitative) | Where documented in this report |
|---|---|---|
| Unauthenticated, potentially internet-facing service that can trigger real LLM spend and overwrite shared credentials | High | §8.1, §9.2 |
| Docker image that crashes on start, blocking any real deployment attempt from succeeding as documented | High (blocks deployment; not a live-system risk until someone tries to deploy) | §5.4 |
| No automated testing/security scanning for a real, deployable web application component of this repository | Medium-High | §6.1, §15.4 |
| Repository's own stated single-product architectural rule is contradicted by a real, committed, deployable second product | Medium (governance/process risk, not a direct technical vulnerability) | This document's opening note, §19.5 item 6 |
| No rate limiting, no error tracking, no alerting for a service that spends real money per request | Medium | §9.2, §14.3, §14.6 |
| Known, unresolved SDK-level hang bug on a governance-critical code path (HITL reject) | Medium | §9.2, §13.4, §15.1 |
| Stale test suite creating false confidence in frontend coverage | Low-Medium | §15.2 |

---

## 20. Source References

This section indexes the primary files this document's claims were verified against, organized by topic. Every specific factual claim in §1–§19 additionally carries its own inline file citation at the point it's made; this index is a convenience map, not a substitute for those inline citations.

**Product overview / architecture:** `README.md`, `dashboard/README.md`, `dashboard_spec.md`, `docs/specs/00-overview.md`, `docs/specs/03-architecture.md`, `llms.txt` (repo root).

**Repository structure:** `docs/specs/02-repository-structure.md`, direct directory listings of the repository root and `dashboard/`.

**SDK source verification (item "SDK-1" referenced above):** `src/korchestrator/__init__.py`, `src/korchestrator/version.py`, `src/korchestrator/exceptions/errors.py`, `src/korchestrator/services/korch.py`, `swarm.py`, `agent.py`, `pyproject.toml`, `CHANGELOG.md`, `.claude/memory/PROJECT_STATE.md`, `.claude/memory/ENGINEERING_LOG.md`, `docs/releases.md`.

**Dashboard backend:** `dashboard/backend/main.py`, `gateway.py`, `tracing.py`, `kcg_tracing.py`, `fincrime_router.py`, `fincrime_data.py`, `researcher_router.py`, `support_escalation_router.py`, `requirements.txt`, `Dockerfile`, `tests/*.py`.

**Dashboard frontend:** `dashboard/frontend/src/*.tsx`, `package.json`, `Dockerfile`, `nginx.conf.template`, `vite-env.d.ts`, `dashboard/e2e/*.spec.ts`, `dashboard/playwright.config.ts`.

**Infrastructure/deployment:** `dashboard/docker-compose.yml`, `dashboard/aws/README.md`, `ecs-task-definition.json`, `iam-execution-role-policy.json`, `iam-task-role-policy.json`, `.dockerignore` (root and `dashboard/frontend/`).

**CI/CD:** `.github/workflows/ci.yml`, `release.yml`, `docs.yml`, `.pre-commit-config.yaml`, `.claude/hooks/pre-commit-check.sh`, `.importlinter`, `scripts/*.py`, `scripts/*.sh`.

**Security/config:** `SECURITY.md`, `.gitignore`, `dashboard/backend/.env.example` / `dashboard/frontend/.env.example` (existence confirmed, contents not readable by this review's tooling — see §12.3), `pyproject.toml` (`[tool.bandit]`, `[tool.ruff]` banned-api section).

**Git state:** `git remote -v`, `git branch -a`, `git tag -l`, `git ls-files`, `git log` — run directly by this review against the local clone at `d:\GitHub\Fintricity\korch-sdk`.

---

*This document was compiled by reading the repository's actual source code, configuration, and committed documentation. No values from any `.env` file, secret, credential, or private key were read or are reproduced here. Where a claim could not be verified from repository contents, it is explicitly marked "Not found / requires verification" rather than assumed. Given the size of the surface reviewed, treat this as a strong starting map rather than an infallible one — spot-check anything decision-critical against the cited file directly before acting on it.*
