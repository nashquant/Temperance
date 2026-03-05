#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STREAMLIT_BIN="${ROOT_DIR}/.venv/bin/streamlit"
APP_FILE="${ROOT_DIR}/app.py"
LOG_DIR="${ROOT_DIR}/data/private/logs"

PORT="${PORT:-8504}"
ADDRESS="${ADDRESS:-0.0.0.0}"

mkdir -p "${LOG_DIR}"

if [[ ! -x "${STREAMLIT_BIN}" ]]; then
  echo "Missing streamlit binary: ${STREAMLIT_BIN}" >&2
  exit 1
fi

if [[ ! -f "${APP_FILE}" ]]; then
  echo "Missing app.py: ${APP_FILE}" >&2
  exit 1
fi

exec "${STREAMLIT_BIN}" run "${APP_FILE}" \
  --server.address "${ADDRESS}" \
  --server.port "${PORT}" \
  --server.headless true \
  --server.fileWatcherType none

