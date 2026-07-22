"""Integration layer (L4). Imports: models, constants, types, stdlib.

A read-only filesystem connector confined to an injected root directory. Paths are resolved and
checked against the root so traversal (``../``, absolute paths) is denied, not served — the security
rule for identifier validation at a trust boundary. The root is injected (no environment reads).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from korchestrator.constants import error_codes as codes
from korchestrator.models.tool import ToolResult
from korchestrator.types import JSONValue

__all__ = ["FilesystemConnector"]


class FilesystemConnector:
    """Read a UTF-8 text file located within a fixed root directory.

    Args:
        root: The only directory this connector may read from. Paths that resolve outside it are
            denied with ``TOOL_ACCESS_DENIED``.

    Example:
        >>> import asyncio, tempfile, pathlib
        >>> d = tempfile.mkdtemp()
        >>> _ = pathlib.Path(d, "note.txt").write_text("hello", encoding="utf-8")
        >>> conn = FilesystemConnector(d)
        >>> asyncio.run(conn.execute("read_file", {"path": "note.txt"})).output
        'hello'
    """

    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = "Read a UTF-8 text file within the configured root directory."
    schema: ClassVar[Mapping[str, JSONValue]] = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, root: str | Path) -> None:
        """Resolve and store the root directory this connector is confined to."""
        self._root = Path(root).resolve()

    async def execute(
        self, tool: str, args: Mapping[str, JSONValue], *, tenant_id: str = "default"
    ) -> ToolResult:
        """Read the requested file if it is inside the root; return a normalised result."""
        target = (self._root / str(args["path"])).resolve()
        if not target.is_relative_to(self._root):
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.TOOL_ACCESS_DENIED,
                error=f"Path {args['path']!r} resolves outside the connector's root.",
            )
        try:
            content = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ToolResult(
                tool=tool,
                ok=False,
                error_code=codes.TOOL_NOT_FOUND,
                error=f"File {args['path']!r} does not exist.",
            )
        except OSError as exc:
            return ToolResult(
                tool=tool, ok=False, error_code=codes.TOOL_EXECUTION_FAILED, error=str(exc)
            )
        return ToolResult(tool=tool, ok=True, output=content)
