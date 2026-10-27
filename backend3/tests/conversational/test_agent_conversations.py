"""Pruebas conversacionales: Gemini, servidor MCP y Supabase reales.

Ejecutar explícitamente desde backend3/:  pytest -m conversational
Variable opcional TEST_CLIENT_ID: id de un cliente existente (por defecto CLI0001).
"""

import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.features.conversational_agent.application.agent import ConversationalAgent
from app.features.conversational_agent.application.services.chat_logger import ChatLogger
from app.features.conversational_agent.infrastructure.llm.gemini import (
    TransientFallbackMiddleware,
    build_agent_model,
    build_fallback_model,
)
from app.features.conversational_agent.infrastructure.mcp.client import McpClient
from app.features.conversational_agent.infrastructure.mcp.langchain_tools import (
    load_mcp_tools,
)
from app.features.conversational_agent.infrastructure.persistence.chat_logs import (
    SupabaseChatLogRepository,
)

pytestmark = pytest.mark.conversational

CLIENT_ID = os.environ.get("TEST_CLIENT_ID", "CLI0001")
SALES_QUESTION = "¿Cuánto hemos vendido en total durante 2026 y cuál ha sido el ticket medio?"
DOCUMENT_QUESTION = "¿Qué condiciones de garantía o mantenimiento aparecen en los documentos?"
MIXED_QUESTION = (
    f"Dame las ventas del cliente {CLIENT_ID} y comprueba si los documentos "
    "mencionan condiciones especiales para él."
)


@asynccontextmanager
async def _open_agent():
    settings = get_settings()
    with open(os.devnull, "w") as errlog:
        async with McpClient(errlog=errlog) as mcp_client:
            yield ConversationalAgent(
                model=build_agent_model(),
                tools=await load_mcp_tools(mcp_client),
                chat_logger=ChatLogger(SupabaseChatLogRepository()),
                middleware=[TransientFallbackMiddleware(build_fallback_model())],
                history_turns=settings.CHAT_HISTORY_TURNS,
                default_model_name=settings.GEMINI_AGENT_MODEL,
            )


def _tool_names(result) -> list[str]:
    return [call.name for call in result.tool_calls]


def _assert_logged(conversation_id, expected_turns: int):
    entries = SupabaseChatLogRepository().list_by_conversation(conversation_id)
    assert len(entries) == expected_turns
    for entry in entries:
        assert entry.api == "3 agent av"
        assert entry.model_used
        assert entry.prompt and entry.reply
        assert entry.total_tokens == entry.prompt_tokens + entry.response_tokens
    return entries


async def test_commercial_question_uses_sales_tool():
    conversation_id = uuid4()
    async with _open_agent() as agent:
        result = await agent.ask(SALES_QUESTION, conversation_id)

    sales_calls = [c for c in result.tool_calls if c.name == "get_sales_data"]
    assert sales_calls
    assert sales_calls[0].arguments.get("fecha_desde") == "2026-01-01"
    assert sales_calls[0].arguments.get("fecha_hasta") == "2026-12-31"
    assert "search_document_chunks" not in _tool_names(result)
    _assert_logged(conversation_id, 1)


async def test_document_question_uses_search_tool():
    conversation_id = uuid4()
    async with _open_agent() as agent:
        result = await agent.ask(DOCUMENT_QUESTION, conversation_id)

    search_calls = [c for c in result.tool_calls if c.name == "search_document_chunks"]
    assert search_calls and search_calls[0].arguments.get("query", "").strip()
    assert "get_sales_data" not in _tool_names(result)
    _assert_logged(conversation_id, 1)


async def test_mixed_question_uses_both_sources():
    conversation_id = uuid4()
    async with _open_agent() as agent:
        result = await agent.ask(MIXED_QUESTION, conversation_id)

    names = _tool_names(result)
    assert {"get_client_summary", "get_sales_data"} & set(names)
    assert "search_document_chunks" in names
    _assert_logged(conversation_id, 1)


async def test_follow_up_uses_history_from_chat_logs():
    conversation_id = uuid4()
    async with _open_agent() as agent:
        await agent.ask(SALES_QUESTION, conversation_id)
        result = await agent.ask("¿Y en 2027?", conversation_id)

    sales_calls = [c for c in result.tool_calls if c.name == "get_sales_data"]
    assert sales_calls
    assert sales_calls[-1].arguments.get("fecha_desde") == "2027-01-01"
    _assert_logged(conversation_id, 2)
