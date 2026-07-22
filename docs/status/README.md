# Implementation Status — Korchestrator SDK

Plain-language snapshot of what has been built, where things stand, and how to pick the work back
up. Written for a quick read; the authoritative technical records stay in `.claude/memory/` and
`docs/specs/`.

**Last updated:** 2026-07-22

## Files in this folder

- **[what-has-been-built.md](what-has-been-built.md)** — every phase so far (P0–P7.1), each explained
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
| P7 | Governance, security & context graph | 🔨 In progress — 1 of 6 tasks done (Shield) |
| P8 | Cross-cutting foundations | ⬜ Not started |
| P9 | Remote client (Python) | ⬜ Not started |
| P10 | Testing, benchmarks & quality | ⬜ Not started |
| P11 | Docs, examples & DX | ⬜ Not started |
| P12 | CI/CD, packaging & publishing | ⬜ Not started |
| P13 | External backend adapter | ⬛ Out of scope (separate repo) |

## Where the code lives right now

- **`develop` branch** (pushed to GitHub): contains **P0 through P6** — everything is merged and
  green.
- **`feat/p7-governance-security` branch** (local only, not pushed yet): contains **P7.1 (Shield
  redactor)** on top of `develop`.

## One-line summary

The SDK already runs a full multi-agent job end-to-end offline: `Korch().run("...")` plans a team,
runs them in deterministic parallel supersteps, routes a model per agent, and returns an answer —
with tools, MCP, streaming, hooks, and PII redaction available. Governance (auto-pause), durable
human-in-the-loop controls, and the memory graph are the next things to build.
