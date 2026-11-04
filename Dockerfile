FROM alpine:3.23 AS app-build

RUN apk upgrade --no-cache \
    && apk add --no-cache python3 libffi openssl sqlite-libs \
    && apk add --no-cache --virtual .build-deps py3-pip py3-setuptools

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/

RUN python3 -m pip install --break-system-packages --no-cache-dir . \
    && apk del .build-deps \
    && find /usr /root /tmp /opt -iname '*setuptools*' -exec rm -rf {} + \
    && rm -rf /root/.cache /tmp/pip-* /tmp/build* \
    && find /usr /root /tmp /opt -type f -name '*.whl' -delete \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && addgroup -S app \
    && adduser -S -D -G app -h /app -s /sbin/nologin app \
    && chown -R app:app /app

FROM scratch
COPY --from=app-build / /
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
