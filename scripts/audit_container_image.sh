#!/usr/bin/env bash
set -euo pipefail

IMAGE_REF="${1:?Usage: audit_container_image.sh IMAGE_REF [SENTINEL]}"
SENTINEL="${2:-}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

if [[ "${PULL_IMAGE:-0}" == "1" ]]; then
  docker pull "$IMAGE_REF"
fi

uid="$(docker run --rm --network none --entrypoint sh "$IMAGE_REF" -c 'id -u')"
if [[ "$uid" == "0" ]]; then
  echo "Image runs as root."
  exit 1
fi

docker run --rm --network none --user 0 --entrypoint sh "$IMAGE_REF" -c \
  'find / -xdev \( -name ".env" -o -name "*.db" -o -name "*.bak*" -o -name "*.sqlite*" \) -not -path "/proc/*" -print' \
  > "$TEMP_DIR/unwanted-files.txt"
if [[ -s "$TEMP_DIR/unwanted-files.txt" ]]; then
  echo "Image contains a prohibited environment, database, or backup file."
  exit 1
fi

set +e
timeout --kill-after=2s 15s docker run --rm --network none \
  -e PYTHON_DOTENV_DISABLED=1 -e APP_ENV=production \
  --entrypoint sh "$IMAGE_REF" -c \
  'unset JWT_SECRET_KEY; exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' \
  > "$TEMP_DIR/startup.log" 2>&1
startup_status=$?
set -e

if [[ "$startup_status" == "0" || "$startup_status" == "124" || "$startup_status" == "137" || "$startup_status" == "143" ]]; then
  echo "Image did not fail promptly when JWT_SECRET_KEY was absent."
  exit 1
fi
if ! grep -Fq 'JWT_SECRET_KEY must be a non-placeholder value of at least 32 bytes.' "$TEMP_DIR/startup.log"; then
  echo "Image failed without JWT_SECRET_KEY but did not report the expected configuration error."
  exit 1
fi

docker history --no-trunc "$IMAGE_REF" > "$TEMP_DIR/history.txt"
if grep -Eiq '(JWT_SECRET_KEY|POSTGRES_PASSWORD)[[:space:]]*=[[:space:]]*[^[:space:]]{8,}|(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}' "$TEMP_DIR/history.txt"; then
  echo "Image history appears to contain a credential; refusing to print the matching line."
  exit 1
fi
if [[ -n "$SENTINEL" ]] && grep -Fq "$SENTINEL" "$TEMP_DIR/history.txt"; then
  echo "Synthetic secret sentinel was found in image history."
  exit 1
fi

echo "PASS: non-root user, no prohibited data files, explicit missing-JWT startup failure, clean image history."
