# Implementation Status — Korchestrator SDK

Plain-language snapshot of what has been built, where things stand, and how to pick the work back
up. Written for a quick read; the authoritative technical records stay in `.claude/memory/` and
`docs/specs/`.

**Last updated:** 2026-07-23

## Files in this folder

- **[what-has-been-built.md](what-has-been-built.md)** — every phase so far (P0–P9), each explained
  in simple points.
- **[how-to-continue.md](how-to-continue.md)** — what is left to do, and the exact prompt to paste
  into a new session to continue.

## At a glance

| Phase | Title | Status |
|---|---|---|
| P0 | Foundations & scaffolding | ✅ Done |
| P1 | Public API & interface contracts | ✅ Done |
| P2 | Core execution kernel (Pregel) | ✅ Done |
| P3 | Runtime adapters (local + Temporal) | ✅ Done |
| P4 | Cognitive layer (agents, taxonomy) | ✅ Done — first end-to-end run |
| P5 | Model routing | ✅ Done — merged & pushed |
| P6 | Integration & observability | ✅ Done — merged & pushed |
| P7 | Governance, security & context graph | ✅ Done — all 6 tasks (P7.1–P7.6) |
| P8 | Cross-cutting foundations | ✅ Done — all 7 tasks (P8.1–P8.7) |
| P9 | Remote client (Python) | ✅ Done — all 8 tasks (P9.1–P9.8) |
| P10 | Testing, benchmarks & quality | ⬜ Not started |
| P11 | Docs, examples & DX | ⬜ Not started |
| P12 | CI/CD, packaging & publishing | ⬜ Not started |
| P13 | External backend adapter | ⬛ Out of scope (separate repo) |

## Where the code lives right now

- **`develop` branch** (pushed to GitHub): contains **P0 through P9** — everything is merged and
  green.
- **`feat/p9-remote-client` branch** (pushed, merged into `develop`): contains all of **P9.1–P9.8**.
- Next: **Phase 10 — Testing, benchmarks & quality gates**, on a new `feat/p10-*` branch off
  `develop`.

## One-line summary

The SDK already runs a full multi-agent job end-to-end offline: `Korch().run("...")` plans a team,
runs them in deterministic parallel supersteps, routes a model per agent, and returns an answer —
with tools, MCP, streaming, hooks, PII redaction, trust-scored governance with durable
human-in-the-loop pause/resume, and a bitemporal Context Graph for decisions and events.
Configuration, logging, serialization, validation, and telemetry are all finalized and
settings-injected end to end. An optional Python remote client (`korchestrator.remote.
KorchestratorClient`, behind `[remote]`) now drives a hosted engine over the full documented
contract — run lifecycle, control, identity, key management, discovery, and SSE streaming — with
the TypeScript client's contract settled (`docs/parity-matrix.md`) but not built (ADR 0008). Phase
10 (testing, benchmarks, and a ratcheted quality bar) is next.
