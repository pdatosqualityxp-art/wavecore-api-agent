# Spec 003: Agente LangChain con Google Gemini y Herramientas MCP

## 1. Objetivo

Crear un agente conversacional en Python utilizando LangChain y la API de Google Gemini, integrando las herramientas del servidor MCP (`002_mcp_server_spec.md`) **a través de un cliente MCP real** (transporte `stdio`), sin importar directamente las funciones Python de las herramientas. Cada interacción se persiste en la tabla `chat_logs` de Supabase, que sirve tanto de auditoría como de memoria conversacional (historial reconstruido por `conversation_id`). El comportamiento se verifica con un script interactivo por consola y con pruebas automatizadas.

### 1.1. Decisiones de Alcance

* **Cliente MCP real:** el agente arranca `server.py` como subproceso y se comunica por `stdio` (sesión, inicialización, listado y llamada de herramientas). Queda prohibido importar `get_sales_data`, `get_client_summary` o `search_document_chunks` desde el agente o sus adaptadores.
* **Fallback acotado:** el modelo de respaldo aplica **únicamente** al modelo conversacional (`GEMINI_AGENT_MODEL`) ante fallos transitorios de la API. Los embeddings siguen siendo independientes (`GEMINI_EMBEDDING_MODEL`, `infrastructure/gemini/embeddings.py`) y no usan este mecanismo.
* **Memoria y auditoría en BD:** `chat_logs` es la única fuente de memoria; no hay memoria en proceso entre ejecuciones.
* **Sin seguridad en esta fase:** no hay autenticación (*Security Last*). `user` y `client_ip` son opcionales; `user` toma por defecto `"anonymous"` y `client_ip` es `None` en consola. Cuando se implemente JWT (spec 005 / 005b), solo cambia el origen de estos valores.

## 2. Requisitos Previos

* `002_mcp_server_spec.md` completado y verificado (servidor ejecutable por `stdio`).
* Variables de entorno `GOOGLE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` configuradas en `.env`; `GEMINI_AGENT_MODEL` y `GEMINI_FALLBACK_MODEL` disponibles en `app/core/config.py`.
* Tabla `chat_logs` creada en Supabase (ver sección 3.4).
* Librerías `langchain`, `langchain-core`, `langchain-google-genai` y `mcp` instaladas en el entorno virtual (`requirements_file.txt`). Para pruebas: `pytest` y `pytest-asyncio`.

## 3. Entregables y Componentes a Crear

### 3.1. Modelo LLM y Herramientas MCP (infraestructura)

* **`app/features/conversational_agent/infrastructure/llm/gemini.py`**: Adaptador del cliente Gemini con `ChatGoogleGenerativeAI`. Lee los modelos de `get_settings()` (nunca valores estáticos) y construye el modelo principal (`GEMINI_AGENT_MODEL`) con reintentos y el modelo de respaldo (`GEMINI_FALLBACK_MODEL`) encadenado como fallback (ver Paso 1).
* **`app/features/conversational_agent/infrastructure/mcp/client.py`**: Cliente MCP con el ciclo de vida completo sobre `stdio`: lanzamiento del subproceso de `server.py`, `ClientSession`, `initialize()`, `list_tools()` y `call_tool()`, y cierre limpio. Expuesto como *async context manager*.
* **`app/features/conversational_agent/infrastructure/mcp/langchain_tools.py`**: Adaptador que convierte las herramientas descubiertas vía `list_tools()` en `StructuredTool` de LangChain (nombre, descripción y `args_schema` derivados del `inputSchema` JSON de cada herramienta). Cada invocación delega en `ClientSession.call_tool()`.

### 3.2. Persistencia, Memoria y Auditoría

* **`app/features/conversational_agent/domain/chat_log.py`**: modelos Pydantic `ChatLogEntry` (campos de la sección 3.4), `AgentResult` y `ToolCallTrace`, y el puerto `ChatLogRepository` (interfaz pura: `add(entry)` y `list_by_conversation(conversation_id, limit)`), sin dependencias de Supabase.
* **`app/features/conversational_agent/infrastructure/persistence/chat_logs.py`**: implementación Supabase de `ChatLogRepository`, usando `get_supabase_client()`.
* **`app/features/conversational_agent/application/services/chat_logger.py`**: servicio que registra cada interacción y reconstruye el historial. Es el mismo servicio previsto en `004b_chat_logs.md`, que lo reutilizará desde el endpoint en lugar de crearlo.

### 3.3. Construcción del Agente y CLI

