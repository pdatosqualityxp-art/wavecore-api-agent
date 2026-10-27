from typing import Any

from app.features.conversational_agent.infrastructure.gemini.embeddings import (
    embed_query,
)
from app.features.conversational_agent.infrastructure.persistence.supabase import (
    get_supabase_client,
)


def search_document_chunks(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Busca fragmentos de documentos por significado usando una consulta en texto."""
    if not query.strip():
        raise ValueError("query no puede estar vacía")
    if len(query) > 1000:
        raise ValueError("query no puede superar los 1000 caracteres")
    if isinstance(top_k, bool) or not 1 <= top_k <= 20:
        raise ValueError("top_k debe estar entre 1 y 20")

    embedding = embed_query(query)
    result = get_supabase_client().rpc(
        "match_document_chunks",
        {"query_embedding": embedding, "match_count": top_k},
    ).execute()
    return [
        {
            "id": row["id"],
            "document_id": row["document_id"],
            "page_number": row["page_number"],
            "chunk_text": row["chunk_text"],
            "similarity": float(row["similarity"]),
        }
        for row in result.data
    ]
