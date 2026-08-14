FROM python:3.13-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system acmetrics \
    && useradd --system --gid acmetrics --create-home acmetrics

WORKDIR /app
COPY pyproject.toml README.md ./
COPY server ./server
COPY alembic.ini ./
RUN pip install --no-cache-dir .

FROM base AS test
RUN pip install --no-cache-dir ".[test]"
USER acmetrics
CMD ["pytest"]

FROM base AS production
USER acmetrics
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read()"]

CMD ["uvicorn", "app.main:app", "--app-dir", "server", "--host", "0.0.0.0", "--port", "8080"]
