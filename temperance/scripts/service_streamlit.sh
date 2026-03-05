#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
APP_FILE="${ROOT_DIR}/app.py"
LOG_DIR="${ROOT_DIR}/data/private/logs"

PORT="${PORT:-8504}"
ADDRESS="${ADDRESS:-0.0.0.0}"

mkdir -p "${LOG_DIR}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python binary: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -f "${APP_FILE}" ]]; then
  echo "Missing app.py: ${APP_FILE}" >&2
  exit 1
fi

exec "${PYTHON_BIN}" -m streamlit run "${APP_FILE}" \
  --server.address "${ADDRESS}" \
  --server.port "${PORT}" \
  --server.headless true \
  --server.fileWatcherType none
