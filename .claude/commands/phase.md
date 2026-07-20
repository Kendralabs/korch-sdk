---
description: Start a build phase or task from the phase plan, with the full standing workflow
argument-hint: "[phase number or task, e.g. P2 or 'P5 explicit router']"
---

Begin work on: **$ARGUMENTS**

Follow the standing workflow. Do not skip steps, and do not start writing code at step 1.

## 1. Locate and restate

Open `docs/specs/11-build-phase-plan.md` and find the phase. Restate, in your own words:

- **Objective** — what this phase is for
- **Build** — the concrete tasks
- **Public surface** — what becomes importable
- **Validation** — what must be demonstrated
- **Definition of Done**

Then confirm it is in scope (`docs/specs/01-scope-and-principles.md` §2–3). If it is not, stop and
say so. If the previous phase's Definition of Done is not met, stop and say so — phases do not overlap.

## 2. Check the prior art

- Which ADRs constrain this work? (`docs/adr/`)
- What did the engineering log say about adjacent work? (`.claude/memory/ENGINEERING_LOG.md`)
- What is the current state? (`.claude/memory/PROJECT_STATE.md`)

## 3. Design the public surface first

Write the signatures, return types, exceptions, and a usage example **before** implementing. Check
every name against the canonical vocabulary in `docs/specs/04-public-api.md` §3.1. If the surface
changes anything frozen in P1, stop — that needs an ADR.

## 4. Place the code

Confirm the layer and the allowed imports (`docs/specs/03-architecture.md` §2–3). Confirm any new
dependency belongs to an extra and is lazy-imported in its one owning module.

## 5. Implement — simplest correct version

No speculative abstraction. Apply the abstraction test before adding any interface or factory.

## 6. Write the tests that lock the behaviour

They must fail without the change. Kernel/runtime/reducer/serde changes additionally need
determinism tests (`.claude/rules/determinism.md`).

## 7. Run the gates

Use `/verify`. Report honestly.

## 8. Update the engineering log — before committing

`/log` — all ten fields. The pre-commit hook blocks a `src/` change without it.

## 9. Commit and PR

Branch `<type>/p<phase>-<slug>` off `develop`. Conventional Commits with the phase tag:
`feat(core): implement Pregel kernel + reducers [P2]`. PR into `develop`. Never commit directly to
`main` or `develop`, and never use `--no-verify`.

## Stop and ask if

- The task conflicts with a golden rule
- It requires changing a P1-frozen contract
- It requires a new dependency, a new port, or a boundary change
- The spec is ambiguous — ask rather than picking an interpretation and building on it
