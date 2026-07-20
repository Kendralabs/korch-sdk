---
description: Write the engineering-log entry for completed work (required before commit)
allowed-tools: Bash, Read, Edit, Grep, Glob
---

Add an entry to `.claude/memory/ENGINEERING_LOG.md` for the work just completed, then refresh
`.claude/memory/PROJECT_STATE.md`.

## 1. Gather the facts — do not guess

```bash
git status --short
git diff --cached --stat
git diff --stat
git log --oneline -5
```

Read the actual diff. The entry must describe what the code does, not what the task intended.

## 2. Write the entry

Newest at the top, immediately under the `NEW ENTRIES GO HERE` marker. Use the template at the
bottom of the log. All ten fields — write `N/A` only where a field genuinely does not apply:

1. **What** was implemented — concretely
2. **Why** — the requirement it satisfies
3. **Design decisions** — what you chose and what you rejected
4. **Architecture changes** — layers, boundaries, ports touched
5. **Files/modules affected**
6. **Breaking changes** — and if yes, the migration note and major-bump plan
7. **Feature version / revision**
8. **Migration notes**
9. **Testing status** — what ran, what passed, what was skipped and why
10. **Known limitations / future improvements**

## 3. Quality bar

- Self-contained: a reader understands the change **without the diff**.
- Honest: if tests were skipped, coverage dropped, or something is half-done, the entry says so.
  A log that only records successes is worse than no log.
- Specific: name modules, functions, and decisions — not "improved the kernel".
- ISO dates. No invented test counts or benchmark numbers.

## 4. If there are breaking changes

The entry needs a migration note and a major-bump plan, **and** the decision needs a short ADR under
`docs/adr/`. Say so explicitly rather than burying it in field 6.

## 5. Refresh project state

Update `.claude/memory/PROJECT_STATE.md`: phase progress, module status, public surface, known gaps.
That file answers "where is this project right now" in one read — keep it true.

## 6. Stage it

```bash
git add .claude/memory/ENGINEERING_LOG.md .claude/memory/PROJECT_STATE.md
```

The pre-commit hook blocks any commit touching `src/` without a staged log update.
