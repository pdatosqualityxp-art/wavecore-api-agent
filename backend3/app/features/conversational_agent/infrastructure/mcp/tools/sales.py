from datetime import date
from decimal import Decimal
from typing import Any

from app.features.conversational_agent.infrastructure.persistence.supabase import (
    get_supabase_client,
)

PAGE_SIZE = 1000
SALES_COLUMNS = (
    "id_venta, id_cliente, id_prod, unidades, total_venta, fecha_venta, "
    "productos(nom_prod)"
)


def _fetch_all_sales(
    *,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    id_cliente: str | None = None,
    id_prod: str | None = None,
) -> list[dict[str, Any]]:
    client = get_supabase_client()
    sales: list[dict[str, Any]] = []
    start = 0

    while True:
        query = (
            client.table("ventas")
            .select(SALES_COLUMNS)
            .order("fecha_venta", desc=True)
            .order("id_venta")
        )
        if fecha_desde is not None:
            query = query.gte("fecha_venta", fecha_desde.isoformat())
        if fecha_hasta is not None:
            query = query.lte("fecha_venta", fecha_hasta.isoformat())
        if id_cliente is not None:
            query = query.eq("id_cliente", id_cliente)
        if id_prod is not None:
            query = query.eq("id_prod", id_prod)

        page = query.range(start, start + PAGE_SIZE - 1).execute().data
        sales.extend(page)
        if len(page) < PAGE_SIZE:
            return sales
        start += PAGE_SIZE


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _format_sale(row: dict[str, Any]) -> dict[str, Any]:
    product = row.get("productos")
    if isinstance(product, list):
        product = product[0] if product else None
    return {
        "id_venta": row["id_venta"],
        "id_cliente": row.get("id_cliente"),
        "producto": product.get("nom_prod") if product else None,
        "unidades": row["unidades"],
        "total_venta": float(_decimal(row["total_venta"])),
        "fecha_venta": row["fecha_venta"],
    }


def get_sales_data(
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    id_cliente: str | None = None,
    id_prod: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Consulta ventas y métricas para análisis comercial con filtros opcionales."""
    if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
        raise ValueError("fecha_desde no puede ser posterior a fecha_hasta")
    for name, value in (("id_cliente", id_cliente), ("id_prod", id_prod)):
        if value is not None and (not value.strip() or len(value) > 50):
            raise ValueError(f"{name} debe tener entre 1 y 50 caracteres")
    if isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100")

    sales = _fetch_all_sales(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        id_cliente=id_cliente,
        id_prod=id_prod,
    )
    total_sales = sum((_decimal(row["total_venta"]) for row in sales), Decimal(0))
    count = len(sales)
    return {
        "metricas": {
            "num_ventas": count,
            "unidades_totales": sum(int(row["unidades"]) for row in sales),
            "total_ventas": float(total_sales),
            "ticket_medio": float(total_sales / count) if count else 0.0,
        },
        "ventas": [_format_sale(row) for row in sales[:limit]],
        "truncado": count > limit,
    }


def get_client_summary(id_cliente: str) -> dict[str, Any]:
    """Resume compras, gasto y ventas recientes de un cliente identificado."""
    if not id_cliente.strip() or len(id_cliente) > 50:
        raise ValueError("id_cliente debe tener entre 1 y 50 caracteres")

    client = get_supabase_client()
    result = (
        client.table("clientes")
        .select("id_cliente, nom_cliente, poblacion_cliente, pais_cliente")
        .eq("id_cliente", id_cliente)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(f"No existe el cliente '{id_cliente}'")

    sales = _fetch_all_sales(id_cliente=id_cliente)
    total_spent = sum(
        (_decimal(row["total_venta"]) for row in sales),
        Decimal(0),
    )
    return {
        "cliente": result.data[0],
        "num_compras": len(sales),
        "total_gastado": float(total_spent),
        "ultima_venta": sales[0]["fecha_venta"] if sales else None,
        "ultimas_ventas": [_format_sale(row) for row in sales[:5]],
    }
