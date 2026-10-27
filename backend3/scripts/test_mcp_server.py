import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BACKEND_DIR = Path(__file__).resolve().parents[1]


def tool_json(result: object) -> object:
    if getattr(result, "isError", False):
        messages = [
            item.text
            for item in getattr(result, "content", [])
            if hasattr(item, "text")
        ]
        raise RuntimeError("La herramienta MCP devolvió un error: " + "\n".join(messages))

    values = []
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            try:
                values.append(json.loads(text))
            except json.JSONDecodeError:
                continue
    if values:
        return values[0] if len(values) == 1 else values
    raise RuntimeError("La herramienta MCP no devolvió JSON en su respuesta")


async def main() -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.features.conversational_agent.infrastructure.mcp.server"],
        cwd=str(BACKEND_DIR),
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            expected = {
                "get_sales_data",
                "get_client_summary",
                "search_document_chunks",
            }
            if names != expected:
                raise RuntimeError(f"Herramientas inesperadas: {sorted(names)}")
            print(f"Herramientas MCP: {', '.join(sorted(names))}")

            sales = tool_json(
                await session.call_tool("get_sales_data", {"limit": 2})
            )
            if len(sales["ventas"]) > 2:
                raise RuntimeError("get_sales_data excedió limit=2")
            if sales["metricas"]["num_ventas"] < len(sales["ventas"]):
                raise RuntimeError("Las métricas no incluyen todas las ventas")
            if sales["truncado"] != (sales["metricas"]["num_ventas"] > 2):
                raise RuntimeError("El indicador truncado no coincide con las métricas")
            print("get_sales_data:", json.dumps(sales, ensure_ascii=False))

            if sales["ventas"]:
                client_id = sales["ventas"][0]["id_cliente"]
                if client_id:
                    summary = tool_json(
                        await session.call_tool(
                            "get_client_summary", {"id_cliente": client_id}
                        )
                    )
                    print(
                        "get_client_summary:",
                        json.dumps(summary, ensure_ascii=False),
                    )

            search = tool_json(
                await session.call_tool(
                    "search_document_chunks",
                    {"query": "estudios de mercado hostelería y bebidas", "top_k": 3},
                )
            )
            if len(search) > 3:
                raise RuntimeError("search_document_chunks excedió top_k=3")
            if any(
                search[i]["similarity"] < search[i + 1]["similarity"]
                for i in range(len(search) - 1)
            ):
                raise RuntimeError("Los chunks no están ordenados por similitud")
            source_chunk = search[0]
            self_search = tool_json(
                await session.call_tool(
                    "search_document_chunks",
                    {"query": source_chunk["chunk_text"][:1000], "top_k": 5},
                )
            )
            if (
                not self_search
                or self_search[0]["id"] != source_chunk["id"]
                or self_search[0]["similarity"] < 0.9
            ):
                raise RuntimeError(
                    "La búsqueda del texto de un chunk no recuperó su propio chunk"
                )
            print(
                "search_document_chunks:",
                json.dumps(
                    [
                        {
                            "id": chunk["id"],
                            "document_id": chunk["document_id"],
                            "page_number": chunk["page_number"],
                            "similarity": chunk["similarity"],
                        }
                        for chunk in search
                    ],
                    ensure_ascii=False,
                ),
            )
            print(
                "Búsqueda del texto de un chunk:",
                f"id={self_search[0]['id']}, "
                f"similarity={self_search[0]['similarity']:.4f}",
            )

            invalid_limit = await session.call_tool(
                "get_sales_data", {"limit": 500}
            )
            if not getattr(invalid_limit, "isError", False):
                raise RuntimeError("Se esperaba un error para limit=500")
            invalid_dates = await session.call_tool(
                "get_sales_data",
                {"fecha_desde": "2026-02-01", "fecha_hasta": "2026-01-01"},
            )
            if not getattr(invalid_dates, "isError", False):
                raise RuntimeError("Se esperaba un error para un rango de fechas inválido")
            print("Validaciones de limit y fechas: correctas")

            invalid = await session.call_tool(
                "get_client_summary", {"id_cliente": "__cliente_inexistente__"}
            )
            if not getattr(invalid, "isError", False):
                raise RuntimeError("Se esperaba un error para un cliente inexistente")
            print("Cliente inexistente: error controlado")


if __name__ == "__main__":
    asyncio.run(main())
