import time
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException

from app.core.config import Settings, get_settings
from app.core.security import decode_supabase_token, get_current_user
from app.features.conversational_agent.domain.chat_log import AgentResult
from app.features.conversational_agent.infrastructure.api.dependencies import (
    get_conversational_agent,
)
from app.features.conversational_agent.infrastructure.api.v1.router import router

SECRET = "test-secret-with-at-least-32-bytes-long!"


class RecordingAgent:
    def __init__(self) -> None:
        self.users: list[str | None] = []

    async def ask(
        self,
        prompt: str,
        conversation_id: UUID,
        *,
        user: str | None = None,
        client_ip: str | None = None,
    ) -> AgentResult:
        self.users.append(user)
        return AgentResult(reply="ok", conversation_id=conversation_id)


def make_token(secret: str = SECRET, **overrides: object) -> str:
    claims: dict[str, object] = {
        "sub": str(uuid4()),
        "email": "ana@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


def build_app(auth_enabled: bool = True) -> tuple[FastAPI, RecordingAgent]:
    application = FastAPI()
    application.include_router(router)
    agent = RecordingAgent()
    settings = Settings(
        SUPABASE_URL="http://x",
        SUPABASE_KEY="k",
        GOOGLE_API_KEY="g",
        SUPABASE_JWT_SECRET=SECRET,
        AUTH_ENABLED=auth_enabled,
    )
    application.dependency_overrides[get_conversational_agent] = lambda: agent
    application.dependency_overrides[get_settings] = lambda: settings
    return application, agent


async def post_chat(application: FastAPI, token: str | None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        return await client.post("/api/v1/chat", json={"message": "Hola"}, headers=headers)


async def test_valid_token_passes_user_email_to_agent() -> None:
    application, agent = build_app()
    response = await post_chat(application, make_token())
    assert response.status_code == 200
    assert agent.users == ["ana@example.com"]


async def test_user_id_used_when_token_has_no_email() -> None:
    application, agent = build_app()
    sub = str(uuid4())
    response = await post_chat(application, make_token(sub=sub, email=None))
    assert response.status_code == 200
    assert agent.users == [sub]


@pytest.mark.parametrize(
    "token",
    [
        None,
        "no-es-un-jwt",
        make_token(secret="otro-secreto-distinto-de-32-bytes-o-mas!!"),
        make_token(exp=int(time.time()) - 10),
        make_token(aud="anon"),
    ],
)
async def test_invalid_token_returns_401(token: str | None) -> None:
    application, agent = build_app()
    response = await post_chat(application, token)
    assert response.status_code == 401
    assert agent.users == []


async def test_auth_disabled_allows_requests_without_token_and_logs_null_user() -> None:
    application, agent = build_app(auth_enabled=False)
    response = await post_chat(application, None)
    assert response.status_code == 200
    assert agent.users == [None]


def es256_token(private_key: object, **overrides: object) -> str:
    claims: dict[str, object] = {
        "sub": str(uuid4()),
        "email": "es@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "k1"})


class FakeJwksClient:
    def __init__(self, public_key: object) -> None:
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        return SimpleNamespace(key=self.public_key)


def test_es256_token_validated_with_jwks_public_key() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    settings = Settings(SUPABASE_URL="http://x", SUPABASE_KEY="k", GOOGLE_API_KEY="g")
    client = FakeJwksClient(private_key.public_key())
    user = decode_supabase_token(es256_token(private_key), settings, client)  # type: ignore[arg-type]
    assert user.identifier == "es@example.com"


def test_es256_token_signed_with_other_key_is_rejected() -> None:
    settings = Settings(SUPABASE_URL="http://x", SUPABASE_KEY="k", GOOGLE_API_KEY="g")
    client = FakeJwksClient(ec.generate_private_key(ec.SECP256R1()).public_key())
    token = es256_token(ec.generate_private_key(ec.SECP256R1()))
    with pytest.raises(HTTPException) as error:
        decode_supabase_token(token, settings, client)  # type: ignore[arg-type]
    assert error.value.status_code == 401


async def test_health_stays_public() -> None:
    application, _ = build_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
