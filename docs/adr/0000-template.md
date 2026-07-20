# ADR NNNN — <Title>

- **Status:** Proposed
- **Date:** YYYY-MM-DD
- **Deciders:** SDK maintainers
- **Phase:** P<n>
- **Supersedes / Superseded by:** —

## Context

State the forces, not the conclusion. What problem exists right now, what constraints apply
(specs, golden rules, existing contracts), and why the decision cannot be deferred. Cite the
spec section or golden rule that makes this a material decision. If a prior ADR is being
revisited, name it and say what changed in the world.

## Decision

State the decision in the present tense, as a rule someone can follow or violate. Be specific
enough that a reviewer can tell whether a diff complies. Name the concrete artefacts: files,
symbols, config keys, header names, CI job names. Avoid hedging — an ADR that says "we should
probably prefer" is not a decision.

## Alternatives considered

| Option | Why rejected |
|---|---|
| <the strongest real alternative> | <the honest trade-off — what it would have bought, and the specific cost that outweighed it> |
| <second alternative> | <why rejected> |

Do not list strawmen. If an alternative is genuinely close, say so and record what would make it
win later; that sentence becomes the re-entry condition for a future superseding ADR.

## Consequences

**Positive**

- <what becomes easier, cheaper, or safer>

**Negative**

- <what becomes harder or is given up — be specific; every real decision costs something>

**Neutral**

- <consequences that are neither good nor bad but that a reader must know>

## Compliance

How a reviewer or CI check verifies this ADR is being honoured. Be concrete: name the CI job, the
test module, the lint rule, the grep, or the settings entry. If compliance is currently manual
(reviewer judgement only), say so plainly and note what would make it automatable.

## Rollback

What reversing this decision costs today, and the point of no return after which reversal is a
breaking change requiring a major bump and a migration guide.

---

<!--
Filing instructions:
1. Copy this file to docs/adr/NNNN-kebab-case-title.md using the next unused number.
2. Fill in every section. An empty section is a defect, not a placeholder.
3. Land the ADR in the same PR as the change it justifies.
4. Set Status to Accepted only when the PR is approved and merged.
5. Once Accepted, the file is immutable except for the Superseded by field. Supersede, never edit.
-->
