"""Contract layer. Imports: korchestrator.models, stdlib, pydantic.

The ``IModelGateway`` ARI port — the only sanctioned way the SDK reaches a model for inference.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from korchestrator.models.routing import ModelCard
from korchestrator.models.state import Message

__all__ = ["IModelGateway"]


@runtime_checkable
class IModelGateway(Protocol):
    """Route a reasoning request to a model and return a typed completion.

    ARI port. Default implementations: ``providers/mock_lm.py`` (offline, deterministic — the
    default gateway) and ``providers/gateway_openai.py``; an enterprise deployment supplies the
    Kendra AI Gateway.

    Concurrency: implementations MUST be safe to call concurrently from within a superstep, and
    MUST NOT introduce nondeterminism into workflow scope — any retry, timing, or sampling
    decision belongs inside the implementation, which the runtime treats as an activity boundary.
    """

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int | None = None,
    ) -> Message:
        """Return the model's completion to ``messages`` as an assistant :class:`Message`."""
        ...

    async def available_models(self) -> list[ModelCard]:
        """List the models this gateway can route to."""
        ...
