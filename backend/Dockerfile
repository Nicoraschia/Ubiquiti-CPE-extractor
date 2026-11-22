FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

# El venv vive fuera de /app para que un bind-mount del codigo no lo tape.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias primero: cambiar el codigo no reinstala paramiko/psycopg.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY tests ./tests
RUN uv sync --frozen

# Sin root: el codigo y el venv quedan de root, solo lectura para el proceso.
RUN useradd --system --uid 10001 --no-create-home app
USER app

ENTRYPOINT ["cpe-scanner"]
