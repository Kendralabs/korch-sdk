"""Unit tests for the lazy DSPy signatures (spec 05 §57, spec 11 P4, P4.5)."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from korchestrator.agents.signatures import (
    ArchitectSignature,
    InputField,
    OutputField,
    Signature,
    WorkerSignature,
    load_dspy,
)
from korchestrator.exceptions import MissingExtraError, ValidationError


class Summarize(Signature):
    """Summarize the document."""

    document: str = InputField(desc="the source text")
    summary: str = OutputField(desc="a one-sentence summary")


def test_declaring_a_signature_needs_no_dspy() -> None:
    # Declaration records fields without importing dspy; order and specs are preserved.
    names = [name for name, _, _ in Summarize.fields()]
    assert names == ["document", "summary"]
    kinds = [spec.kind for _, _, spec in Summarize.fields()]
    assert kinds == ["input", "output"]


def test_fields_are_inherited_subclass_first() -> None:
    class Extended(Summarize):
        """Summarize with a title."""

        title: str = OutputField(desc="a short title")

    names = [name for name, _, _ in Extended.fields()]
    assert names == ["title", "document", "summary"]


def test_subclass_field_overrides_the_base_declaration() -> None:
    class Base(Signature):
        """Base."""

        x: str = InputField(desc="base")

    class Sub(Base):
        """Sub."""

        x: str = OutputField(desc="override")

    # The subclass's field wins and appears once; the base's same-named field is skipped.
    assert [(name, spec.kind) for name, _, spec in Sub.fields()] == [("x", "output")]


def test_builtin_signatures_declare_their_fields() -> None:
    assert [n for n, _, _ in WorkerSignature.fields()] == [
        "role",
        "objective",
        "context",
        "answer",
        "is_final",
    ]
    assert [n for n, _, _ in ArchitectSignature.fields()] == [
        "objective",
        "intent",
        "difficulty",
        "roles",
        "rationale",
    ]


def test_load_dspy_raises_missing_extra_when_absent() -> None:
    # Force `import dspy` to fail regardless of whether the extra is installed here.
    with mock.patch.dict(sys.modules, {"dspy": None}), pytest.raises(MissingExtraError) as excinfo:
        load_dspy()
    assert "korchestrator[dspy]" in str(excinfo.value)


def test_to_dspy_raises_missing_extra_when_absent() -> None:
    with mock.patch.dict(sys.modules, {"dspy": None}), pytest.raises(MissingExtraError):
        Summarize.to_dspy()


def test_to_dspy_rejects_a_fieldless_signature() -> None:
    class Empty(Signature):
        """No fields."""

    with pytest.raises(ValidationError):
        Empty.to_dspy()


def test_to_dspy_materialises_a_real_signature() -> None:
    dspy = pytest.importorskip("dspy")
    compiled = Summarize.to_dspy()
    assert issubclass(compiled, dspy.Signature)
    assert list(compiled.model_fields.keys()) == ["document", "summary"]
    assert compiled.instructions.strip() == "Summarize the document."
