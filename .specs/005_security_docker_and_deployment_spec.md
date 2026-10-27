# Spec 005: Seguridad JWT, Dockerización y Despliegue en Render

## 1. Objetivo

Implementar la capa de seguridad mediante la validación de tokens JWT emitidos por Supabase en los endpoints de FastAPI, empaquetar la aplicación en un contenedor Docker optimizado para producción y configurar la infraestructura necesaria para su despliegue automatizado en la plataforma Render.

## 2. Requisitos Previos

* `004-fastapi-api.md` completado y verificado.

* Endpoints de FastAPI operativos y accesibles localmente.

* Cuenta activa en Render y Docker instalado localmente para pruebas de contenedorización.

## 3. Entregables y Componentes a Crear

### 3.1. Seguridad y Autenticación JWT

* **`app/core/security.py`**: Middleware/Dependencia de FastAPI para verificar y decodificar el token JWT de Supabase presente en el encabezado `Authorization: Bearer <token>`.

### 3.2. Contenedorización con Docker

* **`Dockerfile`**: Definición multietapa de la imagen Docker para Python/FastAPI.

* **`.dockerignore`**: Exclusión de archivos locales innecesarios (`.env`, `venv/`, `.git`, etc.).

### 3.3. Configuración de Despliegue

* **`render.yaml`**: Archivo de especificación de infraestructura como código (IaC) para Render, que incluye el mapeo de variables de entorno críticas y de modelos (`SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_API_KEY`, `CORS_ORIGINS`, `GEMINI_AGENT_MODEL`, `GEMINI_FALLBACK_MODEL`; los secretos con `sync: false`, a rellenar en el panel de Render).
* **`.env.example`**: Plantilla de entorno actualizada que incluye por defecto las variables de configuración de los modelos de Gemini.

## 4. Estructura de Archivos

Los ficheros de contenedorización y despliegue viven en la **raíz del repositorio** (junto a `requirements_file.txt` y `.env`); el contexto de build es la raíz y la imagen copia `backend3/` a `/app`.

```
/
├── Dockerfile
├── .dockerignore
├── render.yaml
├── requirements_file.txt
└── backend3/
    └── app/
        ├── core/
        │   └── security.py
        └── features/
            └── conversational_agent/
                └── infrastructure/
                    └── api/
```

## 5. Plan de Implementación Técnico

### Paso 1: Dependencia de Seguridad JWT (`app/core/security.py`)

* Implementar función `get_current_user` usando `PyJWT` para validar la firma y vigencia del JWT según el algoritmo de la cabecera: ES256/RS256 (claves de firma asimétricas, por defecto en Supabase) con la clave pública del JWKS `SUPABASE_URL/auth/v1/.well-known/jwks.json`; HS256 (clave antigua) con `SUPABASE_JWT_SECRET`, opcional. Audiencia `authenticated`. La dependencia devuelve un `CurrentUser` (`id`, `email`). `/health` y `/docs` siguen siendo públicos. Para desarrollo local, `AUTH_ENABLED=false` desactiva la validación (el usuario queda `NULL` en `chat_logs`); por defecto está activada.

* Proteger la ruta `/api/v1/chat` en su adaptador FastAPI inyectando la dependencia `Depends(get_current_user)`.

### Paso 2: Construcción del Dockerfile (`Dockerfile`)

* Utilizar una imagen base ligera (`python:3.12-slim`).

* Copiar `requirements_file.txt` (o `pyproject.toml` si se migra a ese formato), instalar dependencias y exponer el puerto `8000`.

* Configurar el comando de inicio de producción con `uvicorn app.main:app --host 0.0.0.0 --port 8000` (la aplicación se compone en `app/main.py`).

### Paso 3: Configuración de Render (`render.yaml`)

* Definir un servicio de tipo `web`, runtime `docker`.
* Mapear las variables de entorno necesarias en la especificación de despliegue (`SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_API_KEY`, `CORS_ORIGINS`, `GEMINI_AGENT_MODEL`, `GEMINI_FALLBACK_MODEL`; los secretos con `sync: false`, a rellenar en el panel de Render), permitiendo modificar los modelos de Gemini directamente desde el panel de Render tras el despliegue sin necesidad de recompilar el código.

## 6. Criterios de Aceptación y Verificación

* **Seguridad:** Peticiones HTTP POST a `/api/v1/chat` sin token válido retornan `401 Unauthorized`. Peticiones con token válido de Supabase son procesadas correctamente.

* **Docker:** La imagen `docker build -t wavecore-backend .` se construye sin fallos y el contenedor se ejecuta localmente devolviendo la API funcional.

* **Despliegue:** El servicio despliega con éxito en Render sin errores en los logs de arranque y responde a través de su dominio público HTTPS.