# Security Policy

We take the security of the Korchestrator SDK seriously and appreciate responsible
disclosure.

## Supported versions

While the project is in its `0.x` line, security fixes are released only against the
**latest published `0.x` version**. There is no backport window for older `0.x` releases;
upgrade to the newest release to receive fixes. When `1.0.0` ships, this policy is updated
to name a supported-version window.

| Version | Supported |
|---------|-----------|
| latest `0.x` | ✅ |
| older `0.x` | ❌ (upgrade to latest) |

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.**

Report it privately through either channel:

- **GitHub private vulnerability reporting** — open a report via the repository's
  *Security → Report a vulnerability* form
  (https://github.com/kendralabs/korch-sdk/security/advisories/new).
- **Email** — `security@kendralabs.com`.

Please include: the affected version, a description of the issue and its impact, and the
minimal steps or proof-of-concept needed to reproduce it. Do not include real secrets or
personal data in your report.

## What to expect

- **Acknowledgement** within **3 business days** of your report.
- An initial assessment and a remediation plan within **10 business days**.
- Coordinated disclosure: we agree a disclosure timeline with you, fix forward with a new
  patch release, and credit you in the release notes unless you prefer to remain anonymous.

## Scope

This policy covers the code in this repository — the published `korchestrator` distribution
and its documented public surface. Infrastructure that a consumer provisions and operates
(a Temporal cluster, a database, a model gateway, MCP servers) is outside this repository's
control and is the operator's responsibility.
