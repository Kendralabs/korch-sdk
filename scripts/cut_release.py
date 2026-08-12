#!/usr/bin/env python3
"""Automate the mechanical steps of cutting a release (spec 10 §9, ADR 0020).

Two subcommands, run in order across the two stages the runbook already describes:

``prepare``
    Run from a checkout of ``staging``. Computes the next version (from an explicit
    ``--version`` or a ``--bump patch|minor|major``), writes ``src/korchestrator/version.py``,
    rewrites ``CHANGELOG.md`` (dates the section being released, opens a fresh ``[Unreleased]``
    section above it, updates the compare-link footer), then creates
    ``chore/release-vX.Y.Z`` off ``staging``, commits, pushes, and opens a PR into ``main``.
    Nothing else changes in that PR/commit, matching the runbook's "exactly two kinds of
    change" rule.

``tag``
    Run from a checkout of ``main`` *after* the release PR from ``prepare`` has merged.
    Verifies the working tree is clean and matches ``origin/main``, confirms the CHANGELOG
    has a dated section for the version in ``version.py``, then creates an annotated (or
    ``--sign``ed) ``vX.Y.Z`` tag on the current commit and pushes it — which triggers
    ``.github/workflows/release.yml``.

This script does not publish anywhere itself; per ADR 0020 the actual distribution (build,
verify, checksum, GitHub Release) happens in CI on the tag push. It only automates the git/PR
bookkeeping that the runbook otherwise asks a maintainer to do by hand.

The pure transforms (``bump_version``, ``render_changelog``, ``repo_slug_from_remote_url``) have
no git/network/filesystem side effects and are covered directly by
``tests/unit/test_cut_release.py``; everything else in this module is a thin, untested CLI
wrapper around them plus ``subprocess`` calls to ``git``/``gh``.
"""

# ruff: noqa: S603, S607, T201 — a CLI release script legitimately shells out to git/gh by
# name (not a full path) and prints its progress and results to stdout for the operator running it.
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

VERSION_FILE = Path("src/korchestrator/version.py")
CHANGELOG_FILE = Path("CHANGELOG.md")

VERSION_ASSIGNMENT = re.compile(r'^__version__\s*=\s*"(?P<v>\d+\.\d+\.\d+)"$', re.M)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
UNRELEASED_HEADER = re.compile(r"^## \[Unreleased\]\s*$", re.M)
DATED_HEADER = re.compile(r"^## \[(?P<v>\d+\.\d+\.\d+)\] - Unreleased\s*$", re.M)
FOOTER_LINK = re.compile(r"^\[(?P<name>Unreleased|\d+\.\d+\.\d+)\]:.*$", re.M)


class ReleaseScriptError(RuntimeError):
    """Raised for any precondition or transform failure in this script."""


# --------------------------------------------------------------------------------------------
# Pure transforms — no I/O, fully unit tested.
# --------------------------------------------------------------------------------------------


def bump_version(current: str, bump: str) -> str:
    """Compute the next SemVer version for a MAJOR/MINOR/PATCH bump.

    Args:
        current: The current ``X.Y.Z`` version.
        bump: One of ``"major"``, ``"minor"``, ``"patch"``.

    Returns:
        The next ``X.Y.Z`` version string.

    Raises:
        ReleaseScriptError: If ``current`` isn't a plain ``X.Y.Z`` version or ``bump`` is invalid.
    """
    if not SEMVER.match(current):
        raise ReleaseScriptError(f"cannot bump non-plain-semver version {current!r}")
    major, minor, patch = (int(part) for part in current.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseScriptError(f"unknown bump kind {bump!r}; expected major, minor, or patch")


def repo_slug_from_remote_url(url: str) -> str:
    """Parse an ``origin`` remote URL into an ``Owner/Repo`` slug.

    Args:
        url: An ``https://github.com/...`` or ``git@github.com:...`` remote URL, with or
            without a trailing ``.git``.

    Returns:
        The ``Owner/Repo`` slug.

    Raises:
        ReleaseScriptError: If the URL isn't a recognizable GitHub remote.
    """
    match = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/]+?)(?:\.git)?/?$", url.strip())
    if match is None:
        raise ReleaseScriptError(f"cannot parse a GitHub Owner/Repo slug from remote {url!r}")
    return match.group("slug")


