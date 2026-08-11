"""Regression test for kcg_tracing._extract_agent_id.

Locks in a real bug: the DSPy signature's *system* message contains the field-description
template `[[ ## role ## ]]\n{role}\n`, with the literal placeholder text `{role}` — not a value.
Only the *user* message carries the filled-in role. The first version of this extractor matched
the system message's template line and reported every KCG Decision node's agent_id as the literal
string "{role}", which is what showed up in KCG's Analytics dashboard until this was fixed.
"""

from datetime import datetime, timezone

from kcg_tracing import _extract_agent_id
from korchestrator.models.state import Message, MessageRole

_OFFLINE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _msg(role: MessageRole, content: str) -> Message:
    return Message(
        id="m",
        role=role,
        sender="x",
        content=content,
        superstep=0,
        valid_time=_OFFLINE_TIME,
    )


def test_extract_agent_id_skips_the_system_message_template_placeholder() -> None:
    system = _msg(
        MessageRole.SYSTEM,
        "Your input fields are:\n1. `role` (str)\n\n"
        "[[ ## role ## ]]\n{role}\n\n[[ ## objective ## ]]\n{objective}\n",
    )
    user = _msg(
        MessageRole.USER,
        "[[ ## role ## ]]\nGeneral Research & Knowledge Agent\n\n"
        "[[ ## objective ## ]]\nWhat is 2 + 2?\n",
    )
    assert _extract_agent_id([system, user], fallback="unknown") == "General Research & Knowledge Agent"


def test_extract_agent_id_falls_back_when_no_role_marker_present() -> None:
    msg = _msg(MessageRole.USER, "no signature markers here")
    assert _extract_agent_id([msg], fallback="korchestrator-researcher-demo") == "korchestrator-researcher-demo"
