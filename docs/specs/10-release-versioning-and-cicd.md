# 10 — Release, Versioning and CI/CD

**Purpose:** Define the compatibility contract the SDK makes to its users, how the version is
single-sourced and enforced, how changes are recorded, the automated pipelines that build, verify,
and publish artifacts, and the runbook a maintainer follows to cut a release.

**Read this when:** you are cutting a release, changing a public name, touching a workflow file,
deprecating something, or answering "what does deploying this repository mean?"

Related: [02-repository-structure.md](02-repository-structure.md) for `pyproject.toml` and the
`.github/` inventory, [04-public-api.md](04-public-api.md) for what the public surface contains, and
[09-testing-and-quality.md](09-testing-and-quality.md) for the gates the pipelines run.

---

## 1. Versioning policy

The SDK follows **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`). Development starts at `0.1.0`.

| Bump | When |
|---|---|
| **MAJOR** | A backward-incompatible change to the compatibility surface (§1.1) |
| **MINOR** | Backward-compatible new functionality; a new deprecation; a new optional extra |
| **PATCH** | Backward-compatible bug fixes, documentation, performance, and internal refactors |

### 1.1 The compatibility surface

Only the following is covered by the SemVer promise. **Everything else is internal and may change in
any release**, including patch releases.

| In the compatibility surface | Not in it |
|---|---|
| Names exported from `korchestrator.__all__` | Any name starting with `_` |
| The ARI ports: `IIdentityProvider`, `IExecutionSandbox`, `IModelGateway` | Concrete provider implementations' internals |
| The documented protocols: `IDurableRuntime`, `GraphRepository`, `BaseRouter`, `AUBConnector` | Module paths not re-exported from the package root |
| The documented Pydantic models and their field names, types, and serialized form | Undocumented model fields and private validators |
| The `KorchError` hierarchy and its error codes | Exception message wording |
| The remote contract: endpoint paths, request/response shapes, the auth scheme, status vocabulary | Retry timing, connection pooling, internal client structure |
| Recognised environment variables and `Settings` field names | Default values that are documented as tunable |
| The serialized on-the-wire form of state, tagged with its schema version | In-memory representation |

Adding a field with a default is backward-compatible. Removing a field, narrowing a type, changing a
default that alters behaviour, or renaming anything in the table's left column is breaking.

### 1.2 The 0.x caveat — stated plainly

> **While the version is `0.x`, a MINOR release may contain breaking changes.**

This is a deliberate, published exception to the usual SemVer reading, and it MUST appear verbatim in
three places: the `README.md` install section, the top of `CHANGELOG.md`, and the documentation
site's versioning page. It exists because the public surface is still being validated by real
integrators; freezing it prematurely would force either a `1.0` we cannot honour or a stream of major
bumps that communicate nothing.

Constraints that hold **even during 0.x**:

- A breaking change still requires an ADR, a CHANGELOG entry under `### Removed` or `### Changed`, and
  a migration note.
- A breaking change still uses the deprecation path (§2) **when it is possible to do so**. Skipping
  the overlap period requires the ADR to say why.
- PATCH releases are **never** breaking, at any version.

From `1.0.0` onward the compatibility policy applies without exception, and the 0.x caveat is removed
from all three locations in the release PR that ships `1.0.0`.

### 1.3 Supported Python versions

The SDK supports **Python 3.10, 3.11, 3.12, and 3.13** (`requires-python = ">=3.10"`), and CI tests
every one of them. Dropping a Python version is a **MINOR** bump while `0.x` and a **MAJOR** bump
thereafter; either way it requires an ADR and a CHANGELOG entry, and it may only follow that
version's upstream end-of-life. Adding a newly released Python version is a MINOR bump.

---

## 2. Deprecation policy

Nothing in the compatibility surface is removed without first being deprecated.

