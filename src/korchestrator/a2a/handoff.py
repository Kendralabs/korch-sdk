"""Agent-to-agent layer. Imports: models, stdlib.

Typed directed agent-to-agent messaging. :func:`directed_message` builds a message addressed to one
recipient (the kernel delivers it only along a real edge); :class:`HandoffTransformer` turns one
agent's output into a ``kind="handoff"`` request for another agent, optionally prefixing a summary.
Message ids/sender/superstep are re-stamped by the barrier during routing, so callers pass the
logical fields and the kernel owns provenance.
"""

from __future__ import annotations

from datetime import datetime

from korchestrator.models.state import Message, MessageRole, Performative

__all__ = ["HandoffTransformer", "directed_message"]


def directed_message(
    *,
    sender: str,
    recipient: str,
    content: str,
    superstep: int,
    valid_time: datetime,
    performative: Performative = Performative.INFORM,
    kind: str = "thought",
) -> Message:
    """Build a message addressed to ``recipient`` (delivered only if an edge connects them).

    Args:
        sender: The emitting agent id.
        recipient: The target agent id; the kernel requires a ``sender -> recipient`` edge.
        content: The message body.
        superstep: The current superstep (re-stamped by the barrier).
        valid_time: The message's valid time.
        performative: The FIPA-lite speech act. Defaults to ``INFORM``.
        kind: The message kind. Defaults to ``"thought"``.

    Returns:
        A directed :class:`Message`.

    Example:
        >>> from datetime import datetime, timezone
        >>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        >>> msg = directed_message(
        ...     sender="a", recipient="b", content="hi", superstep=0, valid_time=now
        ... )
        >>> msg.recipient
        'b'
    """
    return Message(
        id=f"{sender}->{recipient}",
        role=MessageRole.ASSISTANT,
        performative=performative,
        kind=kind,
        sender=sender,
        recipient=recipient,
        content=content,
        superstep=superstep,
        valid_time=valid_time,
    )


class HandoffTransformer:
    """Turn one agent's output into a ``kind="handoff"`` request addressed to another agent.

    Example:
        >>> from datetime import datetime, timezone
        >>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        >>> handoff = HandoffTransformer().transform(
        ...     sender="researcher",
        ...     recipient="writer",
        ...     content="findings...",
        ...     superstep=1,
        ...     valid_time=now,
        ...     summary="Draft a summary from these findings",
        ... )
        >>> (handoff.kind, handoff.recipient, handoff.performative.value)
        ('handoff', 'writer', 'request')
    """

    def transform(
        self,
        *,
        sender: str,
        recipient: str,
        content: str,
        superstep: int,
        valid_time: datetime,
        summary: str | None = None,
    ) -> Message:
        """Build the handoff message, prefixing ``summary`` when given.

        Args:
            sender: The handing-off agent id.
            recipient: The receiving agent id (must be edge-connected to ``sender``).
            content: The context to hand over.
            superstep: The current superstep (re-stamped by the barrier).
            valid_time: The message's valid time.
            summary: An optional instruction/summary prefixed to the content.

        Returns:
            A ``kind="handoff"``, ``REQUEST`` :class:`Message` addressed to ``recipient``.
        """
        body = content if summary is None else f"{summary}\n\n{content}"
        return directed_message(
            sender=sender,
            recipient=recipient,
            content=body,
            superstep=superstep,
            valid_time=valid_time,
            performative=Performative.REQUEST,
            kind="handoff",
        )
