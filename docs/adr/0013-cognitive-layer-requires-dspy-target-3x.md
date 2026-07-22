# ADR 0013 — The cognitive layer requires `[dspy]`; target DSPy 3.x

- **Status:** Accepted
- **Date:** 2026-07-22
- **Deciders:** SDK maintainers (with product owner)
- **Phase:** P4
- **Supersedes / Superseded by:** Refines the `[dspy]` pin in spec 02 §8; resolves the spec 04 §2.1
  vs spec 11 P4 tension about whether the base install can reason.

## Context

Two questions block the reasoning core (P4.6):

1. **Does the Tier-1 one-liner need `[dspy]`?** Spec 04 §2.1 says `Korch().run(...)` "works on a base
   install with no configuration … must never regress". Spec 11 P4 says "the base install (no
   `[dspy]`) still imports cleanly and raises an actionable `MissingExtraError` when the cognitive
   layer is used." Taken together they conflict: the one-liner *is* the cognitive layer.

2. **Which DSPy?** Spec 02 §8 pins `dspy-ai>=2.5,<3` and spec 11 names `TypedPredictor`. But
   `dspy-ai` now redirects to the modern `dspy` package, which installs as **3.x** — so `<3` does not
   constrain the real module, and `dspy.TypedPredictor` **does not exist in 3.x** (typed prediction
   folded into `dspy.Predict`).

## Decision

**1. Reasoning requires the `[dspy]` extra.** There is a single reasoning path — the DSPy
`WorkerAgent`. A `pydantic`-only install imports the whole package cleanly, but *running* reasoning
(`Korch().run`, `Swarm().run`, or a `WorkerAgent.think`) raises an actionable `MissingExtraError`
naming `pip install 'korchestrator[dspy]'`. "Base install with no configuration" (spec 04 §2.1) is
read as *no API key and no network* — MockLM by default — **with `[dspy]` present**; the pydantic-only
floor is the *import* contract, not the *run* contract. This keeps one reasoning implementation
(no parallel non-DSPy worker to maintain and keep in behavioural parity).

**2. Target DSPy 3.x.** The `[dspy]` extra becomes `dspy>=2.6,<4` (the maintained line), and the
worker is built on `dspy.Predict` (typed via a compiled `Signature`) and `dspy.ReAct` (bounded loop),
not the removed `TypedPredictor`. The lazy `Signature.to_dspy()` (P4.5) already targets the stable
`make_signature` / `InputField` / `OutputField` API that spans 2.6–3.x.

## Alternatives considered

- **A non-DSPy default worker so the pydantic-only install can run.** Rejected by the product owner:
  it doubles the reasoning surface (a simple gateway-completion worker *and* the DSPy worker) and
  risks the two drifting; the determinism/equivalence tests would have to cover both.
- **Pin DSPy to 2.5.x** to match the spec's `TypedPredictor`. Rejected: 2.5.x is the old line;
  `dspy-ai` already resolves to 3.x, so pinning `<3` is both ineffective and a maintenance trap.

## Consequences

- `agents/` imports `dspy` lazily (unchanged confinement). Using reasoning without the extra raises
  `MissingExtraError`; the Tier-1/Tier-2 doctests that actually run stay `xfail` until P4.9 and then
  execute in the `[dspy]` CI job (with MockLM, offline).
- The extras matrix in spec 02 §8 is updated (`dspy-ai>=2.5,<3` → `dspy>=2.6,<4`); docs and the parity
  matrix follow in the same phase.
- The worker uses `dspy.Predict`/`dspy.ReAct`; any reference to `TypedPredictor` in the specs is read
  as "typed prediction", satisfied by `dspy.Predict` over a typed signature.
- Determinism (spec 06 §6) is preserved by running reasoning under **MockLM**, which is deterministic
  and offline; the DSPy call is confined to an activity boundary (`asyncio.to_thread`), never workflow
  scope.

## Rollback

If a zero-extra reasoning path is later required, add a non-DSPy worker behind the same `Agent`
contract and have the façade select it when `[dspy]` is absent; flip this ADR to *Superseded*. The
DSPy version pin can widen or narrow without an ADR as the ecosystem moves, provided the worker's
`Predict`/`ReAct` usage stays API-compatible.