| Requirement | Detail |
|---|---|
| Warning | The deprecated name emits a `DeprecationWarning` on use, naming its replacement and its removal version |
| Overlap | It remains functional for **at least one full MINOR release** after the release that deprecated it |
| Documentation | The docstring gains a `.. deprecated::` note; `docs/migration.md` gains a section with a before/after example |
| CHANGELOG | An entry under `### Deprecated` in the release that introduces the deprecation, and under `### Removed` in the release that removes it |
| Removal | Only in a release whose bump rule permits it (MAJOR, or MINOR while `0.x`) |
| Telemetry | Where practical, the warning is countable so adoption of the replacement can be observed before removal |

A deprecation MUST NOT change behaviour. The deprecated path keeps working exactly as before until
it is removed; a deprecation that also alters semantics is a breaking change wearing a warning.

### 2.1 Worked example — deprecating a public name

Suppose `Swarm.add_agent()` is being renamed to `Swarm.add()`. Released in `0.4.0`, removed in
`0.6.0`.

```python
# src/korchestrator/services/swarm.py
import warnings
from typing import Self

from korchestrator.models.agent import AgentConfig


class Swarm:
    """A typed, explicitly constructed agent swarm."""

    def add(self, agent: AgentConfig) -> Self:
        """Add an agent to the swarm.

        Args:
            agent: The agent configuration to add.

        Returns:
            This swarm, to allow chaining.

        Example:
            >>> from korchestrator import Agent, Swarm
            >>> swarm = Swarm(objective="Summarize the design").add(Agent(id="lead"))
            >>> swarm.size
            1
        """
        self._agents[agent.id] = agent
        return self

    def add_agent(self, agent: AgentConfig) -> Self:
        """Add an agent to the swarm.

        .. deprecated:: 0.4.0
            Use :meth:`Swarm.add` instead. ``add_agent`` will be removed in 0.6.0.
        """
        warnings.warn(
            "Swarm.add_agent() is deprecated and will be removed in 0.6.0; use Swarm.add().",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.add(agent)
```

The accompanying test asserts both the warning and the preserved behaviour:

```python
def test_add_agent_warns_and_delegates(lead_agent):
    swarm = Swarm(objective="Summarize the design")
    with pytest.warns(DeprecationWarning, match="removed in 0.6.0"):
        swarm.add_agent(lead_agent)
    assert swarm.size == 1
```

`filterwarnings` in `pyproject.toml` turns warnings into errors except for the SDK's own
`DeprecationWarning`s, so an accidental internal call to a deprecated path surfaces immediately in
the suite.

CHANGELOG in `0.4.0`:

```markdown
### Deprecated
- `Swarm.add_agent()` is deprecated in favour of `Swarm.add()`. It continues to work
  unchanged and will be removed in 0.6.0. See docs/migration.md.
```

CHANGELOG in `0.6.0`:

```markdown
### Removed
- `Swarm.add_agent()`, deprecated since 0.4.0. Use `Swarm.add()`.
```

---

## 3. Version single-sourcing

**`src/korchestrator/version.py` is the single source of truth.** Everything else derives from it.

```python
# src/korchestrator/version.py
"""The single authoritative version of the Korchestrator SDK.

Never edit this file outside a release PR. Package metadata, ``__version__``,
the documentation site, and the release tag all derive from this value, and CI
fails if any of them disagree.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

| Consumer | How it derives |
|---|---|
| `pyproject.toml` | `dynamic = ["version"]` with `[tool.hatch.version] path = "src/korchestrator/version.py"` — hatchling reads it at build time |
| `korchestrator.__version__` | Re-exported from `version.py` in `__init__.py` |
| Installed distribution metadata | Produced by hatchling from the same read |
| Documentation site | Injected from the installed package at build time; never typed into a Markdown file |
| Git tag | `vX.Y.Z` must equal the value in `version.py` on the tagged commit |

Editing `version.py` is denied by `.claude/settings.json` (`Edit(src/korchestrator/version.py)` is in
the `deny` list). A release PR is the only context in which the deny is lifted, deliberately, by a
maintainer.

### 3.1 The `version-validate` gate

```python
#!/usr/bin/env python3
"""Assert the version agrees everywhere. Exits non-zero on disagreement."""

from __future__ import annotations

import os
import pathlib
import re
import sys
from importlib.metadata import PackageNotFoundError, version as dist_version

