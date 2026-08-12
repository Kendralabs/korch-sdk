"""Unit tests for the release-cutting automation (spec 10 §9, ADR 0020).

Exercises the pure transforms only — ``bump_version``, ``repo_slug_from_remote_url``, and
``render_changelog`` — none of which touch git, the network, or the filesystem, matching the
convention set by ``tests/unit/test_benchmark_regression_check.py`` for testing ``scripts/``.
"""

from __future__ import annotations

from datetime import date

import pytest
from scripts.cut_release import (
    ReleaseScriptError,
    bump_version,
    render_changelog,
    repo_slug_from_remote_url,
)


class TestBumpVersion:
    def test_patch_bump_increments_the_last_component(self) -> None:
        assert bump_version("0.1.0", "patch") == "0.1.1"

    def test_minor_bump_resets_patch(self) -> None:
        assert bump_version("0.1.5", "minor") == "0.2.0"

    def test_major_bump_resets_minor_and_patch(self) -> None:
        assert bump_version("0.9.3", "major") == "1.0.0"

    def test_an_unknown_bump_kind_is_rejected(self) -> None:
        with pytest.raises(ReleaseScriptError, match="unknown bump kind"):
            bump_version("0.1.0", "banana")

    def test_a_non_plain_semver_current_version_is_rejected(self) -> None:
        with pytest.raises(ReleaseScriptError, match="non-plain-semver"):
            bump_version("0.1.0-rc1", "patch")


class TestRepoSlugFromRemoteUrl:
    def test_https_url_with_dot_git_suffix(self) -> None:
        assert repo_slug_from_remote_url("https://github.com/Kendralabs/korch-sdk.git") == (
            "Kendralabs/korch-sdk"
        )

    def test_https_url_without_dot_git_suffix(self) -> None:
        assert repo_slug_from_remote_url("https://github.com/Kendralabs/korch-sdk") == (
            "Kendralabs/korch-sdk"
        )

    def test_ssh_url(self) -> None:
        assert repo_slug_from_remote_url("git@github.com:Kendralabs/korch-sdk.git") == (
            "Kendralabs/korch-sdk"
        )

    def test_a_non_github_remote_is_rejected(self) -> None:
        with pytest.raises(ReleaseScriptError, match="cannot parse"):
            repo_slug_from_remote_url("https://gitlab.com/Kendralabs/korch-sdk.git")


class TestRenderChangelog:
    # A body paragraph directly under the header, no blank line before it — matching the real
    # CHANGELOG.md's shape exactly. Regression fixture for the bug where a greedy `\s*` in the
    # header regex consumed the header's own trailing newline, collapsing the blank line that's
    # supposed to separate the new dated header from this paragraph.
    FIRST_RELEASE_CHANGELOG = """# Changelog

## [0.1.0] - Unreleased

The first development line, assembled phase by phase.

### Added
- The kernel.

[0.1.0]: https://github.com/Kendralabs/korch-sdk/releases/tag/v0.1.0
"""

    STEADY_STATE_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- `Swarm.edges()` accepts an adjacency mapping.

## [0.1.0] - 2026-08-12

### Added
- The kernel.

[0.1.0]: https://github.com/Kendralabs/korch-sdk/releases/tag/v0.1.0
"""

    def test_first_release_dates_the_lone_section_and_opens_unreleased(self) -> None:
        out = render_changelog(
            self.FIRST_RELEASE_CHANGELOG,
            version="0.1.0",
            repo_slug="Kendralabs/korch-sdk",
            release_date=date(2026, 8, 12),
            existing_tags=[],
        )
        assert "## [Unreleased]\n\n## [0.1.0] - 2026-08-12" in out
        assert "### Added\n- The kernel." in out

    def test_the_blank_line_after_the_dated_header_survives(self) -> None:
        out = render_changelog(
            self.FIRST_RELEASE_CHANGELOG,
            version="0.1.0",
            repo_slug="Kendralabs/korch-sdk",
            release_date=date(2026, 8, 12),
            existing_tags=[],
        )
        # Regression: a greedy `\s*` in the header regex used to eat the header's own trailing
        # newline, collapsing this blank line so the body paragraph ran directly into the header.
        assert "## [0.1.0] - 2026-08-12\n\nThe first development line" in out

    def test_first_release_uses_a_releases_tag_link_with_no_prior_tag(self) -> None:
        out = render_changelog(
            self.FIRST_RELEASE_CHANGELOG,
            version="0.1.0",
            repo_slug="Kendralabs/korch-sdk",
            release_date=date(2026, 8, 12),
            existing_tags=[],
        )
        assert "[0.1.0]: https://github.com/Kendralabs/korch-sdk/releases/tag/v0.1.0" in out
        assert "[Unreleased]: https://github.com/Kendralabs/korch-sdk/compare/v0.1.0...HEAD" in out

    def test_steady_state_dates_the_unreleased_header_and_keeps_prior_sections(self) -> None:
        out = render_changelog(
            self.STEADY_STATE_CHANGELOG,
            version="0.2.0",
            repo_slug="Kendralabs/korch-sdk",
            release_date=date(2026, 9, 1),
            existing_tags=["v0.1.0"],
        )
        assert "## [Unreleased]\n\n## [0.2.0] - 2026-09-01" in out
        assert "## [0.1.0] - 2026-08-12" in out
        assert "Swarm.edges()" in out

    def test_steady_state_compare_link_uses_the_latest_prior_tag(self) -> None:
        out = render_changelog(
            self.STEADY_STATE_CHANGELOG,
            version="0.2.0",
            repo_slug="Kendralabs/korch-sdk",
            release_date=date(2026, 9, 1),
            existing_tags=["v0.1.0"],
        )
        assert "[0.2.0]: https://github.com/Kendralabs/korch-sdk/compare/v0.1.0...v0.2.0" in out
        assert "[Unreleased]: https://github.com/Kendralabs/korch-sdk/compare/v0.2.0...HEAD" in out

    def test_the_latest_of_several_prior_tags_is_used_for_the_compare_link(self) -> None:
        out = render_changelog(
            self.STEADY_STATE_CHANGELOG,
            version="0.2.0",
            repo_slug="Kendralabs/korch-sdk",
            release_date=date(2026, 9, 1),
            existing_tags=["v0.1.0", "v0.1.1", "v0.1.10", "v0.1.2"],
        )
        # Numeric SemVer order, not lexical: 0.1.10 sorts after 0.1.2.
        assert "[0.2.0]: https://github.com/Kendralabs/korch-sdk/compare/v0.1.10...v0.2.0" in out

    def test_a_version_matching_neither_section_shape_is_rejected(self) -> None:
        with pytest.raises(ReleaseScriptError, match="no '## \\[0\\.9\\.0\\]"):
            render_changelog(
                self.FIRST_RELEASE_CHANGELOG,
                version="0.9.0",
                repo_slug="Kendralabs/korch-sdk",
                release_date=date(2026, 8, 12),
                existing_tags=[],
            )
