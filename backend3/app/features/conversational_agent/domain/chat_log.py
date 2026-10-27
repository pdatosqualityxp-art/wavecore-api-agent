from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

API_NAME = "3 agent av"
ANONYMOUS_USER = "anonymous"


class ChatLogEntry(BaseModel):
    api: str = API_NAME
    user: str | None = ANONYMOUS_USER
    model_used: str | None = None
    prompt: str
    reply: str | None = None
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None
    client_ip: str | None = None
    conversation_id: UUID
    created_at: datetime | None = None


class ToolCallTrace(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None


class AgentResult(BaseModel):
    reply: str
    conversation_id: UUID
    model_used: str | None = None
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)


class ChatLogRepository(ABC):
    @abstractmethod
    def add(self, entry: ChatLogEntry) -> None:
        """Persiste una interacción."""

    @abstractmethod
    def list_by_conversation(
        self, conversation_id: UUID, limit: int | None = None
    ) -> list[ChatLogEntry]:
        """Devuelve las interacciones de una conversación en orden cronológico.

        Con `limit` devuelve solo las últimas `limit`, también en orden cronológico.
        """
