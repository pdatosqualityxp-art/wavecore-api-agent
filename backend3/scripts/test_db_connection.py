"""Verifica la conexión con Supabase: consultas relacionales y lectura de embeddings.

Ejecutar desde backend3/:
    python scripts/test_db_connection.py
"""

import json
import math
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.features.conversational_agent.infrastructure.persistence.supabase import (  # noqa: E402
    get_supabase_client,
)


def print_rows(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n=== {title} ({len(rows)} registros) ===")
    if not rows:
        print("(sin resultados)")
        return
    headers = list(rows[0].keys())
    table = [[str(row.get(h, "")) for h in headers] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in table)) for i, h in enumerate(headers)]
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for r in table:
        print(" | ".join(c.ljust(w) for c, w in zip(r, widths)))


def parse_embedding(raw: Any) -> list[float]:
    # PostgREST devuelve los vectores pgvector como texto "[0.1,0.2,...]"
    if isinstance(raw, str):
        return json.loads(raw)
    return list(raw)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def test_clientes(client) -> None:
    result = client.table("clientes").select("*").limit(5).execute()
    print_rows("clientes (primeros 5)", result.data)


def test_ventas_productos(client) -> None:
    result = (
        client.table("ventas")
        .select("id_venta, unidades, total_venta, fecha_venta, productos(nom_prod, precio_prod)")
        .limit(5)
        .execute()
    )
    rows = [
        {
            "id_venta": r["id_venta"],
            "producto": (r.get("productos") or {}).get("nom_prod"),
            "unidades": r["unidades"],
            "total_venta": r["total_venta"],
            "fecha_venta": r["fecha_venta"],
        }
        for r in result.data
    ]
    print_rows("ventas x productos (primeras 5)", rows)


def test_document_chunks(client) -> None:
    result = (
        client.table("document_chunks")
        .select("id, document_id, page_number, chunk_text, embedding")
        .not_.is_("embedding", "null")
        .limit(5)
        .execute()
    )
    if not result.data:
        raise RuntimeError("document_chunks no contiene filas con embedding")

    chunks = [(row, parse_embedding(row["embedding"])) for row in result.data]
    dimensions = {len(vec) for _, vec in chunks}
    print_rows(
        "document_chunks (primeros 5)",
        [
            {
                "id": row["id"],
                "document_id": row["document_id"],
                "page": row["page_number"],
                "dim": len(vec),
                "texto": (row["chunk_text"] or "")[:60],
            }
            for row, vec in chunks
        ],
    )
    print(f"Dimensiones de embedding encontradas: {sorted(dimensions)}")

    # Comprobación de similitud: compara el primer embedding con el resto
    query_row, query_vec = chunks[0]
    print(f"\nSimilitud coseno respecto al chunk {query_row['id']}:")
    for row, vec in chunks[1:]:
        print(f"  chunk {row['id']}: {cosine_similarity(query_vec, vec):.4f}")


def main() -> int:
    try:
        client = get_supabase_client()
        test_clientes(client)
        test_ventas_productos(client)
        test_document_chunks(client)
    except Exception as exc:  # noqa: BLE001 - el script de diagnóstico debe mostrar cualquier fallo
        print(f"\nERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("\nConexión y consultas verificadas correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
