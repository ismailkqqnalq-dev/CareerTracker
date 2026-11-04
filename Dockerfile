FROM python:3.11.18-alpine3.23
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/

RUN apk upgrade --no-cache \
    && python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir . \
    && addgroup -S app \
    && adduser -S -D -G app -h /app -s /sbin/nologin app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
