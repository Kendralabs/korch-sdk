# Background — source inputs

**These documents are provenance, not specification.** They are the original product and build
material that [`docs/specs/`](../specs/README.md) was derived from. Read them for context and
history. **Do not build from them.** Where they disagree with `docs/specs/`, the specs win.

| Document | What it is | Still useful for |
|---|---|---|
| [korchestrator-sdk-build-specification.md](korchestrator-sdk-build-specification.md) | The original SDK developer guide and build specification | The reasoning behind the phase sequence and the capability coverage contract |
| [kendra-orchestrator-platform-reference.md](kendra-orchestrator-platform-reference.md) | Product and technical reference for the KOrchestrator platform | Platform context, sibling systems (KACP/KCG/KIAM/KMCP), the honest built-vs-backlog status (§15), and the hyperscale scaling blueprint (§16) |

## Known differences from `docs/specs/`

All deliberate and ADR-backed. Each is called out in a banner at the top of the affected document.

| Topic | Source input says | Current decision |
|---|---|---|
| TypeScript client | In scope for Phase 9 | **Deferred** — specified, not built ([ADR 0008](../adr/0008-typescript-client-deferred.md)) |
| License | Undecided, to settle in Phase 0 | **Apache-2.0** ([ADR 0003](../adr/0003-license-apache-2-0.md)) |
| Remote auth | Two candidate schemes, pick one | **`Authorization: Bearer`** ([ADR 0005](../adr/0005-remote-auth-bearer-token.md)) |
| Engineering log path | `memory/ENGINEERING_LOG.md` | `.claude/memory/ENGINEERING_LOG.md` |

## Not published

This directory is excluded from the documentation site build. It is engineering provenance for
contributors, not user-facing documentation — publishing a superseded specification alongside the
current one is how readers end up building the wrong thing. Keep `docs/background/` out of the
`mkdocs.yml` nav and in the `exclude_docs` list.
