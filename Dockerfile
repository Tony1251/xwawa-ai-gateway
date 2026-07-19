# ===== Build stage =====
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application source first (needed for editable install)
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY pyproject.toml ./

# Install Python deps
RUN pip install --no-cache-dir -e ".[dev]"

# ===== Production stage =====
FROM python:3.11-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --create-home --shell /bin/bash --gid 1000 --uid 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY pyproject.toml ./
COPY Caddyfile ./
COPY prometheus.yml ./
COPY scripts/ ./scripts/

# Create required directories
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

USER appuser

EXPOSE 8800

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8800/health || exit 1

ENV PYTHONPATH=/app
ENV APP_ENV=production

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8800", "--workers", "4"]
