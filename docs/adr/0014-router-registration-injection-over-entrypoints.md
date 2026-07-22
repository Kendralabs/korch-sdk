# ADR 0014 — Custom routers plug in by injection; entry-point discovery deferred

- **Status:** Accepted
- **Date:** 2026-07-22
- **Deciders:** SDK maintainers
- **Phase:** P5
- **Supersedes / Superseded by:** Narrows the three registration paths in spec 07 §5 for the `0.x`
  line; may be revisited when a second discovery consumer appears.

## Context

Spec 07 §5 lists three ways a custom `BaseRouter` is registered:

1. constructor injection — `Korch(router=CheapestRouter())`;
2. `ROUTING_STRATEGY` naming a discovered plugin;
3. the `korchestrator.routers` entry point.

P5.6's acceptance is narrower: "a custom `BaseRouter` plugs in **via config with no package edit**."
`ROUTING_STRATEGY` is typed in spec 08 §1 as `Literal["explicit","semantic","algorithmic","composite"]`
— a closed set of built-ins, not a free-form plugin name — so (2) as written cannot carry an arbitrary
dotted path without widening that type. (3) requires an `importlib.metadata` entry-point discovery
mechanism and a separately installed distribution to exercise.

The abstraction test (`architecture-boundaries.md`) asks for a demonstrated second implementation and
net code reduction before adding a plug-in point. There is exactly one in-tree consumer of router
selection today (the composition root), and no committed second one.

## Decision

For the `0.x` line, a custom router plugs in **by injection**: `Korch(router=...)` / `Swarm(router=...)`,
resolved by `routing.resolve_router(settings, router=...)` — the injected instance always wins, with
no package edit. `ROUTING_STRATEGY` selects among the **built-in** strategies only, exactly as typed in
spec 08. The `korchestrator.routers` entry-point discovery mechanism is **deferred** until a real second
consumer exists (e.g. a distributed/plugin deployment), at which point it earns its own ADR and the
`ROUTING_STRATEGY` type is widened deliberately rather than by accident.

Injection is the DIP-clean path the rest of the SDK already uses (gateway, runtime, repository), so this
keeps one registration idiom across all replaceable collaborators.

## Consequences

- **Positive.** No speculative discovery machinery; one injection idiom for every collaborator; the
  `ROUTING_STRATEGY` compatibility surface stays a closed, validated enum. P5.6's acceptance is met and
  tested (`resolve_router` returns the injected router; a `UserFunctionRouter` pinned model reaches the
  gateway end-to-end).
- **Negative.** A user who wants pure-config router selection (no code) cannot name a third-party router
  in an environment variable yet. Mitigation: `UserFunctionRouter(my_fn)` and `Korch(router=...)` cover
  the code-level case; entry points arrive when there is a demonstrated need.
- **Rollback.** Additive: introducing entry-point discovery later does not change the injection API or
  the `RoutingResult` contract; it only adds a new resolution source behind `resolve_router`.
