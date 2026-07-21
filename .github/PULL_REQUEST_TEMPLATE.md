<!--
Conventional Commit title with a phase tag, e.g.:
  feat(core): implement Pregel superstep runner [P2]
-->

## Intent

<!-- What this PR does and why. Link the phase/task in docs/specs/12-implementation-plan.md. -->

## Scope and risk

- [ ] This change is in scope for the SDK (one product; no backend/frontend/service).
- [ ] The diff stays narrowly on the stated intent; unrelated cleanup is not mixed in.
- **Risk:** <!-- what could regress, and how it is contained -->

## Public surface and compatibility

- [ ] No change to `korchestrator.__all__`, or the change is additive, documented, and the
      golden snapshot + `CHANGELOG.md` are updated in this PR.
- [ ] Compatibility impact: <!-- none | additive | breaking (0.x) — with migration note -->

## Architecture and determinism

- [ ] Imports point inward; `core/` stays framework-free; heavy imports stay lazy and confined.
- [ ] No sibling feature-module imports; no import cycles.
- [ ] The environment is read only in `config/`; no hardcoded URL/key/model/path.
- [ ] Workflow-path code uses no wall clock or randomness; new reducers are associative and
      order-independent with property tests (if applicable).

## Tests and evidence

- [ ] New behaviour ships a test that fails without the change; a bug fix ships a regression
      test that failed on the old code.
- [ ] Determinism tests added where the kernel/runtime/reducers/serialization changed.
- **Gates run (state what passed):** ruff · ruff format · `mypy --strict` · pytest + coverage ·
      isolation gate · env-read confinement · version-validate · build

## Security and trust boundaries

- [ ] Identity and tenant scope carried through; validation at the boundary; security fails closed.
- [ ] No credentials, tokens, or personal data in logs, spans, exceptions, or fixtures.

## Records

- [ ] `.claude/memory/ENGINEERING_LOG.md` updated (ten fields) for any `src/` change.
- [ ] `CHANGELOG.md` entry added for any user-visible change.
- [ ] ADR added under `docs/adr/` for any material or durable decision.

## Rollback

<!-- How to revert this change safely. -->
