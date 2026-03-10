#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

PYTHON_BIN="${V2_PYTHON_BIN:-${REPO_DIR}/v2/backend/.venv/bin/python}"
V2_BACKEND_DIR="${V2_BACKEND_DIR:-${REPO_DIR}/v2/backend}"
PORT="${V2_BACKEND_PORT:-8000}"
HOST="${V2_BACKEND_HOST:-127.0.0.1}"
USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
CAFFEINATE_BIN="${CAFFEINATE_BIN:-}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python binary: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -d "${V2_BACKEND_DIR}" ]]; then
  echo "Missing v2 backend dir: ${V2_BACKEND_DIR}" >&2
  exit 1
fi

if [[ -z "${CAFFEINATE_BIN}" ]]; then
  CAFFEINATE_BIN="$(command -v caffeinate || true)"
fi

cd "${V2_BACKEND_DIR}"
if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
  exec "${CAFFEINATE_BIN}" -dimsu "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
fi

exec "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
