#!/usr/bin/env python3
"""Assert the version agrees everywhere. Exits non-zero on disagreement.

Single-sources the SemVer version from ``src/korchestrator/version.py`` and checks it against
the installed distribution metadata, the git tag on a tag build, and the CHANGELOG (spec 10
§3). Run on every PR and again on the tag build, where the tag check becomes live.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as dist_version

SOURCE = pathlib.Path("src/korchestrator/version.py")
SEMVER = re.compile(r'^__version__\s*=\s*"(?P<v>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?)"$', re.M)


def main() -> int:
    """Validate version single-sourcing; return a process exit code."""
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

    # 3. The CHANGELOG must contain a section for this version.
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