* **`app/features/conversational_agent/application/prompts.py`**: Prompts del sistema: rol, restricciones y comportamiento analítico del agente.
* **`app/features/conversational_agent/application/agent.py`**: Caso de uso del agente. Con la versión instalada (LangChain 1.x) `AgentExecutor` / `create_tool_calling_agent` ya no forman parte del paquete principal, por lo que se usa su equivalente vigente `langchain.agents.create_agent`. Carga el historial desde `chat_logs`, ejecuta el agente, recopila los pasos de herramientas y registra la interacción. Recibe el LLM, las herramientas y los middlewares por inyección (no importa `langchain_google_genai` ni `mcp`).
* **`backend3/scripts/interactive_chat.py`**: CLI interactivo que compone las piezas (cliente MCP, LLM, repositorio) y muestra la traza limpia de herramientas (sección 5, Paso 6).

### 3.4. Tabla `chat_logs`

La tabla `chat_logs` ya existe en Supabase (verificado al implementar) con estas columnas, incluidas `api`, `user` y `conversation_id`; no hace falta ejecutar DDL. La definición de referencia, por si hay que recrearla:

```sql
CREATE TABLE IF NOT EXISTS chat_logs (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    api              VARCHAR(50)  NOT NULL DEFAULT '3 agent av',
    "user"           VARCHAR(100) DEFAULT 'anonymous',
    model_used       VARCHAR(100),
    prompt           TEXT NOT NULL,
    reply            TEXT,
    prompt_tokens    INTEGER,
    response_tokens  INTEGER,
    total_tokens     INTEGER,
    client_ip        VARCHAR(45),
    conversation_id  UUID NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_logs_conversation
    ON chat_logs (conversation_id, created_at);
```

| Campo | Valor en esta fase |
|-------|--------------------|
| `api` | `"3 agent av"` (fijo) |
| `user` | `"anonymous"` por defecto (o `None`) |
| `model_used` | Modelo que **realmente** respondió (principal o fallback), ej. `gemini-2.5-flash` |
| `prompt` / `reply` | Pregunta del usuario / respuesta final del agente |
| `prompt_tokens`, `response_tokens`, `total_tokens` | Tomados de `usage_metadata` de las respuestas del LLM, **sumados** si el agente hizo varias llamadas al modelo; `None` si no están disponibles |
| `client_ip` | `None` en consola |
| `conversation_id` | UUID de la sesión; se genera al iniciar la CLI o se reanuda con `--conversation-id` |

## 4. Estructura de Archivos

```
backend3/
├── app/
│   └── features/
│       └── conversational_agent/
│           ├── domain/
│           │   └── chat_log.py              # ChatLogEntry, AgentResult + puerto ChatLogRepository
│           ├── application/
│           │   ├── prompts.py
│           │   ├── agent.py
│           │   └── services/
│           │       └── chat_logger.py
│           └── infrastructure/
│               ├── llm/
│               │   └── gemini.py
│               ├── mcp/
│               │   ├── server.py            # existente (no se modifica)
│               │   ├── client.py
│               │   └── langchain_tools.py
│               └── persistence/
│                   └── chat_logs.py
├── scripts/
│   └── interactive_chat.py
└── tests/
    ├── unit/                                # sin red ni Gemini
    │   ├── test_mcp_client_adapter.py
    │   ├── test_chat_logger.py
    │   └── test_gemini_fallback.py
    └── conversational/                      # requieren GOOGLE_API_KEY y Supabase
        └── test_agent_conversations.py
```

## 5. Plan de Implementación Técnico

### Paso 1: Modelo Gemini con reintentos y fallback (`infrastructure/llm/gemini.py`)
* Modelo principal: `ChatGoogleGenerativeAI(model=settings.GEMINI_AGENT_MODEL, temperature=0.2, retries=settings.GEMINI_MAX_RETRIES)`. Nuevas opciones en `config.py` / `.env.example`: `GEMINI_MAX_RETRIES` (2) y `CHAT_HISTORY_TURNS` (10).
* Fallback: middleware propio `TransientFallbackMiddleware` (el `ModelFallbackMiddleware` de LangChain captura cualquier excepción, por lo que no se usa) que, ante un error transitorio del principal (429, 5xx, timeouts/errores de conexión), repite la llamada con un segundo `ChatGoogleGenerativeAI(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.2)`. Errores no transitorios (400, 401/403, argumentos inválidos) se propagan sin cambiar de modelo.
* El adaptador debe permitir conocer qué modelo respondió (campo `response_metadata["model_name"]` del mensaje) para rellenar `model_used`.
* No se usa este adaptador para embeddings.

