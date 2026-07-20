
# Engineering Log — Korchestrator SDK

The project's chronological record. **Append a new entry (newest at top) whenever a
feature/fix/refactor/architectural change is completed — BEFORE committing** (CLAUDE.md §8). Each
entry is self-contained: a reader should understand the change without the git diff. The blank
template is at the bottom of this file.

---

<!-- ⬇️ NEW ENTRIES GO HERE (newest first) ⬇️ -->

## 2026-01-XX · [P0] Repository scaffold, scope freeze & quality net — v0.1.0

**Type:** foundation · **Phase:** P0 · **Author:** <name/agent>

**What.** Stood up the self-contained `korch-sdk` repository: `src/korchestrator/` layout with stub
modules and explicit `__all__`; authoritative `pyproject.toml` (`requires-python >=3.10`, core dep
`pydantic` only, extras stubbed); `version.py` (`0.1.0`); `py.typed`; the CI workflows; the
pre-commit hook; and this engineering log.

**Why.** Everything downstream depends on a self-contained, single-versioned, quality-gated
foundation. Settling naming/version/license/extras and installing the isolation gate now prevents
drift later.

**Design decisions.** Single authoritative version in `version.py` (all else derives); `src/`
layout so imports resolve from the install; core depends only on `pydantic`, everything heavy is an
optional extra; remote auth scheme + method vocabulary + license settled (see `docs/adr/`).

**Architecture changes.** Initial layout established; boundaries defined (see CLAUDE.md §3).

**Files/modules affected.** `pyproject.toml`, `src/korchestrator/**` (stubs), `.github/workflows/**`,
`.claude/**`, `docs/specs/**`, `docs/adr/0001–0008`.

**Breaking changes.** None (initial commit).

**Feature version / revision.** `0.1.0` (pre-release; 0.x MINOR may break per policy).

**Migration notes.** N/A.

**Testing status.** `import korchestrator` works; CI green incl. isolation gate + version-validate;
no behavior tests yet (kernel lands in P2).

**Known limitations / future improvements.** All modules are stubs; the public façade has type
signatures only (frozen in P1); no runtime behavior until P2.

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
