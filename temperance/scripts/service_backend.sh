#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

PYTHON_BIN="${BACKEND_PYTHON_BIN:-${V2_PYTHON_BIN:-${REPO_DIR}/backend/.venv/bin/python}}"
BACKEND_DIR="${BACKEND_DIR:-${V2_BACKEND_DIR:-${REPO_DIR}/backend}}"
PORT="${BACKEND_PORT:-${V2_BACKEND_PORT:-8000}}"
HOST="${BACKEND_HOST:-${V2_BACKEND_HOST:-127.0.0.1}}"
USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
CAFFEINATE_BIN="${CAFFEINATE_BIN:-}"

# Temporarily force embedded Garmin auto-sync off for backend restarts.
export TEMPERANCE_AUTO_SYNC_ENABLED=0

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python binary: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "Missing backend dir: ${BACKEND_DIR}" >&2
  exit 1
fi

if [[ -z "${CAFFEINATE_BIN}" ]]; then
  CAFFEINATE_BIN="$(command -v caffeinate || true)"
fi

cd "${REPO_DIR}"
if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
  exec "${CAFFEINATE_BIN}" -dimsu "${PYTHON_BIN}" -m uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}"
fi

exec "${PYTHON_BIN}" -m uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}"
