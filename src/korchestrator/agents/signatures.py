"""Cognitive layer (L2). Imports: exceptions, stdlib. dspy is lazy ([dspy] extra), never at top.

Declarative reasoning **signatures** that are authored without importing ``dspy`` and materialised
into a real ``dspy.Signature`` only when reasoning actually runs. This lets the base install (no
``[dspy]``) import the cognitive layer cleanly and raise an actionable ``MissingExtraError`` only
when a signature is compiled (spec 05 §57, spec 11 P4). A user declares a custom signature the same
way::

    class Summarize(Signature):
        '''Summarize the document in one sentence.'''
        document: str = InputField(desc="the source text")
        summary: str = OutputField(desc="a one-sentence summary")

and the worker (P4.6) turns it into a ``dspy`` predictor at call time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, get_type_hints

from korchestrator.exceptions import MissingExtraError, ValidationError

__all__ = [
    "ArchitectSignature",
    "InputField",
    "OutputField",
    "Signature",
    "WorkerSignature",
    "load_dspy",
]


def load_dspy() -> Any:
    """Import ``dspy`` lazily, raising an actionable error when the extra is absent.

    Returns:
        The imported ``dspy`` module. Typed ``Any`` because ``dspy`` is an optional extra that
        cannot be imported at module scope (the base install must stay ``pydantic``-only).

    Raises:
        MissingExtraError: If the ``[dspy]`` extra is not installed.
    """
    try:
        import dspy
    except ImportError as exc:
        raise MissingExtraError(
            "The cognitive layer requires the 'dspy' extra. "
            "Install it with: pip install 'korchestrator[dspy]'"
        ) from exc
    return dspy


@dataclass(frozen=True)
class _FieldSpec:
    """A declared signature field, recorded without importing ``dspy``."""

    kind: Literal["input", "output"]
    desc: str = ""


# ``Any`` return: the marker is assigned to a typed field (``x: str = InputField()``), mirroring
# ``dspy.InputField``; a precise type would make that assignment fail to type-check.
def InputField(*, desc: str = "") -> Any:  # noqa: N802 — mirrors dspy.InputField's public name
    """Declare a signature **input** field (dspy-free); materialised to ``dspy.InputField``."""
    return _FieldSpec("input", desc)


def OutputField(*, desc: str = "") -> Any:  # noqa: N802 — mirrors dspy.OutputField's public name
    """Declare a signature **output** field (dspy-free); materialised to ``dspy.OutputField``."""
    return _FieldSpec("output", desc)


class Signature:
    """Base class for a declarative reasoning signature — a ``dspy.Signature`` declared lazily.

    Subclass it, annotate typed input/output fields with :func:`InputField` / :func:`OutputField`,
    and put the instruction in the docstring. Declaring a subclass imports **no** ``dspy``; call
    :meth:`to_dspy` (as the worker does) to materialise the real ``dspy.Signature`` — that is the
    only point that requires the ``[dspy]`` extra.

    Example:
        >>> from korchestrator.agents.signatures import Signature, InputField, OutputField
        >>> class Summarize(Signature):
        ...     '''Summarize the document.'''
        ...     document: str = InputField(desc="the source text")
        ...     summary: str = OutputField(desc="a one-sentence summary")
        >>> [name for name, _, _ in Summarize.fields()]
        ['document', 'summary']
    """

    @classmethod
    def fields(cls) -> list[tuple[str, type, _FieldSpec]]:
        """Return the declared ``(name, annotation, spec)`` fields in declaration order.

        Walks the MRO so a subclass inherits its bases' fields; a subclass's own fields come first.
        Annotations are resolved to real types (``from __future__ import annotations`` stores them
        as strings), which is what the ``dspy`` materialisation needs.
        """
        hints = get_type_hints(cls)
        collected: list[tuple[str, type, _FieldSpec]] = []
        seen: set[str] = set()
        for klass in cls.__mro__:
            for name in getattr(klass, "__annotations__", {}):
                if name in seen:
                    continue
                spec = getattr(cls, name, None)
                if isinstance(spec, _FieldSpec):
                    collected.append((name, hints[name], spec))
                    seen.add(name)
        return collected

    @classmethod
    # ``Any`` return: a ``dspy.Signature`` subclass; ``dspy`` is an optional extra not importable
    # at module scope, so the concrete type cannot be named here.
    def to_dspy(cls) -> Any:
        """Materialise this signature as a ``dspy.Signature`` subclass.

        Returns:
            A ``dspy.Signature`` subclass with this signature's fields and its docstring as the
            instruction.

        Raises:
            MissingExtraError: If the ``[dspy]`` extra is not installed.
            ValidationError: If the signature declares no fields.
        """
        fields = cls.fields()
        if not fields:
            raise ValidationError(
                f"Signature {cls.__name__!r} declares no fields. Add at least one InputField and "
                "one OutputField."
            )
        dspy = load_dspy()
        dspy_fields: dict[str, tuple[type, Any]] = {}
        for name, annotation, spec in fields:
            make = dspy.InputField if spec.kind == "input" else dspy.OutputField
            dspy_fields[name] = (annotation, make(desc=spec.desc))
        instructions = (cls.__doc__ or "").strip()
        return dspy.make_signature(dspy_fields, instructions, signature_name=cls.__name__)


class WorkerSignature(Signature):
    """Contribute to the objective from this agent's role, and judge whether it is now met."""

    role: str = InputField(desc="the agent's role and persona")
    objective: str = InputField(desc="the overall goal to achieve")
    context: str = InputField(desc="the relevant conversation and shared state so far")
    answer: str = OutputField(desc="this agent's contribution, or the final answer")
    is_final: bool = OutputField(desc="whether the answer completes the objective")


class ArchitectSignature(Signature):
    """Decompose an objective into a small team of agent roles that can achieve it."""

    objective: str = InputField(desc="the overall goal")
    intent: str = InputField(desc="the classified intent of the objective")
    difficulty: str = InputField(desc="one of: trivial, moderate, complex")
    roles: str = OutputField(desc="a newline-separated list of agent roles and each one's remit")
    rationale: str = OutputField(desc="why this decomposition fits the objective")
