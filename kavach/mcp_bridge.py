"""MCP on both sides of the gateway.

* `MCPTransport`: KAVACH as an MCP *client* of the upstream tool servers.
* `build_gateway_server`: KAVACH as the agent's only MCP *server*. Every
  `tools/call` an external agent (Claude Desktop, an IDE agent, etc.) makes
  goes through `Gateway.call`.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from mcp import Client, types
from mcp.server.lowlevel import Server

from kavach.gateway import Gateway, Session
from mocks.mcp_servers import TOKEN_META_KEY
from mocks.tools import UpstreamError


class MCPTransport:
    """Routes `server.tool` names to the matching upstream MCP client."""

    def __init__(self, upstreams: dict[str, Server | str]) -> None:
        self._upstreams = upstreams
        self._clients: dict[str, Client] = {}
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> MCPTransport:
        for name, target in self._upstreams.items():
            self._clients[name] = await self._stack.enter_async_context(Client(target))
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._stack.aclose()

    async def list_tools(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for server, client in self._clients.items():
            listing = await client.list_tools()
            out += [
                {
                    "name": t.name,
                    "server": server,
                    "description": t.description or "",
                    "input_schema": t.input_schema,
                }
                for t in listing.tools
            ]
        return out

    async def call(self, tool: str, args: dict[str, Any], token: str | None) -> dict[str, Any]:
        server = tool.split(".", 1)[0]
        client = self._clients.get(server)
        if client is None:
            raise UpstreamError(404, f"no upstream MCP server for {tool}")
        result = await client.call_tool(tool, args, meta={TOKEN_META_KEY: token or ""})
        payload = result.structured_content
        if payload is None:
            text = "".join(c.text for c in result.content if isinstance(c, types.TextContent))
            payload = json.loads(text) if text else {}
        if result.is_error:
            raise UpstreamError(int(payload.get("status", 502)), str(payload.get("error", "upstream error")))
        return payload


def build_gateway_server(gateway: Gateway, session: Session) -> Server:
    """KAVACH as an MCP server: the agent sees upstream tools, but every call is enforced."""

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        tools = await gateway.list_tools()
        return types.ListToolsResult(
            tools=[
                types.Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
                for t in tools
            ]
        )

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        outcome = await gateway.call(session, params.name, dict(params.arguments or {}))
        payload = outcome.for_agent()
        payload_with_verdict = {**payload, "_kavach": {"verdict": outcome.decision.verdict.value}}
        return types.CallToolResult(
            content=[
                types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, default=str))
            ],
            structured_content=payload_with_verdict,
            is_error=bool(outcome.error),
        )

    return Server("kavach-gateway", on_list_tools=on_list_tools, on_call_tool=on_call_tool)
