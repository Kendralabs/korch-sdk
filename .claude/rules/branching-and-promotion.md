# Rule — Branching and promotion

Repository-specific and **authoritative** for this repo's branch model. The org-wide baseline
(`Fintricity/.claude/rules/git-and-review.md`) still applies for commit style and review
expectations; this file overrides it wherever the two describe branch names.

## The three long-lived branches

```
<type>/<slug>  →  dev  →  staging  →  main
```

| Branch | Role | Receives from |
|---|---|---|
| `dev` | Integration. Everything lands here first. | Short-lived work branches |
| `staging` | Release-candidate verification against a promotion-only snapshot. | `dev` |
| `main` | Released. The only branch tags are cut from. | `staging` |

`main` is the repository's default branch: it is what a visitor lands on and what release
automation reads. Work PRs must therefore **retarget to `dev`** — GitHub will propose `main` by
default and that proposal is always wrong for feature work.

## The invariant

At rest, every commit on `main` is on `staging`, and every commit on `staging` is on `dev`:

```bash
git merge-base --is-ancestor origin/main origin/staging \
  && git merge-base --is-ancestor origin/staging origin/dev \
  && echo OK
```

This must print `OK`. If it does not, a promotion was skipped or a branch was written to directly —
fix that before merging anything else. Everything below exists to keep this invariant true.

## Doing the work

1. Branch off `dev` as `<type>/p<phase>-<slug>` — `feat`, `fix`, `docs`, `refactor`, `test`,
   `chore`, `security`, `perf`. Example: `feat/p2-superstep-kernel`.
2. Commit with Conventional Commits and the phase tag: `feat(core): add reducers [P2]`.
3. Open a PR **into `dev`**. Merge with `--no-ff` so the branch's shape survives in history.
4. Delete the work branch once merged.

## Promoting

Promotion is a PR like any other, merged `--no-ff`, and obeys three constraints:

- **Forward-only.** Promote whatever is on the source branch, as a unit. Never cherry-pick a subset
  into `staging` or `main` — that is what breaks the invariant and produces "fixed in dev, still
  broken in main" states that nobody can reason about.
- **No skipping.** `dev → main` directly is prohibited, including for "trivial" changes. The stage
  exists to be observed, not to be believed.
- **Green first.** The source branch must be green on the full CI matrix before the promotion PR
  opens, not after.

`src/korchestrator/version.py` is edited **only** in the `staging → main` release PR, and tags are
cut **only** on `main`. See `docs/releases.md`.

## Hotfixes — the one exception

A production defect too urgent to walk through `dev` may branch `fix/<slug>` off **`main`** and PR
back into `main`. It is then **immediately back-merged `main → staging → dev`**, in that order, in
the same session.

Skipping the back-merge silently reverts the fix on the next ordinary promotion, because `staging`
and `dev` still carry the old code and they are what flows forward. A hotfix that is not
back-merged is a hotfix that will be undone.

## Never

- Commit directly to `dev`, `staging`, or `main` — all three land changes only via reviewed PRs.
- Force-push or rewrite history on any of the three.
- `git commit --no-verify`.
- Promote a red branch, or promote to "get CI to run on it".
