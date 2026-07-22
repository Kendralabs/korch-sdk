"""The public-surface guard (spec 04 §4.2) and the spec-04 usage examples as xfail-strict tests.

The golden snapshot fails the moment ``korchestrator.__all__`` changes. That is the design working:
update ``public_surface.json`` DELIBERATELY, in the same PR as a CHANGELOG entry and a version
decision. The xfail-strict tests execute the spec-04 tier examples; each becomes a real passing test
(and its marker must be removed) the moment its behaviour lands.
"""

from __future__ import annotations

import json
import pathlib

import pytest

import korchestrator

GOLDEN = pathlib.Path(__file__).parent / "public_surface.json"


def test_public_surface_is_unchanged() -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))["all"]
    assert sorted(korchestrator.__all__) == expected


def test_every_exported_name_is_importable() -> None:
    for name in korchestrator.__all__:
        assert hasattr(korchestrator, name), f"{name} is in __all__ but not importable"


def test_timeout_error_is_not_top_level_but_is_reachable() -> None:
    # Deliberately not re-exported at top level (would shadow the builtin under `import *`).
    assert "TimeoutError" not in korchestrator.__all__
    from korchestrator.exceptions import TimeoutError  # noqa: A004

    assert issubclass(TimeoutError, korchestrator.KorchError)


def test_tier1_one_liner() -> None:
    pytest.importorskip("dspy")  # reasoning requires the [dspy] extra (ADR 0013)
    from korchestrator import Korch

    result = Korch().run("Research durable agent execution and summarize the top 3")
    assert result.final_answer


def test_tier2_typed_swarm() -> None:
    pytest.importorskip("dspy")  # reasoning requires the [dspy] extra (ADR 0013)
    from korchestrator import Agent, Swarm

    swarm = (
        Swarm(objective="Review this PR for security and performance")
        .add(Agent(id="security", role="security-reviewer", model="claude-3.5-sonnet"))
        .add(Agent(id="perf", role="performance-reviewer", model="gpt-4o-mini"))
        .add(Agent(id="lead", role="review-lead"))
        .edges([("security", "lead"), ("perf", "lead")])
    )
    result = swarm.run(max_supersteps=5)
    assert result.final_answer


def test_tier3_kernel_direct_symbols_exist() -> None:
    # Landed in P2: the kernel is directly embeddable (spec 04 Tier 3).
    from korchestrator.core import AgentGraph, PregelRunner

    assert callable(PregelRunner)
    assert callable(AgentGraph)
