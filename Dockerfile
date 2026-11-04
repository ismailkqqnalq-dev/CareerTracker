FROM python:3.11.18-slim-trixie
WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
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
    && python -c 'import ensurepip, pathlib; [p.unlink() for p in pathlib.Path(ensurepip.__path__[0], "_bundled").glob("setuptools-*.whl")]' \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
