"""Kernel layer (L1), framework-free. Imports: korchestrator.core.reducers, stdlib.

Binds each ``AgentState.context`` channel to exactly one reducer (spec 06 §3). A channel with no
explicit binding uses the default reducer, ``LastValue`` — the safest merge (last writer wins).
"""

from __future__ import annotations

from collections.abc import Mapping

from korchestrator.core.reducers import LastValue, Reducer

__all__ = ["ChannelSchema"]


class ChannelSchema:
    """A mapping from context channel name to its bound reducer, with a default.

    Args:
        reducers: Explicit channel-to-reducer bindings.
        default: The reducer for any unbound channel. Defaults to ``LastValue()``.

    Example:
        >>> from korchestrator.core import Append, LastValue
        >>> from korchestrator.core.channels import ChannelSchema
        >>> schema = ChannelSchema({"findings": Append()})
        >>> isinstance(schema.reducer_for("findings"), Append)
        True
        >>> isinstance(schema.reducer_for("anything_else"), LastValue)
        True
    """

    def __init__(
        self,
        reducers: Mapping[str, Reducer] | None = None,
        *,
        default: Reducer | None = None,
    ) -> None:
        """Store the channel bindings and the default reducer."""
        self._reducers: dict[str, Reducer] = dict(reducers or {})
        self._default: Reducer = default if default is not None else LastValue()

    def reducer_for(self, channel: str) -> Reducer:
        """Return the reducer bound to ``channel``, or the default if none is bound."""
        return self._reducers.get(channel, self._default)

    @property
    def bound_channels(self) -> tuple[str, ...]:
        """The names of channels with an explicit reducer binding, sorted."""
        return tuple(sorted(self._reducers))
