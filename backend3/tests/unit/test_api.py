from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.core.security import get_current_user
from app.features.conversational_agent.domain.chat_log import AgentResult, ToolCallTrace
from app.features.conversational_agent.infrastructure.api.dependencies import (
    get_conversational_agent,
)
from app.features.conversational_agent.infrastructure.api.v1.router import router


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, str | None]] = []

    async def ask(
        self,
        prompt: str,
        conversation_id: UUID,
        *,
        user: str | None = None,
        client_ip: str | None = None,
    ) -> AgentResult:
        self.calls.append((prompt, conversation_id, client_ip))
        return AgentResult(
            reply="Respuesta de prueba",
            conversation_id=conversation_id,
            model_used="test-model",
            prompt_tokens=4,
            response_tokens=3,
            total_tokens=7,
            tool_calls=[ToolCallTrace(name="test_tool")],
        )


@pytest.fixture
def test_app() -> tuple[FastAPI, FakeAgent]:
    application = FastAPI()
    application.include_router(router)
    fake_agent = FakeAgent()
    application.state.conversational_agent = fake_agent
    application.dependency_overrides[get_conversational_agent] = lambda: fake_agent
    application.dependency_overrides[get_current_user] = lambda: None
    return application, fake_agent


@pytest.mark.asyncio
async def test_chat_generates_session_id_and_returns_agent_metadata(
    test_app: tuple[FastAPI, FakeAgent],
) -> None:
    application, fake_agent = test_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/chat", json={"message": "Hola"})

    assert response.status_code == 200
    body = response.json()
    generated_session_id = UUID(body["session_id"])
    assert body["response"] == "Respuesta de prueba"
    assert body["model_used"] == "test-model"
    assert body["prompt_tokens"] == 4
    assert body["response_tokens"] == 3
    assert body["total_tokens"] == 7
    assert body["tool_calls"] == [{"name": "test_tool", "arguments": {}, "result": None}]
    assert body["elapsed_ms"] >= 0
    assert fake_agent.calls == [("Hola", generated_session_id, "127.0.0.1")]


@pytest.mark.asyncio
async def test_chat_continues_session_and_rejects_client_history(
    test_app: tuple[FastAPI, FakeAgent],
) -> None:
    application, fake_agent = test_app
    session_id = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Seguimos", "session_id": str(session_id)},
        )
        history_response = await client.post(
            "/api/v1/chat", json={"message": "Hola", "history": []}
        )

    assert response.status_code == 200
    assert UUID(response.json()["session_id"]) == session_id
    assert fake_agent.calls[0] == ("Seguimos", session_id, "127.0.0.1")
    assert history_response.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_invalid_session_id(
    test_app: tuple[FastAPI, FakeAgent],
) -> None:
    application, _ = test_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/chat", json={"message": "Hola", "session_id": "not-a-uuid"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint_reports_liveness() -> None:
    application = FastAPI()
    application.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
