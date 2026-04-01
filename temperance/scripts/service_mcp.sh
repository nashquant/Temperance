#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

PYTHON_BIN="${BACKEND_PYTHON_BIN:-${V2_PYTHON_BIN:-${REPO_DIR}/backend/.venv/bin/python}}"
USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
CAFFEINATE_BIN="${CAFFEINATE_BIN:-}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python binary: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ -z "${CAFFEINATE_BIN}" ]]; then
  CAFFEINATE_BIN="$(command -v caffeinate || true)"
fi

cd "${REPO_DIR}"
if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
  exec "${CAFFEINATE_BIN}" -dimsu "${PYTHON_BIN}" -m backend.app.mcp_server
fi

exec "${PYTHON_BIN}" -m backend.app.mcp_server
