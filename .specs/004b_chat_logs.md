# Spec 004b: Auditoría y Registro de Conversaciones (chat_logs)

## 1. Objetivo
Implementar el registro automático de cada interacción de chat en la tabla relacional `chat_logs` de Supabase, capturando métricas de uso de modelos, conteo de tokens, metadatos de red y asociando obligatoriamente el identificador de API `"3 agent av"`.

## 2. Requisitos Previos
* `004-fastapi-api.md` (o `004_fastapi_api_spec_2.md`) completado y operativo.
* Tabla `chat_logs` creada y validada en Supabase (según `.specs/database/schema.sql`).

## 3. Entregables y Componentes a Crear / Modificar
* **`app/features/conversational_agent/application/services/chat_logger.py`**: Servicio de aplicación para gestionar la inserción del log.
* **`app/features/conversational_agent/infrastructure/persistence/chat_logs.py`**: Adaptador que inserta y recupera registros en Supabase.
* El caso de uso del agente registra cada interacción; el endpoint entrega la IP al agente y no duplica el logging.

## 4. Estructura de Datos a Registrar (`chat_logs`)
Por cada petición y respuesta procesada por el agente, se insertará un registro con los siguientes campos:
- `api`: `"3 agent av"` *(Valor fijo obligatorio)*.
- `model_used`: Nombre del modelo Gemini utilizado (ej. `gemini-2.5-flash`).
- `prompt`: Texto de la pregunta del usuario.
- `reply`: Texto de la respuesta generada por el agente.
- `prompt_tokens`: Conteo de tokens de entrada (si el LLM los provee).
- `response_tokens`: Conteo de tokens de salida.
- `total_tokens`: Suma de tokens consumidos.
- `client_ip`: Dirección IP del cliente extraída de la petición HTTP.
- `conversation_id`: Identificador único de la sesión de chat (UUID).
- `created_at`: Fecha y hora asignadas por la base de datos.
- `id`: Identificador secuencial usado para ordenar turnos con la misma marca temporal.
- `user`: Columna nullable preparada para la identidad autenticada de la spec 005b; en 004b se guarda el valor anónimo configurado por defecto.

La definición SQL está en `.specs/database/schema.sql`. Aplicar y verificar la tabla e índice en Supabase antes de probar el logging real.

## 5. Criterios de Aceptación y Verificación
* Cada llamada exitosa a `/api/v1/chat` genera un registro en la tabla `chat_logs` de Supabase.
* El campo `api` contiene exactamente la cadena `"3 agent av"`.
* Si ocurren errores durante el guardado del log, la respuesta al usuario no se ve afectada (manejo de excepciones no bloqueante).
* Las pruebas unitarias verifican que el adaptador envía a Supabase el payload de auditoría esperado.