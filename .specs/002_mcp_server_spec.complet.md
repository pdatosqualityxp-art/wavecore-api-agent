# Spec 002: Servidor MCP (Model Context Protocol)

## 0. Ficheros implicados

Rutas relativas a la raíz del repositorio.

### Crear o modificar
- `backend3/app/features/conversational_agent/infrastructure/mcp/tools/sales.py`: herramientas de ventas y resumen de cliente.
- `backend3/app/features/conversational_agent/infrastructure/mcp/tools/documents.py`: búsqueda semántica de fragmentos.
- `backend3/app/features/conversational_agent/infrastructure/mcp/server.py`: registro y ejecución del servidor MCP por stdio.
- `backend3/app/features/conversational_agent/infrastructure/gemini/embeddings.py`: generación de embeddings de consulta.
- `backend3/scripts/test_mcp_server.py`: prueba del servidor y sus herramientas.
- `.specs/database/functions/match_document_chunks.sql`: función RPC de búsqueda vectorial para aplicar en Supabase.
- `backend3/app/core/config.py`: configuración de `GEMINI_EMBEDDING_MODEL`.
- `requirements_file.txt`: dependencia del SDK MCP compatible con `FastMCP`.

### Referencias
- `backend3/app/features/conversational_agent/infrastructure/persistence/supabase.py`: cliente reutilizable configurado en la spec 001.
- `.specs/database/schema.sql`: esquema de ventas, clientes, productos y `document_chunks`.
- `.specs/database/relationships.md`: relaciones entre ventas, productos y clientes.
- `.specs/001_supabase_connection_spec.md`: configuración y verificación de la conexión a Supabase.
- `.env`: variables locales de Supabase y Gemini; contiene secretos y no debe versionarse.

## 1. Objetivo

Empaquetar las consultas a Supabase en herramientas estandarizadas mediante el SDK de MCP en Python (`FastMCP`), expuestas por transporte **stdio**, para:

* Consultar datos de ventas y métricas comerciales.
* Obtener un resumen de cliente.
* Búsqueda semántica sobre `document_chunks` a partir de **texto** (el servidor genera el embedding).

---

## 2. Requisitos Previos

* `001_supabase_connection_spec.md` completado y verificado (cliente en `app/features/conversational_agent/infrastructure/persistence/supabase.py`).
* Dependencia `mcp>=1.0.0,<2.0.0` instalada en el entorno virtual (`venv/`), ya que el servidor usa `FastMCP` de la API 1.x.
* `GOOGLE_API_KEY` configurada en `.env` (la usa el embedding de consultas).
* **Modelo de embeddings idéntico al de ingesta.** Configurado con `GEMINI_EMBEDDING_MODEL` (por defecto `gemini-embedding-001`, 768 dimensiones). Verificado: un chunk existente re-embebido con ese modelo tiene similitud coseno 1.0000 con su embedding guardado. Si se cambia el modelo, la búsqueda deja de funcionar.

---

## 3. Entregables y Componentes a Crear

### 3.1. Herramientas MCP (MCP Tools)
* **`app/features/conversational_agent/infrastructure/mcp/tools/sales.py`**: `get_sales_data` y `get_client_summary`.
* **`app/features/conversational_agent/infrastructure/mcp/tools/documents.py`**: `search_document_chunks` (búsqueda semántica con `pgvector`).

### 3.2. Servidor MCP
* **`app/features/conversational_agent/infrastructure/mcp/server.py`**: Instancia `FastMCP`, registra las herramientas y expone `main()` para arrancar por stdio.

### 3.3. Embeddings de consulta
* **`app/features/conversational_agent/infrastructure/gemini/embeddings.py`**: Función `embed_query(text: str) -> list[float]` que llama a la API de embeddings de Gemini con `output_dimensionality=768`. Reutilizada por la herramienta de documentos.

### 3.4. SQL de la función de búsqueda
* **`.specs/database/functions/match_document_chunks.sql`**: Función RPC que ordena por distancia coseno. Se aplica manualmente en el *SQL Editor* de Supabase.

### 3.5. Script de Prueba MCP
* **`scripts/test_mcp_server.py`**: Lanza el servidor como subproceso por stdio con un cliente MCP, lista las herramientas e invoca cada una.

## 4. Estructura de Archivos

```text
backend3/
├── app/
│   └── features/
│       └── conversational_agent/
│           └── infrastructure/
│               ├── gemini/
│               │   └── embeddings.py
│               └── mcp/
│                   ├── server.py
│                   └── tools/
│                       ├── sales.py
│                       └── documents.py
└── scripts/
    └── test_mcp_server.py

.specs/database/functions/
└── match_document_chunks.sql
```

## 5. Plan de Implementación Técnico

### Paso 1: Herramientas comerciales (`infrastructure/mcp/tools/sales.py`)

**`get_sales_data`** — parámetros tipados, sin `dict` libre:

