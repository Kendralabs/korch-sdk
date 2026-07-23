"""Context layer (L3).

Imports: korchestrator.interfaces, korchestrator.config, korchestrator.exceptions,
korchestrator.persistence.repository, stdlib.

``resolve_repository`` — the one place a ``PERSISTENCE_BACKEND`` config value becomes a concrete
:class:`~korchestrator.interfaces.GraphRepository`, or ``None`` for a fully standalone run.
"""

from __future__ import annotations

from korchestrator.config import Settings
from korchestrator.exceptions import ConfigurationError
from korchestrator.interfaces import GraphRepository
from korchestrator.persistence.repository import InMemoryGraphRepository

__all__ = ["resolve_repository"]


def resolve_repository(
    settings: Settings, repository: GraphRepository | None = None
) -> GraphRepository | None:
    """Return the injected repository, or the one selected by ``settings.persistence_backend``.

    ``"none"`` returns ``None`` — a fully standalone run with no persistence at all.
    ``"memory"`` (the default) returns a fresh :class:`InMemoryGraphRepository`.
    ``"kcg"`` (an external Kendra Context Graph backend) is post-1.0 and not yet implemented.

    Args:
        settings: The resolved settings; ``persistence_backend`` selects the backend when
            ``repository`` is not injected.
        repository: An explicitly injected repository, taking precedence over ``settings``.

    Returns:
        A :class:`~korchestrator.interfaces.GraphRepository`, or ``None`` for ``"none"``.

    Raises:
        ConfigurationError: If ``persistence_backend="kcg"`` — not yet implemented.

    Example:
        >>> from korchestrator.config import Settings
        >>> from korchestrator.persistence import InMemoryGraphRepository, resolve_repository
        >>> isinstance(resolve_repository(Settings(persistence_backend="memory")),
        ...            InMemoryGraphRepository)
        True
        >>> resolve_repository(Settings(persistence_backend="none")) is None
        True
    """
    if repository is not None:
        return repository
    if settings.persistence_backend == "none":
        return None
    if settings.persistence_backend == "memory":
        return InMemoryGraphRepository()
    raise ConfigurationError(
        f"PERSISTENCE_BACKEND={settings.persistence_backend!r} (an external Kendra Context Graph "
        "backend) is not yet implemented — external backends are post-1.0. Use 'memory' (the "
        "default, zero-infrastructure) or 'none' (fully standalone).",
        code="KORCH_CONFIG_INVALID",
    )
