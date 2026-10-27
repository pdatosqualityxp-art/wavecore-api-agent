# Spec 004: Exposición del Agente mediante API Web con FastAPI

## 1. Objetivo

Envolver el agente conversacional de LangChain en una API REST robusta utilizando FastAPI. Se expondrán endpoints HTTP para interactuar con el chat (recibiendo preguntas y devolviendo respuestas del agente) y se validará el correcto funcionamiento mediante la interfaz interactiva de Swagger UI (`/docs`).

## 2. Requisitos Previos

* `003-langchain-gemini-agent.md` completado y verificado.

* Agente de LangChain funcionando correctamente de forma aislada.

* Librerías `fastapi` y `uvicorn` instaladas en el entorno virtual.

## 3. Entregables y Componentes a Crear

### 3.1. Esquemas de Petición y Respuesta (Pydantic)

* **`app/features/conversational_agent/infrastructure/api/schemas/chat.py`**: Modelos de transporte HTTP para validar las entradas (`ChatRequest`) y salidas (`ChatResponse`, metadatos de herramientas usadas, modelo/tokens y tiempo de respuesta).

### 3.2. Endpoints de la API

* **`app/features/conversational_agent/infrastructure/api/v1/endpoints/chat.py`**: Ruta POST `/api/v1/chat` que delega en el caso de uso del agente.

* **`app/features/conversational_agent/infrastructure/api/v1/endpoints/health.py`**: Ruta GET `/health` para verificación del estado del servidor.

### 3.3. Servidor Principal FastAPI

* **`app/main.py`**: Aplicación FastAPI con configuración de CORS, routers e inicialización global.

## 4. Estructura de Archivos

```
backend3/
├── app/
│   ├── main.py
│   └── features/
│       └── conversational_agent/
│           ├── domain/
│           ├── application/
│           └── infrastructure/
│               └── api/
│                   ├── schemas/
│                   │   └── chat.py
│                   └── v1/
│                       ├── router.py
│                       └── endpoints/
│                           ├── health.py
│                           └── chat.py
```

## 5. Plan de Implementación Técnico

### Paso 1: Definir Esquemas HTTP (`app/features/conversational_agent/infrastructure/api/schemas/chat.py`)

* `ChatRequest`: Atributos `message` (str) y `session_id` (UUID, opcional). Si se omite, el servidor genera un identificador.

* No se acepta `history`: el historial se recupera en el servidor desde `chat_logs` usando el `session_id`.

* `ChatResponse`: Atributos `response` (str), `session_id` (UUID), `tool_calls`, metadatos de modelo/tokens y tiempo de respuesta.

### Paso 2: Crear Endpoint `/chat` (`app/features/conversational_agent/infrastructure/api/v1/endpoints/chat.py`)

* Recibir la petición HTTP POST y delegar en el caso de uso de `app/features/conversational_agent/application/agent.py`; no acceder directamente a Supabase ni inicializar Gemini desde el endpoint.

* Retornar la respuesta estructurada. Errores de validación (incluido un UUID inválido o campos no admitidos) responden con HTTP 422; errores inesperados del agente responden con HTTP 500 sin exponer detalles internos.

### Paso 3: Configurar Aplicación Principal (`app/main.py`)

* Inicializar `FastAPI(title="WaveCore Agent API", version="1.0.0")`.

* Incluir los routers de la API v1 y Middleware de CORS, configurando los orígenes permitidos mediante `CORS_ORIGINS` (separados por comas).

## 6. Criterios de Aceptación y Verificación

* El servidor arranca sin errores ejecutando `uvicorn app.main:app --reload`.

* La documentación interactiva está accesible en `http://localhost:8000/docs`.

* Peticiones POST enviadas a `/api/v1/chat` desde Swagger o cURL responden correctamente con el texto generado por el agente y el detalle de la interacción.

* Si se omite `session_id`, la API devuelve un UUID generado que puede reutilizarse en turnos posteriores. El historial se administra en el servidor y no se acepta en la petición.