"""A real business swarm: triage -> research (tool use) -> resolve -> review, on real OpenAI models.

Four agents collaborate on a customer support escalation about a failed payment, each on a
model chosen for its task (heterogeneous per-agent models, spec 04 Agent.model):

  triage (gpt-4o-mini)      -> classifies urgency/category
  researcher (gpt-4o-mini)  -> calls the `lookup_account` tool for payment history
  resolver (gpt-4o)         -> drafts the customer-facing resolution (stronger model)
  reviewer (gpt-4o-mini)    -> policy/tone check before the draft is considered final

Edges route triage -> researcher -> resolver -> reviewer, so each downstream agent sees its
upstream neighbour's findings in `context` once the kernel's Pregel barrier has propagated
them (spec 06 §2: superstep 0 activates every agent against the bare objective; each later
superstep only reactivates agents that received a new message). A well-behaved agent finalizes
only once it has what it needs.

Run: python examples/08_support_escalation_swarm.py
Requires: pip install "korchestrator[dspy,remote]"

With OPENAI_API_KEY set (see .env.example), this calls real OpenAI models end to end. With no
key, it falls back to a small deterministic offline gateway (below) so the example stays
runnable and testable with no network and no cost (testing rule T1/T4) — the topology, tool
call, and multi-round propagation are exercised identically either way; only the reasoning is
canned.

Per-agent models are overridable via TRIAGE_MODEL / RESEARCHER_MODEL / RESOLVER_MODEL /
REVIEWER_MODEL so model selection is configurable, not hardcoded.
"""

import json
import os
from datetime import datetime, timezone

from korchestrator import Agent, Swarm
from korchestrator.models.state import Message, MessageRole
from korchestrator.providers import OpenAIGateway
from korchestrator.tools import ConnectorRegistry

TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "gpt-4o-mini")
RESEARCHER_MODEL = os.environ.get("RESEARCHER_MODEL", "gpt-4o-mini")
RESOLVER_MODEL = os.environ.get("RESOLVER_MODEL", "gpt-4o")
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gpt-4o-mini")

OBJECTIVE = (
    "Handle this customer support escalation: 'My recurring subscription payment failed "
    "twice this week even though I have sufficient funds. I need this resolved today.'"
)


# --- The one tool the researcher agent can call --------------------------------------------
async def lookup_account(args: dict) -> str:
    account_id = str(args.get("account_id", "unknown"))
    return (
        f"account {account_id}: card on file expired 2026-07-15; last successful payment "
        "was 2026-06-02 ($89.00); 2 failed attempts this week (reason: expired_card)."
    )


tool_registry = ConnectorRegistry().register_tool(
    "lookup_account",
    {
        "type": "object",
        "properties": {"account_id": {"type": "string"}},
        "required": ["account_id"],
    },
    lookup_account,
    description="Look up a customer account's recent payment history by account_id.",
)


# --- Deterministic offline stand-in, used only when OPENAI_API_KEY is unset ----------------
# Distinctive phrases that only appear in an upstream agent's *real, final* answer (never in its
# "still waiting" placeholder) — downstream agents check for these in `context` before finalizing,
# so the offline path genuinely waits for upstream output instead of guessing at a round number.
_RESEARCH_MARKER = "card on file expired 2026-07-15"
_RESOLUTION_MARKER = "service credit"
_OFFLINE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _worker_reply(*, answer: str, is_final: bool) -> str:
    """A DSPy ChatAdapter-formatted WorkerSignature reply (answer, is_final)."""
    return f"[[ ## answer ## ]]\n{answer}\n\n[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"


def _react_reply(
    *, thought: str = "", tool_name: str = "", tool_args: str = "", answer: str = "", is_final: bool
) -> str:
    """A DSPy ChatAdapter-formatted ReActWorkerSignature reply (all five declared fields)."""
    return (
        "[[ ## thought ## ]]\n"
        f"{thought}\n\n"
        "[[ ## tool_name ## ]]\n"
        f"{tool_name}\n\n"
        "[[ ## tool_args ## ]]\n"
        f"{tool_args}\n\n"
        "[[ ## answer ## ]]\n"
        f"{answer}\n\n"
        f"[[ ## is_final ## ]]\n{is_final}\n\n[[ ## completed ## ]]"
    )


