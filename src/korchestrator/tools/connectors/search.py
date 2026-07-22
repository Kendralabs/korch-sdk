"""Integration layer (L4). Imports: models, types, stdlib.

A deterministic **mock** search connector — the offline fallback used when no real search backend is
configured. It returns stable, query-derived results with no network, so the base install and CI can
exercise the tool path. A real backend (which needs an HTTP client, ``[remote]``) is injected in its
place and is out of scope here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["MockSearchConnector"]


class MockSearchConnector:
    """Return deterministic canned search results for a ``query`` — offline, no network.

    Args:
        results_per_query: How many synthetic results to return. Defaults to ``3``.

    Example:
        >>> import asyncio
        >>> conn = MockSearchConnector()
        >>> result = asyncio.run(conn.execute("web_search", {"query": "durable agents"}))
        >>> result.ok and len(result.output) == 3
        True
    """

    name: ClassVar[str] = "web_search"
    description: ClassVar[str] = (
        "Search the web for a query (offline mock; returns canned results)."
    )
    schema: ClassVar[Mapping[str, JSONValue]] = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, *, results_per_query: int = 3) -> None:
        """Store how many synthetic results each query returns."""
        self._count = results_per_query

    async def execute(
        self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
    ) -> ToolResult:
        """Return ``results_per_query`` deterministic results derived from the query string."""
        query = str(args["query"])
        results: list[JSONValue] = [
            {
                "rank": rank,
                "title": f"Result {rank} for {query!r}",
                "url": f"https://example.test/{rank}",
                "snippet": f"A synthetic offline result about {query!r}.",
            }
            for rank in range(1, self._count + 1)
        ]
        return ToolResult(tool=tool, ok=True, output=results)