SOURCE = pathlib.Path("src/korchestrator/version.py")
SEMVER = re.compile(r'^__version__\s*=\s*"(?P<v>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?)"$', re.M)


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    match = SEMVER.search(text)
    if match is None:
        print(f"FAIL: no valid __version__ assignment found in {SOURCE}", file=sys.stderr)
        return 1
    source_version = match.group("v")

    failures: list[str] = []

    # 1. Installed distribution metadata must match (skipped when not installed).
    try:
        installed = dist_version("korchestrator")
    except PackageNotFoundError:
        print("note: korchestrator is not installed; skipping metadata comparison")
    else:
        if installed != source_version:
            failures.append(f"distribution metadata {installed!r} != version.py {source_version!r}")

    # 2. On a tag build, the tag must match.
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/"):
        tag = ref.removeprefix("refs/tags/")
        if tag != f"v{source_version}":
            failures.append(f"git tag {tag!r} != v{source_version}")

    # 3. The CHANGELOG must contain a released section for this version.
    changelog = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{source_version}]" not in changelog:
        failures.append(f"CHANGELOG.md has no '## [{source_version}]' section")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"version-validate OK: {source_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The gate runs on every PR and again on the tag build, where check 2 becomes live.

---

## 4. CHANGELOG

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) with **ISO dates**
(`YYYY-MM-DD`). Sections, in order: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

**Every user-visible change lands with its CHANGELOG entry in the same PR.** Not in a follow-up, not
batched at release time. A PR that changes public behaviour without a changelog entry fails review.
Internal refactors with no observable effect need no entry — the engineering log covers those.

Entries are written for the person upgrading: what changed, what they must do, where to read more.
Not "refactored the router" but "explicit routing now falls back to the configured default model when
the mapping has no entry, instead of raising".

```markdown
# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **0.x notice.** While the version is `0.x`, a MINOR release may contain breaking
> changes. PATCH releases are never breaking. See docs/versioning.md.

## [Unreleased]

## [0.2.0] - 2026-03-14

### Added
- `Swarm.edges()` accepts an adjacency mapping in addition to an edge list, so a
  topology can be declared in one expression (#118).
- New `[mcp]` extra exposing `korchestrator.mcp.MCPClient` for mounting MCP tool
  servers (#124).

### Changed
- **Breaking (0.x).** `Korch.run()` returns `RunResult` instead of `str`. The previous
  behaviour is available as `RunResult.final_answer`. Migration: append
  `.final_answer` at the call site. See docs/migration.md#0-2-0 (#121).

### Deprecated
- `Swarm.add_agent()` in favour of `Swarm.add()`. Removal in 0.4.0 (#119).

### Fixed
- The barrier applied `Append` reducers in agent-completion order rather than a
  canonical order, so a run could produce a differently ordered message list on
  repeat. Updates are now folded in agent-id order (#126).

### Security
- Credentials passed to `KorchestratorClient` are no longer included in the
  repr of the client object (#129).

[Unreleased]: https://github.com/kendralabs/korch-sdk/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kendralabs/korch-sdk/compare/v0.1.0...v0.2.0
```

---

## 5. The CI pipeline

| Stage | Job | Runs on | Blocking |
|---|---|---|---|
| 1 | Lint and format (`ruff check`, `ruff format --check`) | Push, PR | Yes |
| 2 | Types (`mypy --strict`) | Push, PR | Yes |
| 3 | Tests + coverage across Python 3.10–3.13 | Push, PR | Yes |
| 4 | Base-install kernel suite (no extras) | Push, PR | Yes |
| 5 | Security: `bandit`, `pip-audit`, `gitleaks` | Push, PR | Yes |
| 6 | Isolation gate, env-read confinement, version-validate | Push, PR | Yes |
| 7 | Build wheel + sdist | Push, PR | Yes |
| 8 | Clean-environment install smoke of the built wheel | Push, PR | Yes |
| 9 | Docs build (`mkdocs build --strict`) | Push, PR | Yes |
| 10 | Examples execute under MockLM | PR | Yes |
| 11 | Benchmarks | Manual dispatch, release branches | No |

