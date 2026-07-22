# ADR 0011 — `httpx` is confined to `clients/` **and** `providers/gateway_openai.py`

- **Status:** Accepted
- **Date:** 2026-07-22
- **Deciders:** SDK maintainers
- **Phase:** P4
- **Supersedes / Superseded by:** Refines the heavy-dependency confinement stated in spec 02 §8,
  spec 03 §7, spec 05 §57 and CLAUDE.md §3 ("`httpx` → `clients/`"); reconciles it with the gateway
  example in spec 08 §2.2. Does not change the `[remote]` extra (ADR 0004).

## Context

The confinement rule is stated in several places as a one-line mapping: `dspy → agents/`,
`temporalio → runtime/temporal_runtime.py`, **`httpx → clients/`**, OTel → `telemetry/`. Read
literally, `httpx` may appear in exactly one module, `clients/`.

Phase 4 lands `providers/gateway_openai.py` — the default networked `IModelGateway` (spec 03 §5,
spec 05 §36: "`providers/` … OpenAI-compatible gateway"). A model gateway's entire job is to make an
HTTP call to a chat-completions endpoint, and spec 08 §2.2 shows precisely that: a gateway
`complete()` method doing `import httpx` and wrapping `httpx.TimeoutException` / `httpx.HTTPError`.

So two authoritative specs point in different directions:

- The confinement mapping says `httpx` lives only in `clients/`.
- The gateway catalogue (spec 05 §36) puts the gateway in `providers/`, and the gateway example
  (spec 08 §2.2) makes it use `httpx`.

The gateway cannot satisfy both by delegating to `clients/`: `providers/` and `clients/` are sibling
feature modules, and the independence rule (spec 05 §56, `.importlinter` `features-are-independent`)
forbids a feature module importing a sibling. Nor can it route HTTP through `dspy` — `dspy` is
confined to `agents/`. The gateway must therefore own its own `httpx` usage.

## Decision

**`httpx` is confined to two modules, each importing it lazily inside the function that needs it:**

1. `korchestrator.clients` — the remote `KorchestratorClient` (Tier 4), and
2. `korchestrator.providers.gateway_openai` — the default networked `IModelGateway`.

Both sit behind the `[remote]` extra. The confinement's intent is preserved in full:

- **One extra owns it.** `httpx` is only ever pulled in by `[remote]`; the base install stays
  `pydantic`-only. Verified: `import korchestrator.providers` imports no `httpx`.
- **Lazy.** The import happens inside `complete()` / `available_models()` (and the client's request
  methods), never at module top level — so importing the module never requires the extra.
- **Never inward.** `httpx` never appears in `core/`, `models/`, or `interfaces/`; the
  `kernel-is-framework-free` import-linter contract continues to forbid it in `core/`.

The one-line "`httpx → clients/`" mapping is hereby read as "`httpx` → the SDK's HTTP-owning modules",
which are these two. The mapping predates the networked gateway; this ADR records the correction.

## Alternatives considered

- **Put the gateway in `clients/`.** Rejected: contradicts the module catalogue (spec 05 §36, which
  assigns the gateway to `providers/`) and would mix the ARI provider layer with the remote client.
- **Define an HTTP-transport port in `interfaces/` and implement it in `clients/`.** Rejected as
  over-engineering (fails the abstraction test — one real implementation, no demonstrated second
  axis) and still needs `providers/` to reach an HTTP implementation it may not import directly.
- **Route the gateway through `dspy`.** Rejected: `dspy` is confined to `agents/`, and the default
  gateway must work without the `[dspy]` extra.

## Consequences

- `providers/gateway_openai.py` legitimately imports `httpx` (lazily). Reviews and audits treat this
  as compliant with the confinement, per this ADR.
- The confinement is now **machine-enforced**: a new `import-linter` `forbidden` contract forbids
  `httpx` in every layer except `clients/` and `providers`, so a stray `httpx` import elsewhere
  (e.g. `agents/`, `routing/`) fails CI rather than relying on prose.
- No change to the public API, the extras matrix, or the base install.

## Rollback

If a future design introduces a shared internal HTTP utility, move both call sites onto it and narrow
the confinement back to a single module; update this ADR's status to *Superseded* and the
`import-linter` contract accordingly.
