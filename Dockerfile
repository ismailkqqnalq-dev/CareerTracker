FROM python:3.12.16-alpine3.23 AS app-build
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
    && python -m pip uninstall --yes setuptools \
    && if apk info -e py3-setuptools >/dev/null 2>&1; then apk del py3-setuptools; fi \
    && find /usr /root /tmp /opt -iname '*setuptools*' -exec rm -rf {} + \
    && rm -rf /root/.cache /tmp/pip-* /tmp/build* \
    && find /usr /root /tmp /opt -type f -name '*.whl' -delete \
    && test -z "$(find /usr /root /tmp /opt -iname '*setuptools*' -o -type f -name '*.whl' -print -quit)" \
    && addgroup -S app \
    && adduser -S -D -G app -h /app -s /sbin/nologin app \
    && chown -R app:app /app

RUN echo "Remaining setuptools package records:" \
    && (apk info | grep -i setuptools || true) \
    && (find / -iname '*setuptools*' -print 2>/dev/null || true)

# Copy the cleaned merged filesystem into a fresh image so vulnerable packages
# from the Python base image's lower layers are not retained in the runtime.
FROM scratch
COPY --from=app-build / /
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
