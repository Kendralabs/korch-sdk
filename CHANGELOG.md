# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **0.x notice.** While the version is `0.x`, a MINOR release may contain breaking
> changes. PATCH releases are never breaking. See docs/versioning.md.

## [0.1.0] - Unreleased

The first development line. This version is being assembled phase by phase and has not
yet been published; the date is fixed when `0.1.0` is released (see the release runbook in
`docs/specs/10-release-versioning-and-cicd.md` §9).

### Added

- Self-contained `korchestrator` package skeleton: every module directory from the module
  catalogue, each with a layer-naming docstring and an explicit `__all__`; `py.typed`;
  and the single-source `version.py` pinned to `0.1.0`.
- Authoritative `pyproject.toml`: `hatchling` build backend with the version sourced
  dynamically from `version.py`, `requires-python >=3.10`, the `pydantic`-only core
  dependency, the full extras matrix, and the `ruff` / `mypy` / `pytest` / `coverage`
  configuration.
- Minimal typed `korchestrator.config.Settings` (`mock_llm`, `korch_runtime`,
  `persistence_backend`) with `Settings.from_env()`, the single place the package reads the
  environment. Built on `pydantic.BaseModel` to keep the base install `pydantic`-only
  (see ADR 0009).
- OSS-readiness files: Apache-2.0 `LICENSE`, `NOTICE`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue and pull-request templates, and
  `.editorconfig`.

[0.1.0]: https://github.com/kendralabs/korch-sdk/releases/tag/v0.1.0
