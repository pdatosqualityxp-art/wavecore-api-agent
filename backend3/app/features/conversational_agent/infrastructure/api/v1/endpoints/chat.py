from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from app.core.security import CurrentUser, get_current_user
from app.features.conversational_agent.application.agent import ConversationalAgent
from app.features.conversational_agent.infrastructure.api.dependencies import (
    get_conversational_agent,
)
from app.features.conversational_agent.infrastructure.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    agent: ConversationalAgent = Depends(get_conversational_agent),
    current_user: CurrentUser | None = Depends(get_current_user),
) -> ChatResponse:
    session_id = payload.session_id or uuid4()
    started_at = perf_counter()
    result = await agent.ask(
        payload.message,
        session_id,
        user=current_user.identifier if current_user else None,
        client_ip=request.client.host if request.client else None,
    )
    elapsed_ms = (perf_counter() - started_at) * 1000
    return ChatResponse(
        response=result.reply,
        session_id=result.conversation_id,
        tool_calls=result.tool_calls,
        model_used=result.model_used,
        prompt_tokens=result.prompt_tokens,
        response_tokens=result.response_tokens,
        total_tokens=result.total_tokens,
        elapsed_ms=elapsed_ms,
    )