### Paso 2: Cliente MCP por `stdio` (`infrastructure/mcp/client.py`)
* Usar `StdioServerParameters(command=sys.executable, args=["-m", "app.features.conversational_agent.infrastructure.mcp.server"], cwd=<backend3>, env=<entorno heredado + PYTHONPATH=<backend3>>)`, de modo que el subproceso resuelva el paquete `app` y cargue el `.env` igual que el resto de la aplicación.
* Ciclo de vida como `async with McpClient() as client`: `stdio_client` → `ClientSession` → `await session.initialize()` → `list_tools()` / `call_tool(name, arguments)` → cierre del subproceso al salir (incluyendo salida por excepción o `Ctrl+C`).
* Un único subproceso y sesión por ejecución de la CLI; no se arranca un servidor por pregunta.
* Gestión de errores: si `call_tool` devuelve `isError=True` o el subproceso muere, el adaptador devuelve al agente un mensaje de error legible (para que pueda explicarlo o reintentar) sin romper el bucle del chat.

### Paso 3: Adaptar herramientas MCP (`infrastructure/mcp/langchain_tools.py`)
* Descubrir las herramientas con `list_tools()` (sin lista fija en código) y crear un `StructuredTool` por cada una con `args_schema` generado a partir de `inputSchema`.
* La función asíncrona de cada tool llama a `session.call_tool()` y convierte el contenido devuelto (texto/JSON) en una cadena para el LLM.
* Herramientas esperadas por el servidor actual: `get_sales_data`, `get_client_summary`, `search_document_chunks`.
* Las fechas llegan como cadenas ISO (`YYYY-MM-DD`); el schema debe permitir `null` en los parámetros opcionales para evitar desajustes de tipos.

### Paso 4: Definir prompts del sistema (`application/prompts.py`)
* Rol: asistente analítico de WaveCore Manager.
* Reglas: consultar siempre las herramientas antes de dar cifras o afirmaciones sobre documentos; no inventar datos; indicar cuando una herramienta no devuelve resultados o el resultado está truncado (`truncado: true`); combinar ventas y documentos cuando la pregunta lo requiera; responder en el idioma del usuario.

### Paso 5: Ensamblar el agente con memoria en BD (`application/agent.py` + `services/chat_logger.py`)
* Por cada turno: (1) `list_by_conversation(conversation_id)` ordenado por `created_at`, (2) convertir las filas `prompt`/`reply` en mensajes `Human`/`AI` y limitarlos a los últimos *N* turnos (configurable) para controlar el contexto, (3) ejecutar el agente con LLM, herramientas y prompt, (4) registrar el turno en `chat_logs`.
* Solo se persisten `prompt` y `reply`; los mensajes intermedios de herramientas no se reconstruyen en el historial.
* El registro **no es bloqueante**: si falla la inserción en Supabase se emite un aviso en el log y la respuesta al usuario no se ve afectada (coherente con `004b_chat_logs.md`).
* Los tokens se suman a partir del `usage_metadata` de cada llamada al LLM del turno.
* `user` por defecto `"anonymous"` y `client_ip` `None`; ambos son parámetros opcionales del caso de uso para que la futura capa de seguridad solo tenga que informarlos.

### Paso 6: Script de consola (`backend3/scripts/interactive_chat.py`)
* **Ejecución:** desde el directorio `backend3/`, con `PYTHONPATH` apuntando a `backend3/` (el script no debe depender del directorio de trabajo para resolver `app`):

  ```powershell
  cd backend3
  $env:PYTHONPATH = (Get-Location).Path
  python scripts/interactive_chat.py [--conversation-id <uuid>]
  ```
  ```bash
  cd backend3
  PYTHONPATH=. python scripts/interactive_chat.py [--conversation-id <uuid>]
  ```
* Sin `--conversation-id` se genera un UUID nuevo y se muestra al inicio; con él se reanuda una conversación existente cargando su historial de `chat_logs`.
* **Trazabilidad limpia:** por cada pregunta se imprime, en este orden, y nada más:
  1. Herramienta invocada (nombre).
  2. Argumentos pasados (JSON).
  3. Resultado devuelto (recortado a una longitud máxima configurable para legibilidad).
  4. Respuesta final del agente.
* No se muestran razonamientos internos del LLM ni bloques de "thinking". Se evitan las trazas verbosas del framework (`verbose=False`); la traza se construye a partir de los pasos intermedios del agente (acción + observación).
* Comando de salida: `exit` / `quit` / `Ctrl+C`, con cierre ordenado del cliente MCP.

