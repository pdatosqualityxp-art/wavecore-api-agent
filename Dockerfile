FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements_file.txt .
RUN pip install -r requirements_file.txt


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 1000 appuser
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY backend3/ .
USER appuser

EXPOSE 8000

# El servidor MCP se lanza como subproceso con el mismo intérprete (sys.executable).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