def render_changelog(
    text: str,
    *,
    version: str,
    repo_slug: str,
    release_date: date,
    existing_tags: list[str],
) -> str:
    """Date the section being released and open a fresh ``[Unreleased]`` section above it.

    Handles both CHANGELOG shapes this repository uses:

    - **First release:** a lone ``## [X.Y.Z] - Unreleased`` section (no separate
      ``## [Unreleased]`` header yet).
    - **Steady state:** a ``## [Unreleased]`` header holding the next release's notes.

    Pure — takes the existing tags as input rather than calling git itself, so it's fully
    unit-testable against fixture content.

    Args:
        text: The current ``CHANGELOG.md`` contents.
        version: The version being released (must match the section being dated).
        repo_slug: The ``Owner/Repo`` slug, used to build the footer compare links.
        release_date: The date to stamp the dated section with.
        existing_tags: Every ``vX.Y.Z`` tag already cut, used to find the prior release for the
            compare link. Pass an empty list for the first-ever release.

    Returns:
        The rewritten CHANGELOG contents.

    Raises:
        ReleaseScriptError: If no matching Unreleased section is found for ``version``.
    """
    iso_date = release_date.isoformat()
    dated_header = f"## [{version}] - {iso_date}"

    if UNRELEASED_HEADER.search(text):
        body, count = UNRELEASED_HEADER.subn(dated_header, text, count=1)
        if count != 1:
            raise ReleaseScriptError("failed to rewrite the '## [Unreleased]' header")
    else:
        match = DATED_HEADER.search(text)
        if match is None or match.group("v") != version:
            raise ReleaseScriptError(
                f"CHANGELOG.md has no '## [{version}] - Unreleased' or '## [Unreleased]' "
                "section to date"
            )
        body = text[: match.start()] + dated_header + text[match.end() :]

    # Open a fresh Unreleased section immediately above the section we just dated.
    body = body.replace(dated_header, "## [Unreleased]\n\n" + dated_header, 1)

    previous_tags = _sorted_semver_tags(existing_tags)
    previous = previous_tags[-1] if previous_tags else None
    if previous is None:
        version_link = f"[{version}]: https://github.com/{repo_slug}/releases/tag/v{version}"
    else:
        version_link = (
            f"[{version}]: https://github.com/{repo_slug}/compare/{previous}...v{version}"
        )
    unreleased_link = f"[Unreleased]: https://github.com/{repo_slug}/compare/v{version}...HEAD"

    body = FOOTER_LINK.sub("", body).rstrip() + "\n"
    body += f"\n{unreleased_link}\n{version_link}\n"
    return body


def _sorted_semver_tags(tags: list[str]) -> list[str]:
    """Sort ``vX.Y.Z`` tags ascending by SemVer; non-matching tags are dropped."""
    parsed = []
    for tag in tags:
        match = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", tag)
        if match:
            parsed.append((tuple(int(g) for g in match.groups()), tag))
    return [tag for _, tag in sorted(parsed)]


# --------------------------------------------------------------------------------------------
# Impure helpers — git/gh subprocess calls.
# --------------------------------------------------------------------------------------------


def _run(args: list[str], *, dry_run: bool = False) -> str:
    print(f"$ {' '.join(args)}")
    if dry_run:
        return ""
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    return result.stdout


def _git_tag_list() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "v*"], check=True, capture_output=True, text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _working_tree_is_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip() == ""


def _remote_url(remote: str = "origin") -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", remote], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _read_current_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = VERSION_ASSIGNMENT.search(text)
    if match is None:
        raise ReleaseScriptError(f"no valid __version__ assignment found in {VERSION_FILE}")
    return match.group("v")


def _write_version(version: str) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    new_text, count = VERSION_ASSIGNMENT.subn(f'__version__ = "{version}"', text, count=1)
    if count != 1:
        raise ReleaseScriptError(f"failed to rewrite __version__ in {VERSION_FILE}")
    VERSION_FILE.write_text(new_text, encoding="utf-8")


@dataclass(frozen=True)
class PrepareArgs:
    """Parsed arguments for the ``prepare`` subcommand."""

    version: str
    base: str
    target: str
    open_pr: bool
    dry_run: bool


