from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from app.features.conversational_agent.application.agent import ConversationalAgent
from app.features.conversational_agent.application.services.chat_logger import ChatLogger
from app.features.conversational_agent.domain.chat_log import (
    ChatLogEntry,
    ChatLogRepository,
)


class InMemoryRepository(ChatLogRepository):
    def __init__(self, fail: bool = False):
        self.entries: list[ChatLogEntry] = []
        self.fail = fail

    def add(self, entry):
        if self.fail:
            raise RuntimeError("supabase caído")
        self.entries.append(entry)

    def list_by_conversation(self, conversation_id, limit=None):
        if self.fail:
            raise RuntimeError("supabase caído")
        rows = [e for e in self.entries if e.conversation_id == conversation_id]
        return rows[-limit:] if limit else rows


class ScriptedModel(BaseChatModel):
    """Modelo falso: responde con los mensajes del guion y registra lo que recibe."""

    script: list[AIMessage]
    received: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages: Sequence[BaseMessage], stop=None, run_manager=None, **kwargs):
        self.received.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])


def _ai(text="", tool_calls=None, model="gemini-test", tokens=(10, 5)):
    return AIMessage(
        content=text,
        tool_calls=tool_calls or [],
        response_metadata={"model_name": model},
        usage_metadata={
            "input_tokens": tokens[0],
            "output_tokens": tokens[1],
            "total_tokens": sum(tokens),
        },
    )


@tool
def get_sales_data(limit: int = 20) -> str:
    """Ventas."""
    return '{"total_ventas": 100.0}'


def _agent(script, repository, **kwargs):
    model = ScriptedModel(script=script, received=[])
    return model, ConversationalAgent(
        model=model, tools=[get_sales_data], chat_logger=ChatLogger(repository), **kwargs
    )


async def test_logs_interaction_with_defaults_and_summed_tokens():
    repo = InMemoryRepository()
    conversation_id = uuid4()
    _, agent = _agent(
        [
            _ai(tool_calls=[{"name": "get_sales_data", "args": {"limit": 5}, "id": "1"}]),
            _ai("Vendimos 100.", model="fallback-model", tokens=(20, 7)),
        ],
        repo,
    )

    result = await agent.ask("¿Cuánto vendimos?", conversation_id)

    assert result.reply == "Vendimos 100."
    assert [(c.name, c.arguments, c.result) for c in result.tool_calls] == [
        ("get_sales_data", {"limit": 5}, '{"total_ventas": 100.0}')
    ]
    assert len(repo.entries) == 1
    entry = repo.entries[0]
    assert entry.api == "3 agent av"
    assert entry.user == "anonymous"
    assert entry.client_ip is None
    assert entry.model_used == "fallback-model"
    assert entry.conversation_id == conversation_id
    assert (entry.prompt_tokens, entry.response_tokens, entry.total_tokens) == (30, 12, 42)


async def test_history_is_rebuilt_by_conversation_id():
    repo = InMemoryRepository()
    conv_a, conv_b = uuid4(), uuid4()
    for conv, prompt, reply in [(conv_a, "pregunta A", "respuesta A"), (conv_b, "pregunta B", "respuesta B")]:
        repo.add(ChatLogEntry(conversation_id=conv, prompt=prompt, reply=reply))

    model, agent = _agent([_ai("ok")], repo)
    await agent.ask("seguimiento", conv_a)

    contents = [m.content for m in model.received[0]]
    assert "pregunta A" in contents and "respuesta A" in contents
    assert "pregunta B" not in contents
    assert contents[-1] == "seguimiento"
    assert [e.prompt for e in repo.entries if e.conversation_id == conv_a] == [
        "pregunta A",
        "seguimiento",
    ]


async def test_history_limited_to_last_turns():
    repo = InMemoryRepository()
    conv = uuid4()
    for i in range(5):
        repo.add(ChatLogEntry(conversation_id=conv, prompt=f"p{i}", reply=f"r{i}"))

    model, agent = _agent([_ai("ok")], repo, history_turns=2)
    await agent.ask("nueva", conv)

    humans = [m.content for m in model.received[0] if isinstance(m, HumanMessage)]
    assert humans == ["p3", "p4", "nueva"]


async def test_repository_failure_does_not_affect_reply():
    _, agent = _agent([_ai("respuesta")], InMemoryRepository(fail=True))
    result = await agent.ask("hola", uuid4())
    assert result.reply == "respuesta"


def test_chat_logger_returns_false_when_insert_fails():
    logger = ChatLogger(InMemoryRepository(fail=True))
    assert logger.log_interaction(conversation_id=UUID(int=1), prompt="p", reply="r") is False
