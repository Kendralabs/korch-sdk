---
description: Draft an Architecture Decision Record for a material decision
argument-hint: "[the decision, e.g. 'add a caching port for embeddings']"
allowed-tools: Bash, Read, Write, Grep, Glob
---

Draft an ADR for: **$ARGUMENTS**

## 1. Check it needs one

An ADR is **required** for: a public API contract change, a new dependency or extra, a
boundary/layering change, any deviation from `docs/specs/`, a security-relevant default, or a
breaking change.

It is **not** needed for: implementation detail behind a settled contract, refactors that preserve
behaviour and boundaries, or test and documentation changes.

If it does not need one, say so and stop — an ADR for a non-decision is noise.

## 2. Check it is not already decided

```bash
ls docs/adr/
grep -ril "<key terms>" docs/adr/
```

If an existing ADR covers it, either it already answers the question, or this ADR **supersedes** it —
in which case say so in both files. ADRs are immutable once Accepted: you supersede, never edit.

## 3. Draft it

Copy `docs/adr/0000-template.md` to the next monotonic number (never reuse one). Fill every section:

- **Context** — the forces, honestly. What makes this a real decision rather than an obvious one?
- **Decision** — one paragraph, unambiguous, in the active voice.
- **Alternatives considered** — the *real* trade-off for each rejection. A strawman alternative
  makes the ADR worthless to the person who reopens this in a year.
- **Consequences** — positive, negative, and neutral. **Name the cost.** An ADR with no negative
  consequences is not describing a decision.
- **Compliance** — how a reviewer or CI check verifies this is being honoured. Name the specific
  check, test module, or gate. If the check does not exist yet, say so and note which phase creates it.
- **Rollback** — what reversing costs, and the point of no return.

## 4. Land it with the change

The ADR merges in the **same PR** as the change it justifies — not before, not after. Status
`Accepted` only once a reviewer has signed off; until then it is `Proposed`.

## 5. Cross-link

If a spec in `docs/specs/` is affected, update it in the same PR and link to the ADR from it. The
ADR records the decision; the spec records the resulting design.
