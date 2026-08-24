# Project State — Korchestrator SDK

**What this file is.** The answer to "where is this project right now", in one read. The engineering
log is chronological history; this file is the current snapshot. Update it whenever a phase advances,
a module changes status, or the public surface moves — `/log` does both together.

**Last updated:** 2026-08-24 · **Version:** `0.1.0` (released — GitHub Release published 2026-08-12, verified) · **Branch model:** `dev` → `staging` → `main`

---

## 1. Current position

| | |
|---|---|
| **Active phase** | **P12 — CI/CD, packaging & publishing — complete.** The private-distribution pipeline (P12.1–P12.7, narrowed by [ADR 0020](../../docs/adr/0020-private-distribution-defers-pypi-publishing.md)) shipped and `v0.1.0` is tagged and published as a private [GitHub Release](https://github.com/Kendralabs/korch-sdk/releases/tag/v0.1.0) (published 2026-08-12T08:43:24Z, not a draft/prerelease, wheel+sdist+SHA256SUMS attached — verified via `gh release view v0.1.0` on 2026-08-24). All numbered phases (P0–P12) are complete; P13 (external backend adapter) is out of scope. Remaining work is beta-readiness hardening, not a numbered phase — see `docs/status/beta-release-checklist.md` (not committed; a local tracking doc). |
| **Last completed milestone** | **P12.7 — Release automation script**, followed by the actual `v0.1.0` cut and tag. `.github/workflows/release.yml` checksums the built artifact and publishes a GitHub Release (wheel, sdist, `SHA256SUMS`, CHANGELOG-derived notes) on every `vX.Y.Z` tag, plus an in-pipeline `verify-private-install` job — confirmed it ran successfully for `v0.1.0` (release author: `github-actions[bot]`). `scripts/cut_release.py` (`prepare`/`tag`) automates the release runbook (spec 10 §9), unit tested at `tests/unit/test_cut_release.py`. PyPI Trusted Publishing, SBOM generation, and provenance attestation remain deferred, not implemented — see ADR 0020. |
| **Blocking** | Nothing in the SDK repository itself. `pytest -m temporal` / the Temporal e2e suite still cannot run in this dev environment (pre-existing `beartype`/site-packages conflict, unrelated to any prior-phase work — see the P7.4 engineering-log entry, reproduced again on 2026-08-24; documented as a reader-facing `docs/troubleshooting.md` entry). Separately, outside this repo: the public documentation site has no working public URL yet — `koe.kendralabs.com/docs/` is deployed and internally verified on the VPS but not publicly reachable (ports 80/443 held by another container; the old `:5888` link no longer resolves through Cloudflare) — see `DOCS_DEPLOYMENT.md` "Cutting over from port 5888". This blocks a public beta announcement, not the SDK itself. |
| **Pushed / merged** | All work through P11 (plus the dashboard app) is consolidated and pushed. On 2026-08-12 the repository moved to a `dev` → `staging` → `main` model: the former `develop` and every phase branch were merged, verified fully contained, and deleted; `dev`, `staging` and `main` now all sit at the same commit. This P12 release-pipeline work lands on `feat/p12-private-release-pipeline` off `dev`, per the normal flow, ahead of the separate minimal `chore/release-v0.1.0` PR that actually cuts the tag. |

Every local gate is green except the pre-existing `[temporal]` environment issue above: ruff,
ruff-format, `mypy --strict` (105 source files, clean), doctest examples (99 passed), `pytest`
(dspy + non-dspy paths, `-m "not temporal"`; **836 passed, 0 failed** as re-verified on 2026-08-24,
96.92% cov, comfortably above the 90% floor — `core`/`models` individually above their 97%/99%
floors), import-linter (**4 contracts kept**, incl. the ADR-0011 httpx confinement), the isolation
gate, env-confinement, and version single-sourcing. `python -m build` + `scripts/smoke_install.sh`
both pass (base install pulls in only `pydantic`, `import korchestrator` reports `0.1.0` from a
throwaway venv outside the source tree). `mkdocs build --strict` passes with no broken links
(two pages — `docs/parity-matrix.md`, `docs/competitive-analysis.md` — build fine but aren't
reachable from the site nav; not a broken-link failure, worth fixing in the docs pass). All 8
`examples/*.py` scripts run to completion offline (MockLM). `import korchestrator.agents`/
`korchestrator.routing`/`korchestrator.telemetry` stay `dspy`/`[routing]`/`[otel]`-free; the base
install stays `pydantic`-only, and `korchestrator.clients`/`korchestrator.remote` are never
imported by `korchestrator/__init__.py` (statically checked, `test_remote.py`).

**2026-08-24 verification note:** this pass's local `pytest` run required `-p no:hypothesispytest`
to avoid a `MemoryError` during collection — a `hypothesis` 6.158.0 bug (its
`is_local_module_file` check only recognizes `site.getsitepackages()`, not
`site.getusersitepackages()`; on this machine every third-party package, including `torch` and
`transformers`, installs to the user site-packages and gets misclassified as "local source",
so hypothesis tries to AST-parse and cache constants from all of them at collection time). This is
an environment/tooling issue tied to this machine's package layout, not a korchestrator defect —
CI's Linux runners install into a venv and are very unlikely to hit it, but worth a quick check
next time CI runs if the same `MemoryError` ever shows up there.

## 2. Phase progress

| Phase | Title | Status |
|---|---|---|
| P0 | Foundations, scope freeze, scaffolding | **Complete** (branch `chore/p0-foundations`) |
| P1 | Public API & interface contracts | **Complete** (branch `feat/p1-contracts`) |
| P2 | Core execution kernel (Pregel) | **Complete** (merged to `develop`) |
| P3 | Runtime adapters (local + Temporal) | **Complete** (merged to `develop`) |
| P4 | Cognitive layer (agents, signatures, taxonomy) | **Complete** (P4.1–P4.9; first end-to-end run) |
| P5 | Model routing | **Complete** (P5.1–P5.6; routing wired into execution) |
| P6 | Integration & observability (AUB, MCP, A2A, streaming, context) | **Complete** (P6.1–P6.8; hooks wired into the local runtime) |
| P7 | Governance, security & context graph | **Complete** (P7.1–P7.6; merged to `develop`) |
| P8 | Cross-cutting foundations | **Complete** (P8.1–P8.7; merged to `develop`) |
| P9 | Remote client (Python only — TS deferred) | **Complete** (P9.1–P9.8; merged to `develop`) |
| P10 | Testing, benchmarks & quality gates | **Complete** (P10.1–P10.6) |
| P11 | Documentation, examples & DX | **Complete** (P11.1–P11.6) |
| P12 | CI/CD, packaging & publishing | Private-distribution pipeline shipped (P12.1–P12.7); tagging `v0.1.0` next |
| P13 | External backend adapter | **Out of scope** — separate repository |

## 3. Module status

Every module is **not created**. Populate this table as modules land: `not created` → `stub` →
`implemented` → `tested` → `documented`.

| Module | Layer | Status | Phase |
|---|---|---|---|
| `config/` | Leaf utility | **tested** (full spec 08 §1.3 `Settings` — 28 fields incl. `SecretStr`; opt-in `.env`; `configure`/`get_settings`) | P0, P8.1 |
| `constants/` · `exceptions/` | Leaf utility | **tested** (`KorchError` tree + error codes, frozen) | P1 |
| `types/` · `models/` | Contract | **tested** (`JSONValue` + frozen domain models, frozen) | P1 |
| `interfaces/` | Contract | **tested** (ARI ports + supporting protocols, frozen; `IToolInvoker` added P10.2) | P1 |
| `services/` | Façade | **tested** (`Korch.run`/`Swarm.run` wired to the kernel via `_composition`; first end-to-end run) | P1, P4 |
| `core/` | Kernel (L1) | **tested** (reducers + laws, AgentGraph, ChannelSchema, PregelRunner; determinism-locked; ≥97% cov; message log now carries every `Message.kind`, not just `answer` — P10.2) | P2 |
| `runtime/` | Adapter | **tested** (LocalRuntime + resolve_runtime; TemporalRuntime PregelMaster/SuperstepActivity, retry/rollover, HITL signals; equivalence/replay/crash/rollover verified) | P3 |
| `providers/` | Adapter | **tested** (MockLM; local identity + subprocess sandbox; OpenAI gateway + `get_lm`; 99% cov) | P4 |
| `agents/` | Cognitive (L2) | **tested** (unified `Agent`; lazy DSPy `Signature`s; `WorkerAgent` + `ArchitectAgent` over a shared gateway bridge; `WorkerAgent` now runs a real bounded ReAct tool-calling loop when `tools` is mounted, via the injected `IToolInvoker` — P10.2, ADR 0018, closes a P4.6 gap; 97% cov) | P4 |
| `taxonomy/` | Cognitive (L2) | **tested** (`TaxonomyClassifier` + agent descriptors; 100% cov) | P4 |
| `routing/` | Cognitive (L2) | **tested** (explicit+fallback default, algorithmic, semantic `[routing]`, composite, user-function behind one `BaseRouter`; `get_router`/`resolve_router`; model-card catalogue; wired into execution) | P5 |
| `tools/` | Integration (L4) | **tested** (AUB `invoke_tool` + `ConnectorRegistry` + `Connector` contract; schema/timeout/rate-limit/access gate/redaction seam; filesystem + mock-search connectors; ADR 0015; `RegistryToolInvoker` — the `IToolInvoker` implementation `agents/` calls through, P10.2/ADR 0018) | P6 |
| `mcp/` | Integration (L4) | **tested** (`MCPClient.discover` → `Connector`s; stdio/sse descriptor; fake-session testable; real transport `[mcp]`) | P6 |
| `context/` | Context (L3) | **tested** (`ContextCompiler` MVC extraction, off the hot loop, graceful summariser degradation) | P6 |
| `a2a/` | Integration (L4) | **tested** (`directed_message`, `HandoffTransformer`) | P6 |
| `events/` | Events | **tested** (`EventPublisher`/`Subscription`/`format_sse`; emits, does not serve HTTP) | P6 |
| `governance/` | Governance (L5) | **tested** (`ControlTowerTelemetry`/`check_governance` — trust score read; `evaluate_policy`/`GovernanceDecision`/`AuditLog` — policy + audit, P7.3) | P7 |
| `security/` | Leaf utility | **tested** (Shield redactor, P7.1) | P7 |
| `persistence/` | Context (L3) | **tested** (`InMemoryGraphRepository` + `resolve_repository`, wired into `Korch`/`Swarm` via `_PersistenceMiddleware`; `ContextGraphClient` — bitemporal `DecisionNode`/`EventNode`, Shield-redacted, tenant-scoped, time-travel query, P7.6) | P7 |
| `logging/` | Leaf utility | **tested** (namespaced logger, `NullHandler` by default, `enable_logging`/`disable_logging`, P8.3) | P8.3 |
| `serializers/` | Leaf utility | **tested** (`to_json`/`from_json` — `AgentState`/`ExecutionPlan`/`ModelCard`/`RunResult`, version-tagged, migration mechanism; `AgentGraph` excluded, ADR 0017) | P8.5 |
| `validators/` | Leaf utility | **tested** (`validate_objective`/`validate_max_supersteps`/`validate_unique_agent_id`, wired into `Korch`/`Swarm`) | P8.6 |
| `telemetry/` | Leaf utility | **tested** (`start_span`/`record_metric`, zero-overhead no-op off, lazy `[otel]`; `agent.run` span + `korch.run.duration`/`korch.run.status` wired into `_composition.run_graph`; rest of the span tree/metrics not yet wired — see known gaps) | P8.7 |
| `clients/` | Client | **tested** (`KorchestratorClient`: Bearer auth transport, retry/backoff, `ApiError`, credential-safe `repr`, full run lifecycle, control, identity, key management, discovery, SSE `stream()` — the whole method surface, contract-conformance tested; re-exported as `korchestrator.remote`) | P9.1–P9.7 |

## 4. Public surface

**Currently exported:** 31 names — `Agent`, `AgentState`, `Korch`, `Swarm`, `configure` (P8.1),
`enable_logging` (P8.3), `from_json`/`to_json` (P8.5), the 4 ARI ports
(`IDurableRuntime`/`IExecutionSandbox`/`IIdentityProvider`/`IModelGateway`), the 13 top-level
`KorchError` subclasses, `Message`/`RunResult`/`RunStatus`/`StateUpdate`, `Settings`, and
`__version__`. Full list in `tests/unit/public_surface.json`. Frozen at P1 with 27 names; all four
P8 additions are deliberate, ADR-considered (ADR 0016).

**P8 additions are now complete** (`configure`, `enable_logging`, `from_json`, `to_json` — the
four names anticipated since P1). `korchestrator.exceptions.TimeoutError` and `ConfigurationError`,
`korchestrator.logging.disable_logging`, and `korchestrator.telemetry.{is_enabled,start_span,
record_metric}` (P8.7) are all part of the compatibility surface but intentionally not top-level —
matches spec 04 §6's `__init__.py` example exactly, which lists none of them.

The surface is guarded by the golden-file snapshot test (`tests/unit/test_public_surface.py`).
Changing it is a deliberate act requiring a CHANGELOG entry and a version decision in the same PR.

**`korchestrator.remote` (Phase 9, complete) is a separate, optional import path — not part of
`korchestrator.__all__`, never imported by `korchestrator/__init__.py`.** It exports
`KorchestratorClient` (20 methods: full run lifecycle, control, identity, key management,
discovery, SSE streaming) plus its own `ApiError` and nine `models.remote` types. `docs/parity-
matrix.md` (P9.8) settles its TypeScript equivalent per ADR 0008, marked `TS: planned` throughout
— no TypeScript client exists in this repository.

## 5. Settled decisions

All recorded in [`docs/adr/`](../../docs/adr/README.md) and binding.

| Decision | Outcome | ADR |
|---|---|---|
| Package / client naming | `korchestrator`; `korchestrator.remote`; `KorchestratorClient`; `run`/`run_swarm`/`run_and_wait` | 0001 |
| Version source | `src/korchestrator/version.py`, single literal, starts `0.1.0` | 0002 |
| License | Apache-2.0 | 0003 |
| Dependencies | `pydantic` only in core; extras `dspy`/`temporal`/`routing`/`mcp`/`remote`/`otel`/`all`/`dev` | 0004 |
| Remote auth | `Authorization: Bearer <api-key \| KIAM JWT>`, one scheme | 0005 |
| Runtime | Local + Temporal behind `IDurableRuntime`; one activity per superstep | 0006 |
| Backend boundary | One-way; the SDK never depends on a service | 0007 |
| TypeScript client | Specified, **deferred** — not built in P0–P12 | 0008 |
| Settings dependency | `Settings` on `pydantic.BaseModel`, env read in `config/` — keeps base pydantic-only (not `pydantic-settings`) | 0009 |
| `IDurableRuntime` shape | `now`/`start`/`wait`/`signal`; graph injected at construction | 0010 |
| `httpx` confinement | Owned by `clients/` + `providers/gateway_openai.py` (lazy, `[remote]`); machine-enforced (direct-import) | 0011 |
| Unified `Agent` | One class — declarative **and** subclassable; re-exported from `agents`/`services`/top level | 0012 |
| Cognitive layer needs `[dspy]` | One reasoning path (DSPy `WorkerAgent`); base install imports clean, `MissingExtraError` on run; target dspy 3.x (`dspy>=2.6,<4`) | 0013 |
| Custom router registration | By injection (`Korch(router=)`/`resolve_router`); `ROUTING_STRATEGY` selects built-ins only; entry-point discovery deferred | 0014 |
| Tool/connector registration | On a `ConnectorRegistry` + `Korch(connectors=)` + entry points; no process-global `register_*` (B8) | 0015 |
| Settings finalization | No `pydantic-settings` (hand-written `.env` reader instead); `configure()` wraps into `korchestrator.ValidationError`, `ConfigurationError` covers resolution failures and stays submodule-only | 0016 |
| `AgentGraph` serialization | Excluded from `to_json`/`from_json` — live compute callables have no safe JSON representation | 0017 |

## 6. Known gaps and open items

| Item | Detail | Owner / when |
|---|---|---|
| Compliance checks named in ADRs | `version-validate`, the isolation gate, and env-confinement now **exist and pass** (`scripts/`). The import-purity subprocess test (ADR 0004) and the event-history shape test are still owed by P2/P3. | P2, P3, P9 |
| Coverage floor enforced | Global 80% is wired (`fail_under=80`) and green (100% at this size); `core/`+`models/` 95% checked in CI. Ratchet from P2 as behaviour lands. | P2+ |
| `import-linter` contracts configured | `.importlinter` with 3 contracts (framework-free, layers, feature-independence); `lint-imports` reports 3 kept, 0 broken. `include_external_packages=True` added (import-linter requirement, omitted from spec §9 snippet). | ✔ P0 |
| Manifest corrections during P0 | `--xfail-strict` → `xfail_strict=true` (spec named a nonexistent pytest flag); `import-linter` added to `[dev]`. Both recorded in the engineering log. | ✔ P0 |
| ~~`ConfigurationError` vs `ValidationError` overlap~~ | **Resolved by ADR 0016 (P8.1).** `ValidationError` = structural (wraps pydantic, what `configure()` raises); `ConfigurationError` = resolution/support failures, stays submodule-only. | ✔ P8.1 |
| `ToolError` default code is specific | `ToolError.default_code = TOOL_NOT_FOUND` — a raiser that omits `code=` gets a misleading "not found". No raiser exists until the tool bridge (P6); revisit then (generic default or required `code`). Raised by the P1 API review. | P6 |
| ~~Benchmark baseline not established~~ | **Resolved P10.5.** `benchmarks/baseline.json` committed: `bench_superstep`/`bench_import`/`bench_memory`/`bench_serde` (spec 09 §8) plus `bench_telemetry_overhead` (the telemetry-on/off delta spec 08 §4 requires — the one benchmark that hard-asserts, per that spec's explicit "MUST... assert"). | ✔ P10.5 |
| Telemetry span tree / metrics only partially wired | `telemetry/` (P8.7) built and tested `start_span`/`record_metric`; only the outer `agent.run` span + `korch.run.duration`/`korch.run.status` are actually called (from `_composition.run_graph`). `agent.superstep`/`agent.plan`/`tool.call`/`gen_ai.call` and `korch.superstep.duration`/`korch.agents.active`/`korch.tool.calls`/`korch.model.tokens` are defined but unwired — needs threading through `core/`, `agents/`, `tools/bridge.py`, `providers/`. | Follow-up (no phase assigned) |
| TS parity matrix | Ships as documentation in P9 with every method marked `TS: planned`. | P9 |
| Backlog capabilities deliberately unbuilt | Context Graph external backends, speculative execution, FinOps quotas, KL DSL. Interface-now/implement-minimally; revisit post-1.0 only with real demand. | Post-1.0 |

## 7. Where things live

| What | Where |
|---|---|
| Authoritative design | `docs/specs/` (00–12) — on conflict, the specs win over `.claude/CLAUDE.md` |
| Decisions | `docs/adr/` |
| History | `.claude/memory/ENGINEERING_LOG.md` |
| Current state | this file |
| Agent rules | `.claude/rules/` |
| Commands | `.claude/commands/` — `/phase`, `/verify`, `/log`, `/adr` |
| Subagents | `.claude/agents/` — `boundary-auditor`, `api-reviewer` |
| Skills | `.claude/skills/add-module/` |
| Source inputs (superseded) | `docs/background/` — provenance only, do not build from |
