# Arquitectura de WaveCore Backend 3

El backend sigue una arquitectura **Feature-Driven / Clean Architecture**. El código de la aplicación vive bajo `app/`; los componentes se agrupan primero por funcionalidad y luego por capa.

```text
wavecore-backend3/
├── .specs/                                      # Especificaciones del proyecto (SDD)
│   └── database/                                # Fuente de verdad del esquema Supabase
├── app/
│   ├── core/                                     # Configuración global y seguridad transversal
│   ├── main.py                                   # Composición e inicialización de FastAPI
│   └── features/
│       └── conversational_agent/
│           ├── domain/                           # Modelos, entidades e interfaces puras
│           ├── application/                      # Casos de uso y orquestación del agente
│           └── infrastructure/                  # Adaptadores concretos
│               ├── api/                          # Rutas y esquemas HTTP de FastAPI
│               ├── mcp/                          # Servidor y herramientas MCP
│               ├── persistence/                  # Cliente Supabase y acceso a datos
│               └── llm/                           # Adaptador de Google Gemini
├── scripts/                                      # Scripts de verificación
├── .env.example                                  # Plantilla de variables de entorno
├── AGENTS.md                                     # Guía y contexto para GitHub Copilot / IA
├── Dockerfile                                    # Imagen Docker multietapa (contexto: raíz)
├── .dockerignore
├── render.yaml                                   # Despliegue en Render (IaC)
└── requirements_file.txt                         # Dependencias de Python
```

## Reglas de dependencias

- `domain/` contiene reglas, modelos e interfaces sin dependencias de FastAPI, Supabase ni otros adaptadores.
- `application/` implementa casos de uso y depende del dominio; no contiene acceso directo a la base de datos ni inicialización de proveedores externos.
- `infrastructure/` implementa puertos y adaptadores para HTTP, MCP, Supabase y Gemini.
- `app/core/` aloja configuración y capacidades transversales; `app/main.py` compone la aplicación.
- Las especificaciones de `.specs/` describen esta misma estructura y no definen una jerarquía paralela como `app/db/`, `app/mcp/` o `app/agent/`.

`.specs/database/` es la fuente de verdad para interactuar con las tablas relacionales y vectoriales de Supabase.
