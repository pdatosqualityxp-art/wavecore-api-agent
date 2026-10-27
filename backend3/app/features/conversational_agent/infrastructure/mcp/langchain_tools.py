from typing import Any

from langchain_core.tools import StructuredTool
from mcp import types

from app.features.conversational_agent.infrastructure.mcp.client import McpClient


def _build_tool(client: McpClient, tool: types.Tool) -> StructuredTool:
    async def call(**kwargs: Any) -> str:
        # Gemini envía null en los opcionales omitidos; el servidor aplica sus valores por defecto.
        arguments = {key: value for key, value in kwargs.items() if value is not None}
        result = await client.call_tool(tool.name, arguments)
        return f"ERROR: {result.text}" if result.is_error else result.text

    return StructuredTool(
        name=tool.name,
        description=tool.description or tool.name,
        args_schema=tool.inputSchema,
        coroutine=call,
    )


async def load_mcp_tools(client: McpClient) -> list[StructuredTool]:
    return [_build_tool(client, tool) for tool in await client.list_tools()]