There is **no backend job, no frontend job, no container build, no npm publish, and no deployment
job** anywhere in this pipeline. Their absence is a design requirement, not an omission.

### 5.1 `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
  workflow_dispatch:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

env:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"
  PYTHONHASHSEED: "0"

jobs:
  static:
    name: Lint, format, types, gates
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install -e ".[dev]"
      - name: Lint
        run: ruff check src/korchestrator tests examples benchmarks
      - name: Format
        run: ruff format --check src/korchestrator tests examples benchmarks
      - name: Types
        run: mypy --strict src/korchestrator
      - name: Import-isolation gate
        run: bash scripts/check_isolation.sh
      - name: Environment reads confined to config/
        run: python scripts/check_env_reads.py
      - name: Version single-sourcing
        run: python scripts/validate_version.py

  test:
    name: Tests (py${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - run: python -m pip install -e ".[dev]"
      - name: Run test suite with coverage
        run: pytest tests --cov=korchestrator --cov-report=term-missing --cov-report=xml
      - name: Enforce per-package coverage floors
        run: |
          coverage report --include="src/korchestrator/core/*" --fail-under=95
          coverage report --include="src/korchestrator/models/*" --fail-under=95

  base-install:
    name: Kernel suite on a pydantic-only install
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install with no extras
        run: python -m pip install . pytest pytest-asyncio
      - name: Assert optional dependencies are absent
        run: |
          python - <<'PY'
          import importlib.util, sys
          forbidden = ["dspy", "temporalio", "httpx", "mcp", "opentelemetry"]
          present = [m for m in forbidden if importlib.util.find_spec(m) is not None]
          if present:
              sys.exit(f"optional dependencies leaked into the base install: {present}")
          print("base install is clean")
          PY
      - name: Assert importing the package pulls in no optional dependency
        run: |
          python - <<'PY'
          import sys
          import korchestrator  # noqa: F401
          leaked = [m for m in ("dspy", "temporalio", "httpx", "mcp") if m in sys.modules]
          if leaked:
              sys.exit(f"import korchestrator eagerly imported: {leaked}")
          print("import graph is lazy")
          PY
      - name: Kernel and smoke tests
        run: pytest tests/unit/core tests/unit/models tests/smoke

  security:
    name: Security scans
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install -e ".[dev]"
      - name: Static analysis
        run: bandit -c pyproject.toml -r src/korchestrator
      - name: Dependency audit
        run: pip-audit --strict
      - name: Secret scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  build:
    name: Build and verify the artifact
    runs-on: ubuntu-latest
    needs: [static, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install build
      - name: Build wheel and sdist
        run: python -m build
      - name: Install the built wheel in a clean environment and smoke-test it
        run: |
          python -m venv /tmp/clean
          /tmp/clean/bin/python -m pip install --upgrade pip
          /tmp/clean/bin/python -m pip install dist/*.whl
          /tmp/clean/bin/python -c "import korchestrator; print(korchestrator.__version__)"
          /tmp/clean/bin/python -c "
          from korchestrator import Korch
          print(Korch().run('Summarize durable agent execution').final_answer)
          "
      - name: Verify py.typed is present in the wheel
        run: python -m zipfile -l dist/*.whl | grep -q "korchestrator/py.typed"
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  examples:
    name: Examples run offline
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    env:
      MOCK_LLM: "true"
      KORCH_RUNTIME: local
      PERSISTENCE_BACKEND: none
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install -e ".[all]"
      - run: for f in examples/*.py; do echo "== $f"; python "$f"; done

  docs:
    name: Docs build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install -e ".[dev]"
      - run: mkdocs build --strict
```

---

## 6. `.github/workflows/release.yml`

Tag-triggered. Publishes to PyPI via **Trusted Publishing** (OIDC) — no long-lived API token is
stored in this repository.

```yaml
name: Release

on:
  push:
    tags: ["v[0-9]+.[0-9]+.[0-9]+"]

permissions:
  contents: read

jobs:
  build:
    name: Build, verify, and attest
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
      attestations: write
    outputs:
      version: ${{ steps.version.outputs.value }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - run: python -m pip install build

      - name: Version must match the tag
        id: version
        run: |
          python scripts/validate_version.py
          value=$(python -c "import re,pathlib; \
            print(re.search(r'__version__ = \"([^\"]+)\"', \
            pathlib.Path('src/korchestrator/version.py').read_text()).group(1))")
          echo "value=$value" >> "$GITHUB_OUTPUT"

      - name: Build wheel and sdist
        run: python -m build

      # Verify the ARTIFACT, never the source tree. This is the check that catches
      # packaging defects a source-tree test can never see.
      - name: Verify the built wheel in a clean environment
        run: |
          python -m venv /tmp/verify
          /tmp/verify/bin/python -m pip install --upgrade pip
          /tmp/verify/bin/python -m pip install dist/*.whl
          cd /tmp   # leave the source tree so imports cannot resolve locally
          /tmp/verify/bin/python -c "
          import korchestrator
          assert korchestrator.__version__ == '${{ steps.version.outputs.value }}', \
              korchestrator.__version__
          from korchestrator import Korch
          print(Korch().run('Summarize durable agent execution').final_answer)
          print('artifact verified:', korchestrator.__version__)
          "

      - name: Verify the sdist builds a wheel
        run: |
          python -m venv /tmp/sdist
          /tmp/sdist/bin/python -m pip install --upgrade pip build
          /tmp/sdist/bin/python -m pip install dist/*.tar.gz

      - name: Generate SBOM (CycloneDX)
        run: |
          python -m pip install cyclonedx-bom
          cyclonedx-py environment --output-format json --outfile dist/sbom.cdx.json

      - name: Generate checksums
        run: |
          cd dist
          sha256sum ./*.whl ./*.tar.gz ./sbom.cdx.json > SHA256SUMS
          cat SHA256SUMS

      - name: Attest build provenance
        uses: actions/attest-build-provenance@v1
        with:
          subject-path: "dist/*.whl,dist/*.tar.gz"

      - uses: actions/upload-artifact@v4
        with:
          name: release-dist
          path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/korchestrator
    permissions:
      id-token: write   # Trusted Publishing (OIDC); no API token is stored
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: release-dist
          path: dist/
      - name: Remove non-distribution files before upload
        run: rm -f dist/SHA256SUMS dist/sbom.cdx.json
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          attestations: true

  github-release:
    name: Publish the GitHub release
    needs: [build, publish]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: release-dist
          path: dist/
      - name: Extract the CHANGELOG section for this version
        run: |
          awk -v v="${{ needs.build.outputs.version }}" '
            $0 ~ "^## \\["v"\\]" {p=1; next}
            p && /^## \[/ {exit}
            p {print}
          ' CHANGELOG.md > release-notes.md
          test -s release-notes.md || { echo "no CHANGELOG section found"; exit 1; }
      - uses: softprops/action-gh-release@v2
        with:
          body_path: release-notes.md
          files: |
            dist/*.whl
            dist/*.tar.gz
            dist/sbom.cdx.json
            dist/SHA256SUMS
          fail_on_unmatched_files: true

  verify-published:
    name: Install from PyPI
    needs: publish
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install the published distribution and import it
        run: |
          for attempt in 1 2 3 4 5; do
            if python -m pip install "korchestrator==${{ needs.build.outputs.version }}"; then
              break
            fi
            echo "index not ready yet (attempt $attempt)"
            [ "$attempt" -lt 5 ] || exit 1
          done
          python -c "import korchestrator; print(korchestrator.__version__)"

  deploy-docs:
    name: Deploy documentation for the release
    needs: publish
    uses: ./.github/workflows/docs.yml
    permissions:
      contents: read
      pages: write
      id-token: write
```

> **TypeScript client.** When the deferred TypeScript client is approved, it adds a sibling `npm`
> publish job here, gated on its own tag prefix and its own SemVer line. It is not present in the
> initial pipeline, and no job in this repository publishes to npm today.

---

## 7. `.github/workflows/docs.yml`

```yaml
name: Docs

on:
  push:
    branches: [main]
    paths: ["docs/**", "mkdocs.yml", "src/korchestrator/**", ".github/workflows/docs.yml"]
  workflow_call:
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    name: Build the documentation site
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install -e ".[dev]"
      - name: Build (strict — broken links and nav errors fail)
        run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/

  deploy:
    name: Deploy to GitHub Pages
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

---

## 8. Branching and commits

| Item | Rule |
|---|---|
| `main` | Released state only. Every commit corresponds to a tagged release. Protected; no direct pushes. |
| `develop` | Integration branch. Protected; no direct pushes. |
| Work branches | `<type>/p<phase>-<slug>` off `develop`, where type ∈ `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`, `perf`. Example: `feat/p2-pregel-kernel`. Short-lived. |
| Merges | Work branch → `develop` via reviewed PR. Release PRs go `develop` → `main`. |
| Commits | Conventional Commits with an accurate scope and a phase tag: `feat(core): implement Pregel kernel + reducers [P2]` |
| Green rule | Every commit leaves the package green — build and tests pass |
| Bypasses | `git commit --no-verify`, force-pushing a shared branch, and rewriting history on `main` or `develop` are prohibited |

---

## 9. Release runbook

Follow in order. Do not skip a step because a previous release made it look routine.

1. **Confirm readiness.** `develop` is green on the full CI matrix. Every change intended for this
   release is merged. No blocking gate is suppressed, and no security suppression has expired.
2. **Decide the bump.** Apply §1.1 to the diff since the last tag. If the surface changed, the ADR
   justifying it already exists — if it does not, stop and write it before continuing.
3. **Open the release PR** `chore/release-vX.Y.Z` into `main`, containing exactly two kinds of
   change: the version bump in `src/korchestrator/version.py`, and the CHANGELOG edit moving
   `Unreleased` content into a dated `## [X.Y.Z] - YYYY-MM-DD` section with updated compare links.
   Nothing else belongs in a release PR.
4. **Verify the migration story.** For every entry under `Changed`, `Deprecated`, or `Removed`,
   confirm `docs/migration.md` has a section with a before/after example.
5. **Green CI.** Every blocking gate in §5 must pass on the release PR, including `version-validate`,
   the base-install kernel suite, and the clean-environment install of the built wheel.
6. **Review and merge.** At least one qualified approval. Merge into `main`.
7. **Tag.** Create a **signed, annotated** tag on the merge commit:
   ```bash
   git checkout main && git pull --ff-only
   git tag -s "v0.2.0" -m "korchestrator 0.2.0"
   git push origin "v0.2.0"
   ```
   The tag must equal `v` + the value in `version.py`; `release.yml` fails if it does not.
8. **Watch the release workflow.** It builds, verifies the built artifact in a clean environment
   outside the source tree, generates the SBOM and checksums, attests provenance, publishes to PyPI
   via Trusted Publishing, publishes the GitHub release with notes drawn from the CHANGELOG, verifies
   an install from PyPI, and deploys the docs.
9. **Verify independently.** On a machine that is not the CI runner:
   ```bash
   python -m venv /tmp/rc && /tmp/rc/bin/pip install "korchestrator==0.2.0"
   /tmp/rc/bin/python -c "import korchestrator; print(korchestrator.__version__)"
   /tmp/rc/bin/python -c "from korchestrator import Korch; print(Korch().run('Summarize durable agent execution').final_answer)"
   ```
   Confirm the documentation site shows the new version and that the release page lists the wheel,
   sdist, SBOM, and `SHA256SUMS`.
10. **Merge back and announce.** Merge `main` into `develop` so the version bump is not lost. Publish
    the announcement, stating supported Python versions, public API changes, migrations, and known
    limitations.
11. **Update the running record.** Add the release entry to `.claude/memory/ENGINEERING_LOG.md` and
    reset `.claude/memory/PROJECT_STATE.md` to the next phase.

### 9.1 Releases are immutable

A published version is **never overwritten, re-tagged, or deleted**. If a release is defective:

- Fix forward with a **new patch version**. `0.2.1` supersedes `0.2.0`; `0.2.0` stays on the index.
- **Yank** the bad version at the registry only if it is actively harmful (a security defect, data
  loss, or a wholly broken artifact). Yanking hides it from resolution for new installs while
  leaving existing pins working — it is not deletion.
- Record what happened in the CHANGELOG entry for the superseding release, and in an ADR if the
  cause was a process gap rather than a code defect.

Never move a tag. Consumers, mirrors, SBOM references, and provenance attestations all assume tags
are permanent.

---

## 10. What "deployment" means here

**Deployment for this repository means publishing artifacts, not running a service.** There is no
server, container, or environment operated from this repository. A request to deploy a server from
this repository is out of scope; say so and stop.

| Deliverable | Where it lands |
|---|---|
| Immutable wheel and sdist | PyPI, published on a `vX.Y.Z` tag via Trusted Publishing |
| SBOM, checksums, provenance attestation | Attached to the GitHub release |
| Documentation site for the released version | GitHub Pages |
| Git tag and release notes | This repository |

**What consumers install:**

```bash
pip install korchestrator                        # kernel, local runtime, MockLM — no infrastructure
pip install "korchestrator[dspy]"                # DSPy reasoning agents
pip install "korchestrator[temporal]"            # durable execution on Temporal
pip install "korchestrator[remote]"              # the KorchestratorClient
pip install "korchestrator[all]"                 # everything
```

**Infrastructure the SDK may connect to** — a Temporal cluster, Postgres or Neo4j, a model gateway,
MCP servers — is **provisioned and operated by the consumer**, selected by configuration at runtime
behind an interface, and **always optional**. The default install runs with none of it: local
runtime, MockLM gateway, in-memory persistence. This repository ships no manifests, charts, or
infrastructure-as-code for any of it (see
[02-repository-structure.md](02-repository-structure.md) §7).

A hosted backend that consumes the published SDK is out of scope. Its hosting, authentication,
tenancy, scaling, and infrastructure live in that service's own repository and are never a build,
test, or release dependency of this one.

### 10.1 The remote contract as a compatibility surface

The `[remote]` extra speaks to a hosted engine. Its contract is part of the compatibility surface:
the endpoint paths, the request and response shapes, the status vocabulary, and the auth scheme —
`Authorization: Bearer <api-key | KIAM JWT>` with scopes `korchestrator:read`,
`korchestrator:write`, and `korchestrator:admin`. Changing any of these follows the same SemVer and
deprecation rules as changing a Python signature. See [04-public-api.md](04-public-api.md).

Credentials are never logged, never written to disk by the SDK, and never included in an object
repr or an exception message.

---

## 11. Artifact integrity

| Property | How it is achieved | Verified by |
|---|---|---|
| Type information ships | `py.typed` is included in the wheel via the hatchling package config | CI asserts the path exists inside the built wheel |
| The artifact actually works | The built wheel is installed in a clean venv **outside the source tree** and imported, and the Tier-1 one-liner is executed | `build` job in CI; repeated in `release.yml` |
| The sdist is buildable | The sdist is installed in a separate clean venv, forcing a build from source | `release.yml` |
| Contents are enumerable | A CycloneDX SBOM is generated per release and attached to the GitHub release | `release.yml` |
| Contents are verifiable | `SHA256SUMS` covers the wheel, sdist, and SBOM | `release.yml`; consumers verify with `sha256sum -c` |
| Provenance is attestable | GitHub build provenance attestation over the distributions, plus PyPI attestations from Trusted Publishing | `actions/attest-build-provenance`; verifiable with `gh attestation verify` |
| No long-lived publish credential exists | PyPI Trusted Publishing (OIDC) — the publish job holds `id-token: write` and no stored token | Repository secrets contain no PyPI token |
| Least privilege | The workflow default is `permissions: contents: read`; elevated permissions are granted per job, never workflow-wide | Review of workflow files |

Signing is applied where the registry supports it; PyPI attestations produced by Trusted Publishing
are the current mechanism, and no additional key material is stored in this repository.
