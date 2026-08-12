# Contributing to Korchestrator

Thank you for helping build the Korchestrator SDK. This guide is the short version of the
engineering standard; the authoritative detail lives in `docs/specs/` (start with
`docs/specs/00-overview.md`) and in `.claude/rules/`.

The SDK is **one product**: an installable, self-contained Python library. It ships no
backend, frontend, service, or infrastructure. Contributions that add any of those are out
of scope (see `docs/specs/01-scope-and-principles.md`).

## Getting set up

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install                                # installs the local gate
chmod +x .claude/hooks/pre-commit-check.sh        # one-time, if using the Claude Code hook
```

Python 3.10–3.13 are supported. The base install is `pydantic`-only; every heavier
capability is an optional extra (`[dspy]`, `[temporal]`, `[routing]`, `[mcp]`, `[remote]`,
`[otel]`), and `[all]`/`[dev]` pull them together for testing.

## Branches and commits

- Branch off `dev` as `<type>/p<phase>-<slug>`, where `type` is one of `feat`, `fix`,
  `docs`, `refactor`, `test`, `chore`, `security`, `perf`. Example: `feat/p2-superstep-kernel`.
- **Never commit directly to `dev`, `staging`, or `main`.** All three land changes via reviewed
  PRs. Work PRs target `dev`; GitHub proposes `main` by default, so retarget it.
- Changes promote forward only, one stage at a time: `dev` → `staging` → `main`. Never promote
  `dev` straight to `main`, and never cherry-pick a subset forward. The full model and the
  hotfix exception are in
  [`.claude/rules/branching-and-promotion.md`](.claude/rules/branching-and-promotion.md).
- Use [Conventional Commits](https://www.conventionalcommits.org/) with an accurate scope
  and a phase tag: `feat(core): implement Pregel kernel + reducers [P2]`.
- Every commit leaves the package green — build and tests pass.
- `git commit --no-verify`, force-pushing a shared branch, and rewriting history on `dev`,
  `staging`, or `main` are prohibited.
- `src/korchestrator/version.py` is edited only in a release PR — it is the single source
  of the version.

## The local gate (mirrors CI)

Before pushing, all of these must be green — never claim a check passed unless it ran:

```bash
ruff check src/korchestrator tests examples benchmarks
ruff format --check src/korchestrator tests examples benchmarks
mypy --strict src/korchestrator
pytest tests --cov=korchestrator --cov-report=term-missing
bash scripts/check_isolation.sh          # prints OK
python scripts/check_env_reads.py
python scripts/validate_version.py
```

`pre-commit` runs the fast subset automatically, and `.claude/hooks/pre-commit-check.sh`
additionally enforces the import-isolation gate and the engineering-log requirement.

## Tests

- A capability with no test is not delivered. New behaviour ships with a test that **fails
  without the change**; a bug fix ships a regression test that **failed on the old code**.
- No test may touch the network, call a real model, `sleep`, read the wall clock, or depend
  on shared developer state or test order. **MockLM** is the default gateway.
- Kernel, runtime, reducer, and serialization changes ship determinism tests (repeatability,
  reducer laws, replay, serde stability).
- Coverage floors (global 80%; `core/` and `models/` 95%) move up, never down. Do not lower
  a floor or add `# pragma: no cover` to make a build pass.

See `docs/specs/09-testing-and-quality.md` for the full policy.

## Architecture boundaries

- Dependencies point **inward**: `services → agents → core → interfaces/models`. Feature
  modules never import each other; they meet at `interfaces/` and `models/`.
- `core/` is framework-free — `pydantic` and stdlib only.
- Heavy dependencies (`dspy`, `temporalio`, `httpx`, OTel) are lazy-imported inside the one
  module that owns them, never at module top level.
- The environment is read only in `config/`. No hardcoded URLs, keys, models, or paths.
- Never import from `backend`, `apps`, `services` (external), or `frontend`.

See `docs/specs/03-architecture.md` and `.claude/rules/architecture-boundaries.md`.

## Pull requests

Your PR description states: the intent, the risk, the test evidence (which gates ran and
what they showed), the security and compatibility impact, any migrations, and the rollback.
A user-visible change lands with its `CHANGELOG.md` entry **in the same PR**. Any `src/`
change lands with a ten-field entry in `.claude/memory/ENGINEERING_LOG.md`.

A material or durable decision — a new dependency, a boundary change, a public-surface
change — is recorded as an ADR under `docs/adr/` before the code lands.

## Decisions and questions

If a change conflicts with a golden rule, is out of scope, or the spec is ambiguous: stop,
state the conflict, and raise it (an issue or a draft ADR) before writing code. When in
doubt, the specs win over the condensed rules.

By contributing, you agree that your contributions are licensed under the Apache License,
Version 2.0 (see `LICENSE`).
