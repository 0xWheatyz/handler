# syntax=docker/dockerfile:1

# ---- ui stage: build the dashboard's static export ----
# The export is a generated artifact (gitignored), so the image builds it here rather
# than trusting the checkout to carry it. package*.json is copied alone first so the
# npm ci layer caches until the lockfile actually changes.
FROM node:20-slim AS ui

WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
RUN npm run build

# ---- build stage: install the package + deps into an isolated venv ----
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
# Drop the built UI into the packaged tree before pip install: hatchling ships every
# non-.py file under src/handler, so the wheel carries the export and FastAPI serves it
# same-origin — exactly what committing src/handler/api/static used to provide.
COPY --from=ui /ui/out ./src/handler/api/static
RUN pip install .

# ---- runtime stage ----
FROM python:3.11-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # SQLite fallback lives on the /var/lib/handler volume; point DATABASE_URL at
    # Postgres for real deploys (see .env.example / docker-compose.yml).
    DATABASE_URL="sqlite:////var/lib/handler/handler.db" \
    PROJECTS_ROOT="/var/lib/handler/projects"

COPY --from=builder /opt/venv /opt/venv

# Alembic runs from /app: alembic.ini resolves script_location=src/handler/migrations
# relative to the cwd, so the migration tree is shipped alongside the installed package.
WORKDIR /app
COPY alembic.ini ./
COPY src/handler/migrations ./src/handler/migrations
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN useradd --system --home-dir /var/lib/handler --create-home handler \
    && mkdir -p /var/lib/handler/projects \
    && chown -R handler:handler /var/lib/handler \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

USER handler
VOLUME /var/lib/handler
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "handler.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
