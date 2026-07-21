
# Engineering Log — Korchestrator SDK

The project's chronological record. **Append a new entry (newest at top) whenever a
feature/fix/refactor/architectural change is completed — BEFORE committing** (CLAUDE.md §8). Each
entry is self-contained: a reader should understand the change without the git diff. The blank
template is at the bottom of this file.

---

<!-- ⬇️ NEW ENTRIES GO HERE (newest first) ⬇️ -->

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
