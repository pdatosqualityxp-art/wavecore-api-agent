# Spec 005b: Identificación de Usuario en chat_logs

## 1. Objetivo

Extender el mecanismo de auditoría en la tabla `chat_logs` de Supabase para registrar la identidad del usuario autenticado que realiza la consulta, añadiendo la columna `user` en la base de datos e integrando la extracción del usuario a partir del token JWT validado en la Spec 005.

---

## 2. Requisitos Previos

* `004b_chat_logs_spec.md` completado y verificado (mecanismo base de logging funcionando).
* `005_security_docker_and_deployment_spec.md` completado y verificado (dependencia `get_current_user` lista en `app/core/security.py`).
* Acceso con permisos de administración a la consola SQL o migraciones de Supabase.

---

## 3. Modificación del Esquema de Base de Datos (DDL SQL)

Antes de realizar cambios en el código Python, es obligatorio ejecutar la siguiente instrucción DDL en el editor SQL de Supabase para crear la columna `user` en la tabla `chat_logs`:

```sql
-- Añadir la columna 'user' a la tabla chat_logs para almacenar el email o UUID del usuario autenticado
ALTER TABLE chat_logs 
ADD COLUMN IF NOT EXISTS "user" VARCHAR(100) DEFAULT NULL;

-- Comentario explicativo en el esquema de la base de datos
COMMENT ON COLUMN chat_logs."user" IS 'Identificador o email del usuario autenticado extraído del token JWT';
```

---

## 4. Entregables y Componentes a Modificar

### 4.1. Servicio de Auditoría
* **`app/features/conversational_agent/application/services/chat_logger.py`**:
  - Actualizar la firma de la función/método de registro para aceptar el parámetro opcional u obligatorio `user: Optional[str]`.
  - Incluir el campo `"user"` en el payload que se envía a la tabla `chat_logs` de Supabase.

### 4.2. Adaptador API (FastAPI)
* **`app/features/conversational_agent/infrastructure/api/v1/endpoints/chat.py`**:
  - Inyectar el usuario actual mediante la dependencia de seguridad `current_user = Depends(get_current_user)`.
  - Pasar el identificador/email del `current_user` al servicio `chat_logger`.

---

## 5. Estructura de Archivos Involucrados

```text
backend3/
└── app/
    ├── core/
    │   └── security.py           # Inyecta get_current_user
    └── features/
        └── conversational_agent/
            ├── application/
            │   └── services/
            │       └── chat_logger.py  # Modificado para recibir 'user'
            └── infrastructure/
                └── api/
                    └── v1/
                        └── endpoints/
                            └── chat.py  # Inyecta dependencia y delega al logger
```

---

## 6. Plan de Implementación Técnico

### Paso 1: Ejecución SQL en Supabase
Ejecutar la sentencia `ALTER TABLE` descrita en la sección 3.

### Paso 2: Actualización del Servicio `chat_logger.py`
Mapear el campo `user` en la carga útil de la consulta a Supabase:
```python
payload = {
    "api": "3 agent av",
    "user": user_identifier,  # ej. current_user.email o current_user.id
    "model_used": model_used,
    "prompt": prompt,
    "reply": reply,
    "prompt_tokens": prompt_tokens,
    "response_tokens": response_tokens,
    "total_tokens": total_tokens,
    "client_ip": client_ip,
    "conversation_id": conversation_id,
}
```

### Paso 3: Integración en el Endpoint HTTP (`chat.py`)
Extraer el usuario del token autenticado y enviarlo al registrador:
```python
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    ...
```

---

## 7. Criterios de Aceptación y Verificación

* La columna `user` existe en la tabla `chat_logs` de Supabase sin alterar los registros existentes.
* Al enviar una petición POST a `/api/v1/chat` con un token Bearer válido, el campo `user` en `chat_logs` se puebla con la identidad correspondiente (email o UUID).
* Si por configuración o pruebas locales el token no está presente, el campo `user` acepta valores nulos (`NULL`) sin interrumpir la persistencia del log.