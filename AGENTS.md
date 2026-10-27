# AGENTS.md - Contexto para GitHub Copilot (WaveCore Backend 3)

## 🎯 Propósito del Proyecto
Estás desarrollando el **Backend 3** de **WaveCore Manager**. Es un microservicio en **Python (FastAPI)** que implementa un **Agentic RAG** utilizando **LangChain**, **Google Gemini** y el **Model Context Protocol (MCP)** para realizar consultas cruzadas avanzadas entre las tablas relacionales de **Supabase** y los fragmentos vectoriales (*chunks*) de documentos corporativos.

## 🛠️ Stack Tecnológico Ofertado
- **Python 3.10+** con **FastAPI** y **Uvicorn**.
- **LangChain** para orquestación de agentes y cadenas de razonamiento.
- **Google Gemini API** (`langchain-google-genai`) como LLM principal.
- **MCP Python SDK** (`mcp`) para la capa de herramientas estandarizadas.
- **Supabase** (PostgreSQL + pgvector).

## 🏛️ Directrices de Arquitectura (Feature-Driven / Clean Architecture)
El proyecto debe estructurarse estrictamente siguiendo una arquitectura **Feature-Driven basada en Clean Architecture**:

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
│           └── infrastructure/# Adaptadores concretos
└── scripts/               # Scripts de verificación y utilidades
```

### Reglas de Arquitectura para el Código:
1. **Dominio (`domain/`)**: Contiene únicamente modelos Pydantic, entidades e interfaces puras. No debe importar librerías externas de infraestructura (sin `fastapi`, sin `asyncpg`, sin `supabase`).
2. **Aplicación (`application/`)**: Contiene la lógica de los casos de uso y la orquestación del agente con LangChain. Utiliza los modelos del dominio y llama a las herramientas expuestas por la infraestructura.
3. **Infraestructura (`infrastructure/`)**: Contiene las implementaciones concretas: endpoints de FastAPI, cliente oficial de Supabase/PostgreSQL, servidor MCP y adaptadores de Gemini.
4. **Desacoplamiento:** No acoples las llamadas directas a la base de datos ni la lógica de Gemini dentro de los endpoints de FastAPI. Usa adaptadores y servicios intermedios.

## 🗄️ Esquema de Base de Datos y Metadatos
La estructura y metadatos completos de la base de datos de Supabase se encuentran en `.specs/database/`:
- **DDL SQL:** `schema.sql`
- **Metadatos de Columnas:** `columns_metadata.md`
- **Resumen de Tablas y Constraints:** `tables_summary.md`
- **Relaciones (Foreign Keys):** `relationships.md`

## 🔒 Estado Actual de Seguridad
- **Fase actual:** Spec 005 implementada. `POST /api/v1/chat` valida el JWT de Supabase (ES256 vía JWKS; HS256 opcional con `SUPABASE_JWT_SECRET`) y registra el usuario en `chat_logs`.
- **Nota:** `AUTH_ENABLED=false` desactiva la validación solo para desarrollo local. CORS se configura con `CORS_ORIGINS`.