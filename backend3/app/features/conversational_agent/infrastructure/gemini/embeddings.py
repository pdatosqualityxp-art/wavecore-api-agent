import httpx

from app.core.config import get_settings

EMBEDDING_DIMENSIONS = 768
EMBEDDING_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
)


def embed_query(text: str) -> list[float]:
    if not text.strip():
        raise ValueError("query no puede estar vacía")
    if len(text) > 1000:
        raise ValueError("query no puede superar los 1000 caracteres")

    settings = get_settings()
    response = httpx.post(
        EMBEDDING_API_URL.format(model=settings.GEMINI_EMBEDDING_MODEL),
        headers={"x-goog-api-key": settings.GOOGLE_API_KEY},
        json={
            "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
            "outputDimensionality": EMBEDDING_DIMENSIONS,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    values = response.json()["embedding"]["values"]
    if len(values) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"El modelo de embeddings devolvió {len(values)} dimensiones; "
            f"se esperaban {EMBEDDING_DIMENSIONS}"
        )
    return values
