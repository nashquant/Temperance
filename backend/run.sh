#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
PYTHON_BIN="${BACKEND_PYTHON_BIN:-${V2_PYTHON_BIN:-}}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
  elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

exec "${PYTHON_BIN}" -m uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --reload
