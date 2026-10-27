import httpx
import pytest

from app.features.conversational_agent.infrastructure.llm.gemini import (
    TransientFallbackMiddleware,
    build_agent_model,
    build_fallback_model,
    is_transient_error,
)


class ApiError(Exception):
    def __init__(self, code: int):
        super().__init__(f"{code} error")
        self.code = code


class FakeRequest:
    def __init__(self, model):
        self.model = model

    def override(self, **kwargs):
        return FakeRequest(kwargs["model"])


@pytest.mark.parametrize("code", [429, 500, 503])
def test_transient_status_codes(code):
    assert is_transient_error(ApiError(code))


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_non_transient_status_codes(code):
    assert not is_transient_error(ApiError(code))


def test_transient_error_detected_through_cause_chain():
    try:
        try:
            raise ApiError(503)
        except ApiError as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as exc:
        assert is_transient_error(exc)


def test_network_errors_are_transient():
    assert is_transient_error(TimeoutError())
    assert is_transient_error(httpx.ConnectTimeout("timeout"))
    assert not is_transient_error(ValueError("argumento inválido"))


async def test_fallback_model_used_on_transient_error():
    middleware = TransientFallbackMiddleware("fallback-model")
    seen = []

    async def handler(request):
        seen.append(request.model)
        if request.model == "primary":
            raise ApiError(503)
        return "ok"

    assert await middleware.awrap_model_call(FakeRequest("primary"), handler) == "ok"
    assert seen == ["primary", "fallback-model"]


async def test_no_fallback_on_non_transient_error():
    middleware = TransientFallbackMiddleware("fallback-model")
    seen = []

    async def handler(request):
        seen.append(request.model)
        raise ApiError(400)

    with pytest.raises(ApiError):
        await middleware.awrap_model_call(FakeRequest("primary"), handler)
    assert seen == ["primary"]


def test_sync_fallback_on_transient_error():
    middleware = TransientFallbackMiddleware("fallback-model")

    def handler(request):
        if request.model == "primary":
            raise ApiError(429)
        return request.model

    assert middleware.wrap_model_call(FakeRequest("primary"), handler) == "fallback-model"


def test_models_are_read_from_settings(monkeypatch):
    from app.core import config

    settings = config.Settings(
        SUPABASE_URL="http://x",
        SUPABASE_KEY="k",
        GOOGLE_API_KEY="g",
        GEMINI_AGENT_MODEL="agent-model-x",
        GEMINI_FALLBACK_MODEL="fallback-model-y",
        _env_file=None,
    )
    monkeypatch.setattr(
        "app.features.conversational_agent.infrastructure.llm.gemini.get_settings",
        lambda: settings,
    )
    assert build_agent_model().model.endswith("agent-model-x")
    assert build_fallback_model().model.endswith("fallback-model-y")
