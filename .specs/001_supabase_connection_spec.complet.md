# Spec 001: Conexión y Pruebas con Supabase

## 0. Ficheros implicados

Rutas relativas a la raíz del repositorio.

### Crear o modificar
- `backend3/app/core/config.py`: configuración y validación de variables de entorno.
- `backend3/app/features/conversational_agent/infrastructure/persistence/supabase.py`: cliente reutilizable de Supabase.
- `backend3/scripts/test_db_connection.py`: pruebas de conexión, consultas relacionales y lectura de embeddings.
- `requirements_file.txt`: dependencias requeridas por la configuración y el cliente de Supabase.
- `.env.example`: nombres de variables necesarias para configurar el entorno; no incluir credenciales reales.

### Referencias
- `.specs/database/schema.sql`: DDL de las tablas.
- `.specs/database/columns_metadata.md`: tipos y nulabilidad de columnas.
- `.specs/database/tables_summary.md`: resumen de tablas y columnas.
- `.specs/database/relationships.md`: relaciones entre tablas.
- `.env`: configuración local; contiene secretos y no debe versionarse.

## 1. Objetivo
Establecer la conexión desde Python con la base de datos de Supabase para verificar que las consultas a tablas relacionales (`ventas`, `clientes`, etc.) y las búsquedas vectoriales en `document_chunks` funcionan correctamente antes de construir la capa MCP.

---

## 2. Requisitos Previos
- Variables de entorno configuradas en `.env` (`SUPABASE_URL`, `SUPABASE_KEY`).
- Base de datos en Supabase con tablas creadas y datos de prueba insertados.
- Archivos de esquema y metadatos alojados en `.specs/database/`.

---

## 3. Entregables y Componentes a Crear

### 3.1. Gestión de Entorno y Cliente
- **`app/core/config.py`**: Carga de variables de entorno mediante `pydantic-settings` (incluyendo credenciales de Supabase y los modelos configurables de Gemini: `GEMINI_AGENT_MODEL` y `GEMINI_FALLBACK_MODEL`).
- **`app/features/conversational_agent/infrastructure/persistence/supabase.py`**: Inicialización del cliente oficial de Supabase para Python, como adaptador de persistencia de la funcionalidad.

### 3.2. Script de Verificación
- **`scripts/test_db_connection.py`**:
  - Consulta relacional a la tabla `clientes` y `ventas`.
  - Prueba de similitud de vectores sobre `document_chunks` usando la función RPC o cliente directo.

---

## 4. Estructura de Archivos a Crear / Modificar
```text
backend3/
├── app/
│   ├── core/
│   │   └── config.py
│   └── features/
│       └── conversational_agent/
│           └── infrastructure/
│               └── persistence/
│                   └── supabase.py
└── scripts/
    └── test_db_connection.py
```

---

## 5. Plan de Implementación Técnico 

### Paso 1: Configuración de Variables (`app/core/config.py`)
Definir una clase Settings para validar la presencia de las credenciales obligatorias (`SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_API_KEY`) y definir los modelos de IA configurables por entorno (`GEMINI_AGENT_MODEL` y `GEMINI_FALLBACK_MODEL`) con sus valores por defecto.

### Paso 2: Cliente Supabase (`app/features/conversational_agent/infrastructure/persistence/supabase.py`)
Instanciar el cliente `supabase.Client` reutilizable para el resto del proyecto.

### Paso 3: Script de Pruebas (`scripts/test_db_connection.py`)
Implementar consultas simples:
1. Extraer los primeros 5 registros de la tabla `clientes`.
2. Realizar una consulta a `ventas` cruzando con `productos`.
3. Ejecutar una prueba de consulta vectorial o consulta simple a `document_chunks`.

---

## 6. Criterios de Aceptación y Verificación
- El script `python scripts/test_db_connection.py` se ejecuta sin errores de autenticación o conexión.
- Imprime por consola los registros obtenidos de la base de datos de forma legible.
- Confirmación de lectura de embeddings/vectores en `document_chunks`.