## 6. Criterios de Aceptación y Verificación

### 6.1. Pruebas unitarias (sin Gemini ni red; `tests/unit/`)

* **Adaptador MCP:** arrancando el servidor real por `stdio` (o un servidor MCP de prueba mínimo con las mismas firmas), `list_tools()` devuelve `get_sales_data`, `get_client_summary` y `search_document_chunks`; los `StructuredTool` generados exponen los argumentos y tipos correctos; una llamada con argumentos válidos devuelve contenido y una con argumentos inválidos (ej. `limit=0`) devuelve un error controlado sin colgar la sesión. Verificar que el subproceso termina al cerrar el contexto.
* **Sin importación directa:** ningún módulo de `application/` ni de `infrastructure/mcp/client.py` / `langchain_tools.py` importa `tools.sales` o `tools.documents`.
* **Fallback:** con un LLM simulado que lanza un error transitorio, se usa `GEMINI_FALLBACK_MODEL` y `model_used` refleja el modelo de respaldo; con un error no transitorio no hay fallback. Los embeddings no pasan por este mecanismo.
* **`chat_logger`:** con un repositorio en memoria, se inserta un registro con `api="3 agent av"`, `user="anonymous"` y `client_ip=None` por defecto; el historial se reconstruye en orden filtrando por `conversation_id` (dos conversaciones no se mezclan); un fallo del repositorio no propaga la excepción.

### 6.2. Pruebas conversacionales (Gemini + MCP + Supabase reales; `tests/conversational/`)

Requieren credenciales; se marcan (`@pytest.mark.conversational`) y no se ejecutan en CI por defecto. Se validan mediante los pasos de herramientas capturados, no solo el texto de la respuesta.

| # | Tipo | Entrada de prueba | Verificación |
|---|------|-------------------|--------------|
| 1 | Comercial | "¿Cuánto hemos vendido en total durante 2026 y cuál ha sido el ticket medio?" | Se invoca `get_sales_data` con `fecha_desde=2026-01-01` y `fecha_hasta=2026-12-31`; **no** se invoca `search_document_chunks`; la respuesta cita `total_ventas` y `ticket_medio` devueltos por la herramienta. |
| 2 | Documental | "¿Qué condiciones de garantía o mantenimiento aparecen en los documentos?" | Se invoca `search_document_chunks` con una `query` no vacía; **no** se invoca `get_sales_data`; la respuesta se apoya en `chunk_text` devueltos. |
| 3 | Mixta | "Dame las ventas del cliente `CLI0001` y comprueba si los documentos mencionan condiciones especiales para él." | Se invocan `get_client_summary` (o `get_sales_data`) **y** `search_document_chunks` antes de la respuesta final; la respuesta integra ambas fuentes. |

Los datos actuales de ventas cubren 2026–2027 (consultar 2024/2025 devuelve cero ventas). El id del cliente puede cambiarse con la variable `TEST_CLIENT_ID`. Dado el carácter no determinista del LLM, cada caso se evalúa sobre el **conjunto** de herramientas invocadas (y orden solo cuando es relevante), no sobre el texto exacto. Ejecución: `pytest -m conversational` desde `backend3/` (excluidas por defecto en `pytest.ini`).

Criterios adicionales:
* Cada caso genera exactamente un registro en `chat_logs` con `api="3 agent av"`, `model_used` no nulo, `prompt` y `reply` coherentes, tokens poblados (`total_tokens = prompt_tokens + response_tokens`) y el mismo `conversation_id` dentro de la sesión.
* Memoria: tras la pregunta 1, un seguimiento como "¿y en 2023?" se resuelve usando el contexto reconstruido desde `chat_logs` filtrando por `conversation_id`; reanudar la CLI con `--conversation-id` conserva ese contexto.
* `python scripts/interactive_chat.py`, ejecutado desde `backend3/` con `PYTHONPATH` configurado, transcurre sin errores de invocación de API ni desajustes de tipos en los argumentos, y la salida cumple el formato de trazabilidad limpia del Paso 6 (sin razonamiento interno del LLM).

## 7. Fuera de Alcance

* Autenticación, validación JWT y obtención real de `user` / `client_ip` (specs 005 y 005b).
* Exposición HTTP del agente (spec 004) y su integración con `chat_logs` (spec 004b), que reutilizarán `chat_logger.py`.
* Persistencia de mensajes intermedios de herramientas en el historial.