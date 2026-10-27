from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.conversational_agent.domain.chat_log import ToolCallTrace


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: UUID
    tool_calls: list[ToolCallTrace]
    model_used: str | None = None
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None
    elapsed_ms: float
