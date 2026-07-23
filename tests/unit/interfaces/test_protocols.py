"""Structural-conformance tests for the ARI ports and supporting protocols (P1.3/P1.4).

Protocols carry no behaviour, so these tests lock the *shape*: the exported names, each a
runtime-checkable Protocol, a conforming implementation satisfies ``isinstance``, and a
non-conforming class does not. Renaming a protocol method breaks the matching fake below.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime

from korchestrator import interfaces
from korchestrator.interfaces import (
    AUBConnector,
    BaseRouter,
    GraphRepository,
    IDurableRuntime,
    IExecutionSandbox,
    IIdentityProvider,
    IModelGateway,
    IToolInvoker,
    TenantStore,
)
from korchestrator.models.context_graph import GraphNode
from korchestrator.models.result import RunResult
from korchestrator.models.routing import ModelCard, RoutingContext, RoutingResult
from korchestrator.models.state import AgentState, Message
from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

EXPECTED = {
    "AUBConnector",
    "BaseRouter",
    "Connector",
    "GraphRepository",
    "IDurableRuntime",
    "IExecutionSandbox",
    "IIdentityProvider",
    "IModelGateway",
    "IToolInvoker",
    "TenantStore",
}


def test_interfaces_export_the_expected_protocols() -> None:
    assert set(interfaces.__all__) == EXPECTED


# --- conforming fakes ----------------------------------------------------------------------------


class _Gateway:
    async def complete(
        self, messages: list[Message], *, model: str, max_tokens: int | None = None
    ) -> Message:
        raise NotImplementedError

    async def available_models(self) -> list[ModelCard]:
        raise NotImplementedError


class _Identity:
    async def authenticate(self, agent_id: str, *, tenant_id: str = "default") -> str:
        raise NotImplementedError

    def tenant_of(self, agent_id: str) -> str:
        raise NotImplementedError


class _Sandbox:
    async def execute(
        self,
        tool: str,
        args: Mapping[str, JSONValue],
        *,
        tenant_id: str = "default",
        timeout_seconds: float = 30.0,
    ) -> ToolResult:
        raise NotImplementedError


class _Runtime:
    def now(self) -> datetime:
        raise NotImplementedError

    async def start(self, state: AgentState, *, max_supersteps: int = 10) -> str:
        raise NotImplementedError

    async def wait(self, run_id: str, *, timeout_seconds: float | None = None) -> RunResult:
        raise NotImplementedError

    async def signal(self, run_id: str, name: str, payload: Mapping[str, str]) -> None:
        raise NotImplementedError


class _Repository:
    async def save_state(self, state: AgentState, *, tenant_id: str) -> None:
        raise NotImplementedError

    async def load_state(self, run_id: str, *, tenant_id: str) -> AgentState | None:
        raise NotImplementedError

    async def record_node(self, node: GraphNode, *, tenant_id: str) -> None:
        raise NotImplementedError

    async def query_nodes(
        self,
        *,
        tenant_id: str,
        run_id: str | None = None,
        as_of: datetime | None = None,
        valid_at: datetime | None = None,
    ) -> tuple[GraphNode, ...]:
        raise NotImplementedError


class _Tenants:
    async def is_known(self, tenant_id: str) -> bool:
        raise NotImplementedError


class _Router:
    async def select_model(self, context: RoutingContext) -> RoutingResult:
        raise NotImplementedError


class _Connector:
    async def execute(
        self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
    ) -> ToolResult:
        raise NotImplementedError


class _ToolInvoker:
    async def invoke_tool(
        self,
        tool: str,
        args: Mapping[str, JSONValue],
        *,
        tenant_id: str,
        mounted: Collection[str],
    ) -> ToolResult:
        raise NotImplementedError

    def describe_tool(self, tool: str) -> str:
        raise NotImplementedError


CONFORMING = [
    (_Gateway(), IModelGateway),
    (_Identity(), IIdentityProvider),
    (_Sandbox(), IExecutionSandbox),
    (_Runtime(), IDurableRuntime),
    (_Repository(), GraphRepository),
    (_Tenants(), TenantStore),
    (_Router(), BaseRouter),
    (_Connector(), AUBConnector),
    (_ToolInvoker(), IToolInvoker),
]


def test_conforming_implementations_satisfy_their_protocol() -> None:
    for impl, protocol in CONFORMING:
        assert isinstance(impl, protocol), f"{type(impl).__name__} !~ {protocol.__name__}"


def test_a_non_conforming_class_does_not_satisfy_a_protocol() -> None:
    class _Empty:
        pass

    assert not isinstance(_Empty(), IModelGateway)
    assert not isinstance(_Empty(), BaseRouter)


def test_protocols_are_cross_checked_not_universally_matching() -> None:
    # A gateway is not a router — the method sets differ.
    assert not isinstance(_Gateway(), BaseRouter)
    assert not isinstance(_Router(), IModelGateway)
