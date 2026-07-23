"""Exception-wrapping boundary tests (spec 08 §2.2, P8.4).

Per-adapter boundary tests already live beside the code they cover — this file adds the
cross-cutting checks the spec asks for (every ``KorchError`` subclass carries a non-empty, stable
``code``; the same instance is catchable as its concrete type and as the base) rather than
duplicating assertions that already exist elsewhere. See, for the third-party-exception-wrapping
boundary itself:

- ``tests/unit/providers/test_gateway_openai.py`` — every ``httpx`` failure mode.
- ``tests/unit/agents/test_worker.py`` / ``test_architect.py`` / ``test_signatures.py`` — the
  ``dspy`` boundary (``ProviderError``/``MissingExtraError``).
- ``tests/unit/runtime/test_temporal_error_wrapping.py`` — the ``temporalio`` client boundary
  (``NetworkError``/``RunFailedError``/``ProviderError``), added in P8.4.
- ``tests/unit/routing/test_model_cards.py`` — file/JSON reads (``ConfigurationError``).
- ``tests/unit/config/test_dotenv.py`` — ``.env`` reads.
"""

from __future__ import annotations

import inspect

import pytest

from korchestrator import exceptions
from korchestrator.exceptions import KorchError


def _korch_error_subclasses() -> list[type[KorchError]]:
    return [
        obj
        for _, obj in inspect.getmembers(exceptions, inspect.isclass)
        if issubclass(obj, KorchError)
    ]


def test_every_exception_module_class_descends_from_korch_error() -> None:
    # The whole point of the tree (spec 08 §2.1): a consumer catching KorchError catches
    # everything the SDK raises deliberately.
    assert len(_korch_error_subclasses()) >= 15


@pytest.mark.parametrize("error_cls", _korch_error_subclasses())
def test_every_korch_error_subclass_has_a_non_empty_default_code(
    error_cls: type[KorchError],
) -> None:
    assert error_cls.default_code
    assert error_cls.default_code.strip() == error_cls.default_code


@pytest.mark.parametrize("error_cls", _korch_error_subclasses())
def test_every_korch_error_subclass_is_catchable_as_the_base(
    error_cls: type[KorchError],
) -> None:
    with pytest.raises(KorchError):
        raise error_cls("boundary test")


def test_wrapping_preserves_the_cause_chain() -> None:
    original = ValueError("upstream detail")
    try:
        try:
            raise original
        except ValueError as exc:
            raise exceptions.ProviderError("wrapped", code="KORCH_PROVIDER_FAILED") from exc
    except exceptions.ProviderError as wrapped:
        assert wrapped.__cause__ is original
        assert isinstance(wrapped, KorchError)
