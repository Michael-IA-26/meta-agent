FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install uv --no-cache-dir

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY apps/ ./apps/
COPY packages/ ./packages/

RUN mkdir -p logs && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3.11 -c "from apps.jmpartners.orchestrator import run; print('OK')" || exit 1

CMD ["uv", "run", "python3.11", "-m", "apps.jmpartners.main"]
