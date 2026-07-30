# ADR 0019 — `GovernanceHaltError` from `before_superstep` now actually halts a run

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** SDK maintainers
- **Phase:** Retroactively completes the veto path documented in spec 07 §9 (deferred at P6.8/P7)
- **Supersedes / Superseded by:** None. Completes the sanctioned-exception path spec 07 §9 already
  specified; does not change any other hook/middleware semantics.

## Context

`korchestrator/services/hooks.py`'s `HookRegistry._safe()` catches every exception raised from a
`Middleware` hook — including `before_superstep` — logs it, and lets the run continue. This was a
deliberate, documented gap: the module docstring stated *"the `before_superstep`
`GovernanceHaltError` veto → pause is wired with governance in a later phase; for now every failure
is isolated so runs always complete."* Spec 07 §9's own extensibility table already prescribed the
target behavior: a `before_superstep` middleware raising `GovernanceHaltError` is *"the only
sanctioned way for middleware to stop a run"* and should transition the run to `governance_paused`.

Building the dashboard client's HITL (human-in-the-loop) scenario (Scenario 4 of
`dashboard_spec.md`) surfaced the gap directly: a "reject" decision could not make the SDK stop
computing — the swarm kept running to completion on its worker thread regardless of the operator's
decision, with the dashboard only able to hide the outcome from the UI. That's a real capability
gap for the one SDK feature (governance HITL veto) the scenario exists to exercise, not a
dashboard-only workaround-able problem — the spec already promised this exact behavior.

This is a deliberate deviation from the "later phase" deferral, made now because a concrete
consumer needed the documented behavior and the wiring is small, additive, and already fully
specified.

## Decision

Wire the veto path exactly as spec 07 §9 describes, touching only two files:

- `services/hooks.py`: `HookRegistry.before_superstep()` no longer routes through the generic
  `_safe()` swallower for this one phase. It runs each middleware's `before_superstep` in a loop
  that re-raises `korchestrator.exceptions.GovernanceHaltError` immediately while still isolating
  every other exception exactly as before (unchanged: `after_superstep` and `dispatch` keep using
  `_safe()` unconditionally — no other phase's isolation guarantee changes).
- `core/pregel.py`: `PregelRunner.run()` wraps its `await self._observer.before_superstep(current)`
  call in a `try/except GovernanceHaltError` that halts the loop immediately (skipping the
  superstep's compute phase entirely) and returns a terminal `RunResult` with
  `status=RunStatus.GOVERNANCE_PAUSED`, `error_code=exc.code`, `error=exc.message`, via a small
  extension to `build_result()` (`error: str | None = None` parameter, overriding its previous
  hardcoded max-supersteps message rather than replacing it).
- `SuperstepObserver`'s protocol docstring is updated: `before_superstep` implementations may now
  raise `GovernanceHaltError` deliberately; every other exception is still an isolation bug in the
  implementation, unchanged.
- The Temporal runtime is untouched — it does not drive `SuperstepObserver`/`HookRegistry` at all
  yet (`resolve_runtime` never passes `observer` to `TemporalRuntime`; confirmed by reading
  `runtime/__init__.py` and `runtime/temporal_runtime.py` before making this change), so this ADR
  has zero effect on Temporal workflow/activity behavior or replay safety. A Temporal-driven HITL
  pause/resume remains a later-phase capability, not something this ADR claims to deliver.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Leave `hooks.py` as-is; keep the dashboard-level "fake cancel" workaround (publish a UI-only terminal status while the SDK computation runs to completion in the background) | Ships a worse experience for the one feature the scenario exists to prove, wastes compute on a rejected run, and leaves the spec's own documented behavior permanently unimplemented for a gap that turned out to be a two-file, backward-compatible fix. |
| Make `_safe()` itself let `GovernanceHaltError` through everywhere (including `after_superstep`, `before_tool`, `after_tool`, and `dispatch`) | Rejected: spec 07 §9 sanctions the veto specifically from `before_superstep`, before the barrier commits state. By the time `after_superstep` or `dispatch` run, the superstep's result is already final — there is nothing left to veto, and letting exceptions escape those phases too would silently change error-isolation guarantees for every existing middleware/event-handler author, not just governance authors. |
| Introduce a new `RunStatus` (e.g., `GOVERNANCE_HALTED`) instead of reusing `GOVERNANCE_PAUSED` | Rejected: spec 06 §1 and spec 07 §9 already name `governance_paused` as the target status for exactly this transition; adding a second status would fragment the documented vocabulary for no behavioral gain. (Note the resulting asymmetry below under Consequences — it's a naming tension inherited from the spec, not something this ADR should paper over with a new status.) |

## Consequences

**Positive**

- `AgentConfig`/`Middleware` authors get the one escape hatch spec 07 §9 always promised: a
  governance/HITL middleware can now genuinely stop a run instead of only being able to observe it.
- The dashboard's Scenario 4 "reject" now halts the underlying `Swarm`/`Korch` computation
  immediately (raises `GovernanceHaltError`, which the kernel catches) instead of letting it run to
  completion silently in the background — no more wasted compute, and the terminal `RunResult`
  itself reflects the veto (`error_code="KORCH_GOVERNANCE_HALT"`), not just a UI-side illusion.
- Zero behavior change for any existing middleware that doesn't raise `GovernanceHaltError` — every
  other exception from every hook phase is isolated exactly as before (pinned by
  `test_a_raising_middleware_is_isolated` and the new
  `test_a_raising_middleware_is_still_isolated_alongside_a_veto`).

**Negative**

- On the **local** runtime, `RunStatus.GOVERNANCE_PAUSED` is, in practice, terminal — there is no
  resume path (`LocalRuntime.signal()` always raises `NotImplementedError`, and `run()` has already
  returned by the time a caller could act on the status). This is a pre-existing asymmetry in the
  spec (HITL parking-and-resume is a Temporal-only capability), not introduced by this ADR, but this
  change makes it directly observable for the first time on the local runtime, where a status named
  "paused" is functionally a hard stop. Callers building local-runtime HITL flows (like the
  dashboard) should treat a `GOVERNANCE_PAUSED` `RunResult` from `Swarm.run()`/`Korch.run()` as
  terminal, not as something they can resume.
- `build_result()`'s `error` parameter changes its default-message logic from
  `"error_code is set" -> hardcoded max-supersteps string` to `error or (that hardcoded string if
  error_code)`. Existing callers that pass only `error_code` (the max-supersteps path) are
  unaffected since they don't pass `error`.

**Neutral**

- No public API surface changed (`__all__` unchanged; no new public model fields; `RunStatus.
  GOVERNANCE_PAUSED` already existed). This is a behavior completion, not a new contract, so no
  version bump beyond a normal patch/minor release note.

## Compliance

- `tests/unit/services/test_hooks.py::test_governance_halt_error_propagates_from_before_superstep`
  and `::test_a_raising_middleware_is_still_isolated_alongside_a_veto` pin the isolation boundary at
  the `HookRegistry` level.
- `tests/unit/core/test_pregel.py::test_a_governance_halt_from_the_observer_pauses_the_run` pins
  that the kernel halts before the vetoed superstep's compute phase runs and returns
  `GOVERNANCE_PAUSED` with the raised error's `code`/`message`.
- `tests/unit/services/test_run.py::test_a_governance_halt_error_pauses_the_run_end_to_end` pins the
  full `Swarm.run()` path a real consumer (like the dashboard) exercises.
- `mypy --strict`, `ruff check`, and `ruff format --check` are clean on both changed modules.

## Rollback

Fully reversible: reverting `hooks.py`'s `before_superstep` to route through `_safe()` unconditionally and reverting `pregel.py`'s `run()`/`build_result()` to their prior signatures restores the exact prior (documented-as-deferred) behavior. No persisted state format, public model, or `__all__` entry changed, so rollback is a plain code revert with no migration.
