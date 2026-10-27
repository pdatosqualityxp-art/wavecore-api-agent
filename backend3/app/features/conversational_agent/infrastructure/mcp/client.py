import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, TextIO

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parents[5]
SERVER_MODULE = "app.features.conversational_agent.infrastructure.mcp.server"


class McpToolResult(BaseModel):
    text: str
    is_error: bool = False


class McpClient:
    """Cliente MCP sobre stdio: arranca el servidor como subproceso y gestiona la sesión."""

    def __init__(self, errlog: TextIO | None = None) -> None:
        self._errlog = errlog if errlog is not None else sys.stderr
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "McpClient":
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", SERVER_MODULE],
            cwd=str(BACKEND_DIR),
            env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
        )
        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(server, errlog=self._errlog)
            )
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        stack, self._stack, self._session = self._stack, None, None
        if stack is not None:
            await stack.aclose()

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("El cliente MCP no está iniciado")
        return self._session

    async def list_tools(self) -> list[types.Tool]:
        return (await self._require_session().list_tools()).tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        try:
            result = await self._require_session().call_tool(name, arguments)
        except Exception as exc:
            return McpToolResult(text=f"Fallo al invocar '{name}': {exc}", is_error=True)

        texts = [item.text for item in result.content if isinstance(item, types.TextContent)]
        if not texts and result.structuredContent is not None:
            texts = [json.dumps(result.structuredContent, ensure_ascii=False)]
        return McpToolResult(text="\n".join(texts), is_error=bool(result.isError))
