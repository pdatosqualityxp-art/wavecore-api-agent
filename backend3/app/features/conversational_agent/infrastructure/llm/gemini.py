import re
import warnings
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.errors import GraphBubbleUp

from app.core.config import get_settings

# Algunos modelos Gemini ignoran temperature y langchain-google-genai avisa en cada llamada.
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*", category=UserWarning)

TEMPERATURE = 0.2
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
TRANSIENT_MESSAGE = re.compile(
    r"\b(408|429|500|502|503|504)\b|RESOURCE_EXHAUSTED|UNAVAILABLE|DEADLINE_EXCEEDED|"
    r"INTERNAL|timed? ?out",
    re.IGNORECASE,
)


def build_agent_model() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_AGENT_MODEL,
        temperature=TEMPERATURE,
        api_key=settings.GOOGLE_API_KEY,
        retries=settings.GEMINI_MAX_RETRIES,
    )


def build_fallback_model() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_FALLBACK_MODEL,
        temperature=TEMPERATURE,
        api_key=settings.GOOGLE_API_KEY,
        retries=settings.GEMINI_MAX_RETRIES,
    )


def is_transient_error(exc: BaseException) -> bool:
    """Distingue fallos temporales de la API (cuota, 5xx, red) de errores de petición."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (TimeoutError, ConnectionError)):
            return True
        for attr in ("code", "status_code"):
            code = getattr(current, attr, None)
            if isinstance(code, int):
                return code in TRANSIENT_STATUS_CODES
        if type(current).__module__.startswith(("httpx", "httpcore")) and (
            type(current).__name__.endswith(("Timeout", "TimeoutException", "ConnectError"))
        ):
            return True
        current = current.__cause__ or current.__context__
    return bool(TRANSIENT_MESSAGE.search(str(exc)))


class TransientFallbackMiddleware(AgentMiddleware):
    """Reintenta con el modelo de respaldo solo ante errores transitorios del principal."""

    def __init__(self, fallback_model: ChatGoogleGenerativeAI) -> None:
        super().__init__()
        self._fallback_model = fallback_model

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        try:
            return handler(request)
        except GraphBubbleUp:
            raise
        except Exception as exc:
            if not is_transient_error(exc):
                raise
            return handler(request.override(model=self._fallback_model))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        try:
            return await handler(request)
        except GraphBubbleUp:
            raise
        except Exception as exc:
            if not is_transient_error(exc):
                raise
            return await handler(request.override(model=self._fallback_model))
