
# Engineering Log — Korchestrator SDK

The project's chronological record. **Append a new entry (newest at top) whenever a
feature/fix/refactor/architectural change is completed — BEFORE committing** (CLAUDE.md §8). Each
entry is self-contained: a reader should understand the change without the git diff. The blank
template is at the bottom of this file.

---

<!-- ⬇️ NEW ENTRIES GO HERE (newest first) ⬇️ -->

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
