import ast
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from app.features.conversational_agent.infrastructure.mcp.client import (
    BACKEND_DIR,
    McpClient,
)
from app.features.conversational_agent.infrastructure.mcp.langchain_tools import (
    load_mcp_tools,
)

EXPECTED_TOOLS = {"get_sales_data", "get_client_summary", "search_document_chunks"}
CONVERSATIONAL_DIR = BACKEND_DIR / "app" / "features" / "conversational_agent"
FORBIDDEN_IMPORTS = ("mcp.tools.sales", "mcp.tools.documents")


@asynccontextmanager
async def open_tools():
    with open(os.devnull, "w") as errlog:
        async with McpClient(errlog=errlog) as client:
            yield {tool.name: tool for tool in await load_mcp_tools(client)}


async def test_lists_server_tools():
    async with open_tools() as tools:
        assert set(tools) == EXPECTED_TOOLS


async def test_tool_schemas_expose_arguments():
    async with open_tools() as tools:
        assert set(tools["get_sales_data"].args_schema["properties"]) == {
            "fecha_desde",
            "fecha_hasta",
            "id_cliente",
            "id_prod",
            "limit",
        }
        assert tools["get_client_summary"].args_schema["required"] == ["id_cliente"]
        assert tools["search_document_chunks"].args_schema["required"] == ["query"]


async def test_invalid_arguments_return_controlled_error():
    async with open_tools() as tools:
        result = await tools["get_sales_data"].ainvoke({"limit": 0})
        assert result.startswith("ERROR:")
        assert "limit" in result

        # La sesión sigue operativa tras un error
        result = await tools["get_sales_data"].ainvoke(
            {"fecha_desde": "2026-02-01", "fecha_hasta": "2026-01-01"}
        )
        assert result.startswith("ERROR:")


async def test_null_optional_arguments_are_dropped():
    async with open_tools() as tools:
        result = await tools["get_sales_data"].ainvoke({"limit": 0, "fecha_desde": None})
        assert result.startswith("ERROR:")
        assert "fecha_desde" not in result


async def test_context_manager_closes_session():
    with open(os.devnull, "w") as errlog:
        client = McpClient(errlog=errlog)
        async with client:
            assert await client.list_tools()
        with pytest.raises(RuntimeError):
            await client.list_tools()


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def test_agent_side_never_imports_tool_functions_directly():
    files = list((CONVERSATIONAL_DIR / "application").rglob("*.py"))
    files += [
        CONVERSATIONAL_DIR / "infrastructure" / "mcp" / "client.py",
        CONVERSATIONAL_DIR / "infrastructure" / "mcp" / "langchain_tools.py",
        BACKEND_DIR / "scripts" / "interactive_chat.py",
    ]
    for path in files:
        for module in _imported_modules(path):
            assert not module.endswith(FORBIDDEN_IMPORTS), f"{path.name} importa {module}"
