# ── Stage 1 : Builder ──────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --user --no-cache-dir uv \
 && python -m uv pip install --system --no-cache-dir .

# ── Stage 2 : Runtime ──────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# User non-root (sécurité)
RUN useradd -m -u 1000 appuser \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Paris

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# main.py utilise BlockingScheduler (pas FastAPI) — exécution directe
CMD ["python", "-m", "apps.jmpartners.main"]