| Parámetro | Tipo | Por defecto | Validación |
|---|---|---|---|
| `fecha_desde` | `date \| None` | `None` | ISO `YYYY-MM-DD` |
| `fecha_hasta` | `date \| None` | `None` | ISO; si se da con `fecha_desde`, debe ser ≥ |
| `id_cliente` | `str \| None` | `None` | Máx. 50 caracteres |
| `id_prod` | `str \| None` | `None` | Máx. 50 caracteres |
| `limit` | `int` | `20` | Entre 1 y 100 |

Devuelve:
```json
{
  "metricas": {
    "num_ventas": 0,
    "unidades_totales": 0,
    "total_ventas": 0.0,
    "ticket_medio": 0.0
  },
  "ventas": [
    {"id_venta": "...", "id_cliente": "...", "producto": "...", "unidades": 0, "total_venta": 0.0, "fecha_venta": "YYYY-MM-DD"}
  ],
  "truncado": false
}
```
* `metricas` se calcula sobre **todas** las ventas que cumplen los filtros, no solo sobre las `limit` devueltas.
* `ticket_medio = total_ventas / num_ventas` (0 si no hay ventas).
* `truncado = true` si hay más ventas que `limit`.
* Se resuelve el nombre de producto mediante el join `ventas.id_prod → productos.id_prod`.

**`get_client_summary(id_cliente: str)`**:
```json
{
  "cliente": {"id_cliente": "...", "nom_cliente": "...", "poblacion_cliente": "...", "pais_cliente": "..."},
  "num_compras": 0,
  "total_gastado": 0.0,
  "ultima_venta": "YYYY-MM-DD | null",
  "ultimas_ventas": []
}
```
* `ultimas_ventas`: últimas 5 ventas del cliente, ordenadas por `fecha_venta` descendente.
* Si el cliente no existe, devuelve un error de herramienta claro (no una excepción sin tratar).

### Paso 2: Búsqueda semántica (`infrastructure/mcp/tools/documents.py`)

**`search_document_chunks(query: str, top_k: int = 5)`**:
1. Valida `query` (no vacía, máx. 1000 caracteres) y `top_k` (1–20).
2. Genera el embedding con `embed_query(query)` (`infrastructure/gemini/embeddings.py`).
3. Llama a la RPC `match_document_chunks` vía `supabase.rpc(...)`.
4. Devuelve `[{"id", "document_id", "page_number", "chunk_text", "similarity"}]`, sin el campo `embedding`.

**Función SQL** (`.specs/database/functions/match_document_chunks.sql`):
```sql
create or replace function public.match_document_chunks(
  query_embedding vector(768),
  match_count int default 5
)
returns table (
  id int,
  document_id varchar,
  page_number int,
  chunk_text text,
  similarity float
)
language sql stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.page_number,
    dc.chunk_text,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  where dc.embedding is not null
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
```
* Con RLS activo, la función debe ejecutarse con permisos que puedan leer `document_chunks`. Con la clave `secret` no hay problema; si se usa `anon`, hará falta una política de lectura.

### Paso 3: Servidor (`infrastructure/mcp/server.py`)
* Crear `mcp = FastMCP("wavecore-data")`.
* Registrar las tres herramientas con `@mcp.tool()`. Las descripciones deben indicar al LLM cuándo usar cada una.
* Función `main()` que llama a `mcp.run(transport="stdio")`.
* Los logs van a `stderr`; **nunca a `stdout`**, porque corrompen el protocolo stdio.

### Paso 4: Script de prueba (`scripts/test_mcp_server.py`)
* Arranca el servidor con `StdioServerParameters` (`sys.executable`, `-m app.features.conversational_agent.infrastructure.mcp.server`, cwd `backend3/`).
* Llama a `list_tools()` y comprueba que aparecen las tres herramientas.
* Invoca cada herramienta con parámetros de ejemplo e imprime el resultado. Para `get_client_summary`, usa un `id_cliente` obtenido antes con `get_sales_data`.

---

## 6. Criterios de Aceptación y Verificación

* `python -c "import app.features.conversational_agent.infrastructure.mcp.server"` (desde `backend3/`) no falla.
* `python scripts/test_mcp_server.py` lista las tres herramientas y todas responden con JSON válido y la estructura de la sección 5.
* `get_sales_data` con `limit=2` devuelve como máximo 2 ventas, `truncado=true` y `metricas` calculadas sobre el total.
* `get_sales_data` con `fecha_desde > fecha_hasta` o `limit=500` devuelve error de validación.
* `get_client_summary` con un id inexistente devuelve un error controlado.
* `search_document_chunks` devuelve chunks ordenados por `similarity` descendente. Al buscar el texto de un chunk existente, este aparece primero con similitud ≥ 0.9 (la consulta usa `RETRIEVAL_QUERY`, mientras que el embedding almacenado se generó como documento).
* No se imprime nada en `stdout` desde el servidor fuera del protocolo MCP.

## 7. Fuera de alcance

* Autenticación de las herramientas (se trata en la spec de seguridad).
* Transporte HTTP/SSE.
* Escritura en la base de datos: todas las herramientas son de solo lectura.