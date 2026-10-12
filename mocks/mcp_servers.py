"""Expose each mock system as a real MCP server (email, crm, payments).

KAVACH's action token rides in the MCP request `_meta` under `kavach/token`,
so upstream servers can verify it exactly as the HTTP payments API does.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server

from mocks.tools import TOOLS, UpstreamError
from mocks.world import World

TOKEN_META_KEY = "kavach/token"


def _tool_result(payload: dict[str, Any], *, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, default=str))],
        structured_content=payload,
        is_error=error,
    )


def build_upstream_server(world: World, server_name: str) -> Server:
    owned = {name: t for name, t in TOOLS.items() if t.server == server_name}

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=t.name,
                    description=world.tool_description_overrides.get(t.name, t.description),
                    input_schema=t.input_schema,
                )
                for t in owned.values()
            ]
        )

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        tool = owned.get(params.name)
        if tool is None:
            return _tool_result({"status": 404, "error": f"unknown tool {params.name}"}, error=True)
        token = (params.meta or {}).get(TOKEN_META_KEY)
        try:
            return _tool_result(await tool.handler(world, dict(params.arguments or {}), token))
        except UpstreamError as exc:
            return _tool_result({"status": exc.status, "error": str(exc)}, error=True)

    return Server(f"ourbank-{server_name}", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def build_upstream_servers(world: World) -> dict[str, Server]:
    return {name: build_upstream_server(world, name) for name in sorted({t.server for t in TOOLS.values()})}
