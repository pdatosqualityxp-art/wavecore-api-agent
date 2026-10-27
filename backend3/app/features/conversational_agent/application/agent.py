import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.features.conversational_agent.application.prompts import build_system_prompt
from app.features.conversational_agent.application.services.chat_logger import ChatLogger
from app.features.conversational_agent.domain.chat_log import (
    ANONYMOUS_USER,
    AgentResult,
    ToolCallTrace,
)

DEFAULT_HISTORY_TURNS = 10


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, str) or block.get("type") == "text"
        )
    return str(content)


def _collect_tool_calls(messages: Sequence[AnyMessage]) -> list[ToolCallTrace]:
    traces: dict[str, ToolCallTrace] = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                traces[call["id"]] = ToolCallTrace(name=call["name"], arguments=call["args"])
        elif isinstance(message, ToolMessage) and message.tool_call_id in traces:
            traces[message.tool_call_id].result = _text(message.content)
    return list(traces.values())


def _sum_tokens(messages: Sequence[AnyMessage]) -> tuple[int | None, int | None, int | None]:
    usages = [
        message.usage_metadata
        for message in messages
        if isinstance(message, AIMessage) and message.usage_metadata
    ]
    if not usages:
        return None, None, None
    prompt_tokens = sum(usage.get("input_tokens", 0) for usage in usages)
    response_tokens = sum(usage.get("output_tokens", 0) for usage in usages)
    return prompt_tokens, response_tokens, prompt_tokens + response_tokens


def _model_used(messages: Sequence[AnyMessage], default: str | None) -> str | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            name = message.response_metadata.get("model_name")
            if name:
                return name
    return default


class ConversationalAgent:
    def __init__(
        self,
        *,
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        chat_logger: ChatLogger,
        middleware: Sequence[AgentMiddleware] = (),
        history_turns: int = DEFAULT_HISTORY_TURNS,
        default_model_name: str | None = None,
    ) -> None:
        self._agent = create_agent(
            model,
            list(tools),
            system_prompt=build_system_prompt(),
            middleware=list(middleware),
        )
        self._chat_logger = chat_logger
        self._history_turns = history_turns
        self._default_model_name = default_model_name

    async def _load_history(self, conversation_id: UUID) -> list[AnyMessage]:
        entries = await asyncio.to_thread(
            self._chat_logger.get_history, conversation_id, self._history_turns
        )
        history: list[AnyMessage] = []
        for entry in entries:
            history.append(HumanMessage(entry.prompt))
            history.append(AIMessage(entry.reply or ""))
        return history

    async def ask(
        self,
        prompt: str,
        conversation_id: UUID,
        *,
        user: str | None = ANONYMOUS_USER,
        client_ip: str | None = None,
    ) -> AgentResult:
        input_messages = [*await self._load_history(conversation_id), HumanMessage(prompt)]
        state = await self._agent.ainvoke({"messages": input_messages})

        turn_messages = state["messages"][len(input_messages):]
        reply = _text(turn_messages[-1].content) if turn_messages else ""
        prompt_tokens, response_tokens, total_tokens = _sum_tokens(turn_messages)
        model_used = _model_used(turn_messages, self._default_model_name)

        await asyncio.to_thread(
            self._chat_logger.log_interaction,
            conversation_id=conversation_id,
            prompt=prompt,
            reply=reply,
            model_used=model_used,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            user=user,
            client_ip=client_ip,
        )
        return AgentResult(
            reply=reply,
            conversation_id=conversation_id,
            model_used=model_used,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            tool_calls=_collect_tool_calls(turn_messages),
        )