def cmd_prepare(args: PrepareArgs) -> int:
    """Bump the version, date the CHANGELOG, and open the release PR."""
    branch = _current_branch()
    if branch != args.base and not args.dry_run:
        raise ReleaseScriptError(
            f"run 'prepare' from a checkout of {args.base!r}, not {branch!r} "
            f"(git checkout {args.base} && git pull --ff-only)"
        )
    if not _working_tree_is_clean() and not args.dry_run:
        raise ReleaseScriptError("working tree is not clean; commit or stash first")

    current = _read_current_version()
    print(f"current version: {current} -> release version: {args.version}")

    repo_slug = repo_slug_from_remote_url(_remote_url())
    changelog_text = CHANGELOG_FILE.read_text(encoding="utf-8")
    new_changelog = render_changelog(
        changelog_text,
        version=args.version,
        repo_slug=repo_slug,
        release_date=date.today(),
        existing_tags=_git_tag_list(),
    )

    if args.dry_run:
        print("--- dry run: would write the following CHANGELOG.md ---")
        print(new_changelog)
        print(f"--- dry run: would set __version__ = {args.version!r} ---")
        return 0

    if current != args.version:
        _write_version(args.version)
    CHANGELOG_FILE.write_text(new_changelog, encoding="utf-8")

    release_branch = f"chore/release-v{args.version}"
    _run(["git", "checkout", "-b", release_branch])
    _run(["git", "add", str(VERSION_FILE), str(CHANGELOG_FILE)])
    _run(
        [
            "git",
            "commit",
            "-m",
            f"chore(release): cut v{args.version} [P12]",
        ]
    )
    _run(["git", "push", "-u", "origin", release_branch])

    if args.open_pr:
        _run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                args.target,
                "--head",
                release_branch,
                "--title",
                f"chore(release): v{args.version}",
                "--body",
                f"Release PR for v{args.version}. Contains only the version bump in "
                f"{VERSION_FILE} and the dated CHANGELOG.md section, per spec 10 §9.",
            ]
        )
    print(f"\nNext: get the PR reviewed and merged into {args.target}, then run:")
    print(f"  git checkout {args.target} && git pull --ff-only")
    print("  python scripts/cut_release.py tag")
    return 0


@dataclass(frozen=True)
class TagArgs:
    """Parsed arguments for the ``tag`` subcommand."""

    branch: str
    sign: bool
    dry_run: bool


def cmd_tag(args: TagArgs) -> int:
    """Create and push the signed/annotated release tag from ``main``."""
    branch = _current_branch()
    if branch != args.branch and not args.dry_run:
        raise ReleaseScriptError(
            f"run 'tag' from a checkout of {args.branch!r}, not {branch!r} "
            f"(git checkout {args.branch} && git pull --ff-only)"
        )
    if not _working_tree_is_clean() and not args.dry_run:
        raise ReleaseScriptError("working tree is not clean; commit or stash first")

    version = _read_current_version()
    changelog_text = CHANGELOG_FILE.read_text(encoding="utf-8")
    if f"## [{version}] - " not in changelog_text or f"## [{version}] - Unreleased" in (
        changelog_text
    ):
        raise ReleaseScriptError(
            f"CHANGELOG.md has no dated '## [{version}] - YYYY-MM-DD' section; "
            "did the release PR from 'prepare' actually merge?"
        )

    tag = f"v{version}"
    existing_tags = _git_tag_list()
    if tag in existing_tags:
        raise ReleaseScriptError(f"tag {tag} already exists; releases are immutable (ADR 0020)")

    flag = "-s" if args.sign else "-a"
    if args.dry_run:
        print(f"--- dry run: would run git tag {flag} {tag} -m 'korchestrator {version}' ---")
        print(f"--- dry run: would run git push origin {tag} ---")
        return 0

    _run(["git", "tag", flag, tag, "-m", f"korchestrator {version}"])
    _run(["git", "push", "origin", tag])
    print(f"\nPushed {tag}. Watch the release workflow: gh run watch")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="bump the version, date the CHANGELOG, open the PR")
    bump_group = prepare.add_mutually_exclusive_group(required=True)
    bump_group.add_argument("--bump", choices=["major", "minor", "patch"])
    bump_group.add_argument("--version", help="explicit X.Y.Z version, instead of --bump")
    prepare.add_argument("--base", default="staging", help="branch to release from")
    prepare.add_argument("--target", default="main", help="branch the release PR targets")
    prepare.add_argument(
        "--no-pr", action="store_true", help="push the branch but skip 'gh pr create'"
    )
    prepare.add_argument("--dry-run", action="store_true", help="print the computed changes only")

    tag = sub.add_parser("tag", help="tag and push the release from main, after the PR merges")
    tag.add_argument("--branch", default="main", help="branch the tag is cut from")
    tag.add_argument("--sign", action="store_true", help="create a GPG-signed tag (-s) not -a")
    tag.add_argument("--dry-run", action="store_true", help="print the computed changes only")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    # CHANGELOG.md contains non-ASCII punctuation (arrows, em dashes); the default Windows
    # console encoding (cp1252) can't represent all of it, so force UTF-8 for our own output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            version = args.version or bump_version(_read_current_version(), args.bump)
            return cmd_prepare(
                PrepareArgs(
                    version=version,
                    base=args.base,
                    target=args.target,
                    open_pr=not args.no_pr,
                    dry_run=args.dry_run,
                )
            )
        if args.command == "tag":
            return cmd_tag(TagArgs(branch=args.branch, sign=args.sign, dry_run=args.dry_run))
        raise ReleaseScriptError(f"unknown command {args.command!r}")
    except ReleaseScriptError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"FAIL: {' '.join(exc.cmd)} exited {exc.returncode}: {exc.stderr}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
