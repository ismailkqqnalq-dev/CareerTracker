FROM python:3.11.18-slim-trixie
WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && if dpkg-query -W -f='${Status}' python3-setuptools 2>/dev/null | grep -q 'install ok installed'; then apt-get purge -y python3-setuptools; fi \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir . \
    && find /usr/lib /usr/local/lib -path '*/ensurepip/_bundled/setuptools-*.whl' -delete \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
