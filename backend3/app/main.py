from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_cors_origins, get_settings
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
from app.features.conversational_agent.infrastructure.api.v1.router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    async with McpClient() as mcp_client:
        app.state.conversational_agent = ConversationalAgent(
            model=build_agent_model(),
            tools=await load_mcp_tools(mcp_client),
            chat_logger=ChatLogger(SupabaseChatLogRepository()),
            middleware=[TransientFallbackMiddleware(build_fallback_model())],
            history_turns=settings.CHAT_HISTORY_TURNS,
            default_model_name=settings.GEMINI_AGENT_MODEL,
        )
        yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="WaveCore Agent API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()
