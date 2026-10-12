"""How the gateway reaches upstream tool servers.

`InProcessTransport` calls the mock handlers directly (tests, benchmark, demo).
`MCPTransport` (kavach/mcp_bridge.py) speaks real MCP to the same mocks. Both
present the identical interface, so enforcement code never knows the difference.
"""

from __future__ import annotations

from typing import Any, Protocol

from mocks.tools import TOOLS, UpstreamError, list_manifests
from mocks.world import World


class Transport(Protocol):
    async def list_tools(self) -> list[dict[str, Any]]: ...

    async def call(self, tool: str, args: dict[str, Any], token: str | None) -> dict[str, Any]: ...


class InProcessTransport:
    def __init__(self, world: World) -> None:
        self.world = world

    async def list_tools(self) -> list[dict[str, Any]]:
        return list_manifests(self.world)

    async def call(self, tool: str, args: dict[str, Any], token: str | None) -> dict[str, Any]:
        tool_def = TOOLS.get(tool)
        if tool_def is None:
            raise UpstreamError(404, f"unknown tool {tool}")
        return await tool_def.handler(self.world, args, token)
