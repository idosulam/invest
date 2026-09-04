FROM node:20-slim AS frontend

WORKDIR /build

# Build Next.js frontend
COPY apps/web/package.json apps/web/package-lock.json* apps/web/
RUN cd apps/web && npm install --prefer-offline
COPY apps/web/ apps/web/
RUN cd apps/web && npm run build


FROM python:3.11-slim

WORKDIR /app

# System deps for PostgreSQL client, build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Python deps — install from lockfile for reproducible builds
COPY pyproject.toml uv.lock .
RUN uv pip install --system --no-cache .

COPY . .

# Copy built frontend from builder stage
COPY --from=frontend /build/apps/web/out apps/web/out

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