class OfflineGateway:
    """A small, deterministic, role-aware stand-in for a real gateway (no network, no cost).

    Keyed by each agent's ``role`` (a signature input field, so it appears verbatim in the
    rendered prompt) rather than by model name, so distinct agents get distinct replies even
    when they share a model. Downstream agents (resolver, reviewer) check `context` for their
    upstream neighbour's marker phrase before finalizing, so the offline run genuinely waits
    for the swarm to propagate real findings — the same "don't finalize until you have what
    you need" behavior a well-prompted real model exhibits.
    """

    def __init__(self) -> None:
        self._researcher_calls = 0

    async def complete(
        self, messages: list[Message], *, model: str, max_tokens: int | None = None
    ) -> Message:
        rendered = "\n".join(message.content for message in messages)
        return Message(
            id="offline-gateway",
            role=MessageRole.ASSISTANT,
            sender="assistant",
            content=self._reply_for(rendered),
            superstep=0,
            valid_time=_OFFLINE_TIME,
        )

    def _reply_for(self, rendered: str) -> str:
        if "account-researcher" in rendered:
            self._researcher_calls += 1
            if self._researcher_calls == 1:
                return _react_reply(
                    thought="I should check this account's recent payment history first.",
                    tool_name="lookup_account",
                    tool_args=json.dumps({"account_id": "ACC-48213"}),
                    is_final=False,
                )
            return _react_reply(
                thought="The account lookup answers the research question.",
                answer=(
                    f"Account ACC-48213: {_RESEARCH_MARKER}, causing both failed charges; last "
                    "successful payment was $89.00 on 2026-06-02."
                ),
                is_final=True,
            )
        if "resolution-specialist" in rendered:
            if _RESEARCH_MARKER in rendered:
                return _worker_reply(
                    answer=(
                        "Update the card on file and we will retry the payment immediately at "
                        f"no extra charge; a $10 {_RESOLUTION_MARKER} has been applied for the "
                        "inconvenience."
                    ),
                    is_final=True,
                )
            return _worker_reply(
                answer="(reviewing the account researcher's findings before drafting a resolution)",
                is_final=False,
            )
        if "qa-reviewer" in rendered:
            if _RESOLUTION_MARKER in rendered:
                return _worker_reply(
                    answer="Draft approved: accurate, empathetic, and consistent with billing policy.",
                    is_final=True,
                )
            return _worker_reply(
                answer="(awaiting the drafted resolution before review)", is_final=False
            )
        if "triage-specialist" in rendered:
            return _worker_reply(
                answer="category=billing_payment_failure; urgency=high; reason=expired card on file.",
                is_final=True,
            )
        return _worker_reply(answer="(no reply)", is_final=True)

    async def available_models(self) -> list:
        return []


def build_gateway():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("[info] OPENAI_API_KEY not set — running against the deterministic offline gateway.\n")
        return OfflineGateway()
    return OpenAIGateway(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))


def build_swarm() -> Swarm:
    return (
        Swarm(objective=OBJECTIVE, model_gateway=build_gateway(), connectors=tool_registry)
        .add(Agent(id="triage", role="triage-specialist", model=TRIAGE_MODEL))
        .add(
            Agent(
                id="researcher",
                role="account-researcher",
                model=RESEARCHER_MODEL,
                tools=("lookup_account",),
            )
        )
        .add(Agent(id="resolver", role="resolution-specialist", model=RESOLVER_MODEL))
        .add(Agent(id="reviewer", role="qa-reviewer", model=REVIEWER_MODEL))
        .edges([("triage", "researcher"), ("researcher", "resolver"), ("resolver", "reviewer")])
    )


def main() -> None:
    swarm = build_swarm()
    result = swarm.run(max_supersteps=8)

    print("status:", result.status, "| supersteps:", result.supersteps)
    for message in result.messages:
        print(f"  [{message.superstep}] {message.sender} ({message.kind}): {message.content[:100]}")

    # `result.final_answer` is every agent's answer-kind message concatenated (spec: it's a full
    # log, not just the terminal step) — useful for audit, but the reviewer's own last answer is
    # the actual customer-facing resolution once the swarm has converged.
    resolution = next(
        (m.content for m in reversed(result.messages) if m.sender == "reviewer" and m.kind == "answer"),
        result.final_answer,
    )
    print("\nresolution (reviewer-approved):\n" + resolution)

    assert result.status.value == "completed"


if __name__ == "__main__":
    main()
