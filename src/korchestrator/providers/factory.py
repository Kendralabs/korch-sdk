"""Adapter layer. Imports: korchestrator.interfaces/config/exceptions, providers. No optional deps.

The ``get_lm`` gateway factory: given a model name and settings, return the right
:class:`~korchestrator.interfaces.IModelGateway` — the offline :class:`MockLM` by default, or a
configured :class:`OpenAIGateway` when a real gateway is selected. Internal helper (not part of the
public ``korchestrator.__all__`` surface); the façade composition root calls it.
"""

from __future__ import annotations

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError, ValidationError
from korchestrator.interfaces import IModelGateway
from korchestrator.providers.gateway_openai import OpenAIGateway
from korchestrator.providers.mock_lm import MockLM

__all__ = ["get_lm"]


def get_lm(
    model_name: str,
    *,
    settings: Settings | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> IModelGateway:
    """Return the model gateway for ``model_name``, honouring the mock-vs-real decision in settings.

    When ``settings.mock_llm`` is true (the zero-config default) the offline :class:`MockLM` is
    returned and the credentials are ignored. Otherwise a networked :class:`OpenAIGateway` is built
    from the injected ``api_key`` and ``base_url`` — both required for a real gateway, since the
    gateway reads no environment. (Phase 8 sources these from :class:`Settings`; until then the
    composition root passes them explicitly.)

    Args:
        model_name: The intended model, e.g. ``"gpt-4o"``; must be non-empty.
        settings: Configuration deciding mock vs real. Defaults to :class:`Settings` (which reads no
            environment on bare construction), i.e. the offline mock.
        api_key: Bearer credential for the real gateway; required when not mocking.
        base_url: Endpoint root for the real gateway; required when not mocking.
        timeout_seconds: Per-request deadline for the real gateway. Defaults to ``30.0``.

    Returns:
        An :class:`~korchestrator.interfaces.IModelGateway`: :class:`MockLM` or
        :class:`OpenAIGateway`.

    Raises:
        ValidationError: If ``model_name`` is empty.
        ConfigurationError: If a real gateway is requested without ``api_key`` and ``base_url``.

    Example:
        >>> from korchestrator.providers import get_lm, MockLM
        >>> isinstance(get_lm("gpt-4o"), MockLM)  # zero-config default is the offline mock
        True
    """
    if not model_name:
        raise ValidationError("model_name must be a non-empty string, e.g. 'gpt-4o'.")
    settings = settings or Settings()
    if settings.mock_llm:
        return MockLM()
    if not api_key or not base_url:
        raise ConfigurationError(
            "A non-mock model gateway requires both api_key and base_url (the gateway reads no "
            f"environment). Provide them for model {model_name!r}, or set mock_llm=True to run "
            "offline with MockLM."
        )
    return OpenAIGateway(api_key=api_key, base_url=base_url, timeout_seconds=timeout_seconds)
