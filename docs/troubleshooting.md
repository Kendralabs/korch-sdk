# Troubleshooting

Concrete errors, what they mean, and how to fix them.

## `MissingExtraError: The cognitive layer requires the 'dspy' extra`

You called `Korch().run(...)`, `Swarm().run(...)`, or a `WorkerAgent.think(...)` without the
`[dspy]` extra installed. Every reasoning agent is built on DSPy — see the
[FAQ](faq.md#why-does-korchrun-need-the-dspy-extra-i-thought-the-base-install-was-just-pydantic).

**Fix:** `pip install "korchestrator[dspy]"` (or `-e ".[dspy]"` if installing from source — see
[Installation](installation.md)).

## `ConfigurationError: ... mounts tools=(...) but no tool invoker is bound`

An agent's `tools=` names a tool, but the swarm was never given a `connectors=`.

**Fix:** pass the tool's connector or registry to `connectors=` on `Korch`/`Swarm` — see
[Writing a custom tool](tutorials/custom-tool.md).

## `ValidationError` on `Swarm.add()`: duplicate agent id

Two agents were added with the same `id`. This is a deliberate rejection (an earlier version of
the SDK silently overwrote the first agent instead) — pick distinct ids.

## `ValidationError`: `max_supersteps` out of range

`Korch.run`/`Swarm.run`'s `max_supersteps` must be between 1 and 100. Pick a value in range —
there's no way to disable the bound entirely; an unbounded run is a design smell (a run that
should have halted did not).

## The default one-liner's output looks like garbage, not an answer

`Korch().run(...)` with no `model_gateway=` and no real gateway configured uses `MockLM`'s default
completion — a raw echo of the rendered prompt, not a real answer. This is expected: MockLM exists
to be deterministic and offline, not to produce readable text. Either script a response
(`MockLM(default_response="...")`) for a clean demo, or configure a real gateway (`KENDRA_AI_
GATEWAY_URL`/`KENDRA_GATEWAY_API_KEY`) for real answers. See the [Quick Start](quickstart.md).

## `NotImplementedError` from `Korch.pause`/`resume`/`cancel`

These require the durable runtime — `pause`/`resume`/`cancel`/`edit_resume` have nothing to signal
on the local runtime, which is synchronous and has no in-flight run to interrupt.

**Fix:** `pip install "korchestrator[temporal]"` and set `KORCH_RUNTIME=temporal` — see
[Human-in-the-loop](tutorials/hitl.md).

## `RunStatus.TIMED_OUT` on a paused durable run

A paused run (manual or governance auto-pause) waits up to a 24-hour deadline for `resume`,
`cancel`, or `edit_resume`. If nothing arrives, it times out on its own — this is not a bug, it's
the designed failure mode for an unattended pause. Build operator tooling that actually watches
pauses, not one that assumes a human will notice in time. See
[Human-in-the-loop](tutorials/hitl.md#what-happens-if-nobody-resolves-it).

## `ValidationError` from `from_json`: schema_version newer than supported

You're reading a payload written by a newer version of the SDK than you have installed (or the
version was downgraded after writing). Upgrade the installed package to a version that supports
that `schema_version`, or re-serialize from the original source with your current version. See
[Migration](migration.md#data-migrations-serialized-state).

## `RuntimeError: Failed validating workflow ...` under the durable runtime (local dev only)

If this happens on a plain `pip install "korchestrator[temporal,otel]"` (or any combination that
pulls in both `temporalio` and a package using `beartype`'s import hooks, such as some
observability extras), the underlying cause is usually a circular import inside
`beartype.claw` that the workflow engine's sandbox import hook triggers — a known conflict between
those two packages' import-time behavior, not a Korchestrator defect.

**To confirm it's this and not something you changed:** the same failure reproduces on an
unmodified checkout — check with `git stash` if you have local changes, or try a clean virtualenv
with only `[temporal]` installed (no `[otel]`, no other package that imports `beartype`).

**Workarounds:**

- Avoid installing `beartype`-dependent packages alongside `[temporal]` in the same environment if
  you can.
- Run the durable-runtime test/workflow paths in a separate virtualenv from packages that pull
  in `beartype`.
- This is a real, tracked gap in some local dev environments — it does not affect the local
  runtime, MockLM, or any code path outside the durable runtime.

## I get an import error mentioning `backend`, `apps`, `services`, or `frontend`

You're importing from an application package that this SDK deliberately never depends on (the
isolation gate blocks this at commit time in the SDK's own repository). If you're consuming
Korchestrator from your own application, this shouldn't happen — check that you're not
accidentally shadowing one of those names with a local module on your `sys.path`.

## Next

- [FAQ](faq.md) — conceptual questions, not error messages.
- Open an issue on the repository if none of the above matches what you're seeing.
