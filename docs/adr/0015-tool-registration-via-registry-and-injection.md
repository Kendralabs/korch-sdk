# ADR 0015 — Tools register on a `ConnectorRegistry`, not a process-global

- **Status:** Accepted
- **Date:** 2026-07-22
- **Deciders:** SDK maintainers
- **Phase:** P6
- **Supersedes / Superseded by:** Refines the registration wording in spec 07 §6 and the public
  surface in spec 04 §7 / spec 11 P6 for the `0.x` line. Parallels ADR 0014 (router registration).

## Context

Spec 07 §6 and the P6 public surface name `register_tool` / `register_connector` and offer three
registration paths: `Korch(connectors=[...])`, "`register_connector(...)` at the composition root",
and the `korchestrator.connectors` entry point. Read literally as *module-level* functions,
`register_tool`/`register_connector` would mutate a process-global registry — which collides with
architecture boundary **B8** ("no import-time side effects, no module-level singletons") and with the
"How NOT to extend" rejections in spec 07 §11 (monkey-patching / global mutation).

## Decision

Registration is **on a `ConnectorRegistry` instance**, wired at the composition root:

- `ConnectorRegistry([...])`, `.register_connector(connector)`, `.register_tool(name, schema, fn)` —
  the documented method names, on the registry, returning `self` for chaining.
- `Korch(connectors=[...])` / `Swarm(connectors=[...])` build and own the registry (the composition
  root), exactly as they own the gateway, runtime, repository, and router.
- `.discover()` reads the `korchestrator.connectors` entry-point group; a failing or duplicate plugin
  is logged and skipped, never fatal.

There is **no process-global `register_tool`/`register_connector` free function** and no implicit
global registry. This keeps one injection idiom across every replaceable collaborator and satisfies
B8.

## Consequences

- **Positive.** No global mutable state; registration is explicit and testable; the entry-point path
  still gives zero-code discovery for installed packages. The AUB bridge (`invoke_tool`) takes the
  registry explicitly, so tool resolution is never ambient.
- **Negative.** Code that expected a bare module-level `register_connector()` must call it on a
  registry (or pass `connectors=` to `Korch`). Mitigation: the names and semantics are identical; only
  the receiver changed.
- **Rollback.** Additive: a thin module-level convenience over a lazily-resolved default registry
  could be added later without changing the registry API — but only if a real need appears (it has
  not).
