# WaveCore Manager - Backend 3 (MCP & Agentic RAG) xp

Backend de microservicio avanzado desarrollado en **Python con FastAPI**, diseñado para actuar como el núcleo de razonamiento inteligente de **WaveCore Manager**. Este servicio implementa un sistema de agentes basados en **LangChain**, integrados mediante **Model Context Protocol (MCP)** para realizar consultas cruzadas avanzadas entre las tablas relacionales de **Supabase** y los fragmentos vectoriales (*chunks*) de los documentos corporativos.

---

## 🚀 Stack Tecnológico

* **Core & API:** Python 3.10+, FastAPI (con Swagger UI integrado), Uvicorn.
* **IA & Orquestación:** LangChain, Google Gemini API.
* **Protocolo & Datos:** MCP (Model Context Protocol) SDK, Supabase (PostgreSQL + pgvector).
* **Contenedorización:** Docker.
* **DevOps & Seguridad:** Render, GitHub Actions, JWT (Supabase Auth), CORS.

---

## 🏛️ Arquitectura

El proyecto sigue una estructura **Feature-Driven basada en Clean Architecture**, organizando el código por funcionalidades de negocio y separando estrictamente el dominio, la aplicación y los adaptadores de infraestructura:

```text
backend3/
│
├── app/
│   ├── core/              # Configuración global y seguridad transversal
│   ├── main.py            # Composición e inicialización de FastAPI
│   └── features/
│       └── conversational_agent/
│           ├── domain/         # Modelos, entidades e interfaces puras
│           ├── application/   # Casos de uso y orquestación
│           └── infrastructure/# Adaptadores MCP, Supabase, Gemini y FastAPI
└── scripts/               # Scripts de verificación y utilidades
```

---

## 📋 Funciones Principales

* **Agentic RAG:** Procesa preguntas complejas de los usuarios generando análisis y recomendaciones corporativas basadas en contexto real.
* **Cruce de Datos:** Conecta dinámicamente información de tablas relacionales (ventas, clientes, stock, compras, intervenciones) con vectores de documentos internos.
* **Estándar MCP:** Utiliza el Model Context Protocol para consumir herramientas de base de datos de forma segura y estandarizada.
* **Orquestación Inteligente:** Utiliza LangChain y Google Gemini para el razonamiento autónomo y la selección de herramientas.
* **Seguridad de Endpoints:** Validación de tokens JWT emitidos por Supabase Auth y control de accesos CORS. `POST /api/v1/chat` exige la cabecera `Authorization` con el token; `AUTH_ENABLED=false` la desactiva solo en local.

---

## ⚙️ Configuración y Puesta en Marcha

### 1. Requisitos previos

* **Python 3.12** (recomendado; las dependencias de IA aún no están probadas con versiones más nuevas).
* Cuenta de **Supabase** con el esquema de `.specs/database/schema.sql` aplicado (incluye la tabla `chat_logs`) y una clave de **Google Gemini** (Google AI Studio).
* Docker, solo si vas a usar la opción de contenedor.

### 2. Variables de Entorno

Copia la plantilla y rellénala. El `.env` va en la **raíz del repositorio** (no dentro de `backend3/`) y nunca se sube a git:

```bash
cp .env.example .env        # Windows (PowerShell): Copy-Item .env.example .env
```

Variables imprescindibles:

* `SUPABASE_URL`: URL del proyecto. También se usa para descargar las claves públicas con las que se valida el JWT.
* `SUPABASE_KEY`: clave `secret` (service role) de Supabase, solo en el servidor.
* `GOOGLE_API_KEY`: clave de Gemini.
* `AUTH_ENABLED`: `true` por defecto. Con `false` el chat se puede llamar sin token y `chat_logs.user` queda `NULL` (solo para desarrollo local).
* `CORS_ORIGINS`: orígenes del frontend, separados por comas.
* `SUPABASE_JWT_SECRET`: opcional; solo si aún tienes tokens firmados con la clave antigua HS256. Los tokens actuales (ES256) no lo necesitan.

### 3. Ejecución Manual (Desarrollo)

Ejecuta los comandos desde la carpeta `backend3/`, porque `app.main` vive ahí:

```bash
# Crear y activar el entorno virtual (en la raíz del repositorio)
py -3.12 -m venv venv              # Linux/macOS: python3.12 -m venv venv
venv\Scripts\activate              # Linux/macOS: source venv/bin/activate

# Instalar dependencias
pip install -r requirements_file.txt

# Iniciar el servidor (el servidor MCP se lanza solo como subproceso)
cd backend3
uvicorn app.main:app --reload --port 8000
```

Comprueba que funciona con `http://localhost:8000/health` y abre Swagger UI en `http://localhost:8000/docs`.

Para llamar a `POST /api/v1/chat` con `AUTH_ENABLED=true`, pulsa **Authorize** en Swagger y pega el *access token* de un usuario de Supabase Auth, sin la palabra `Bearer` y sin espacios ni saltos de línea. Sin token responde `401`.

La API expone `GET /health` y `POST /api/v1/chat`. Enviar `{"message": "..."}` inicia una conversación y devuelve un `session_id` UUID; reutilizarlo en la siguiente petición continúa la conversación. El historial se carga desde `chat_logs` y no se envía desde el cliente.

### 4. Tests

```bash
cd backend3
python -m pytest tests/unit
```

Los tests marcados `conversational` usan Gemini, MCP y Supabase reales y quedan excluidos por defecto.

### 5. Ejecución con Docker

```bash
docker build -t wavecore-backend3 .
docker run -d -p 8000:8000 --env-file .env wavecore-backend3
```

Swagger UI queda en `http://localhost:8000/docs`.

### 6. Despliegue en Render

`render.yaml` (raíz) define un servicio web con runtime Docker. Tras conectar el repositorio, rellena en el panel de Render los secretos `SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_API_KEY` y `CORS_ORIGINS`; los modelos de Gemini se pueden cambiar allí sin recompilar. El health check usa `/health`.
