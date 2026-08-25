# Contributing & Feedback

There are two different things people mean by "contributing" here — pick the one that matches
what you're trying to do.

## Using the SDK and found a bug, want a feature, or have feedback

This is the path for almost everyone during the beta — you don't need to write any Korchestrator
code for this.

- **Bug report** — open an issue using the
  [bug report template](https://github.com/Kendralabs/korch-sdk/issues/new?template=bug_report.yml).
  Include a minimal reproduction that runs offline against `MockLM` (no API key, no network) if at
  all possible — that's the fastest path to a fix.
- **Feature request or API feedback** — open an issue using the
  [feature request template](https://github.com/Kendralabs/korch-sdk/issues/new?template=feature_request.yml).
  This is exactly the feedback channel the beta exists for: what ships in `1.0` is shaped by what
  beta users report against the `0.x` public API — see [Versioning](versioning.md).
- **A usage question, not a defect** — use
  [GitHub Discussions](https://github.com/Kendralabs/korch-sdk/discussions) instead of an issue.
- **A security vulnerability** — never a public issue. See
  [`SECURITY.md`](https://github.com/kendralabs/korch-sdk/blob/main/SECURITY.md) for the private
  reporting channel and what to expect.

`Kendralabs/korch-sdk` is public — no repository access request needed to file an issue, start a
discussion, or open a PR.

## Contributing code

The full engineering workflow — branching model, the local gate (lint/types/tests/coverage),
architecture boundaries, PR expectations, and the release process — is documented in
[`CONTRIBUTING.md`](https://github.com/kendralabs/korch-sdk/blob/main/CONTRIBUTING.md) at the
repository root. It assumes you're comfortable with the project's `dev → staging → main` branching
model ([`.claude/rules/branching-and-promotion.md`](https://github.com/kendralabs/korch-sdk/blob/main/.claude/rules/branching-and-promotion.md))
and is written for both human and AI-agent contributors — the repository is configured for
Claude Code out of the box.

## Community standards

Participation in this project — issues, discussions, PRs, and any other project space — is
governed by the
[Contributor Covenant Code of Conduct](https://github.com/kendralabs/korch-sdk/blob/main/CODE_OF_CONDUCT.md).
Report a violation to `conduct@kendralabs.com`.

## Next

- [FAQ](faq.md) — conceptual questions that come up often.
- [Troubleshooting](troubleshooting.md) — concrete error messages and fixes.
- [Versioning](versioning.md) — what beta feedback actually changes before `1.0`.
