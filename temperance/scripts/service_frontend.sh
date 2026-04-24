#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

FRONTEND_DIR="${FRONTEND_DIR:-${V2_FRONTEND_DIR:-${REPO_DIR}/frontend}}"
NODE_BIN="${NODE_BIN:-}"
NPM_BIN="${NPM_BIN:-}"
PYTHON_BIN="${FRONTEND_PYTHON_BIN:-${REPO_DIR}/.venv/bin/python}"
HOST="${FRONTEND_HOST:-${V2_FRONTEND_HOST:-127.0.0.1}}"
PORT="${FRONTEND_PORT:-${V2_FRONTEND_PORT:-5173}}"
DIST_DIR="${FRONTEND_DIST_DIR:-${FRONTEND_DIR}/dist}"
STATIC_SERVER="${ROOT_DIR}/scripts/serve_frontend_static.py"
BUILD_ON_START="${FRONTEND_BUILD_ON_START:-0}"
USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
CAFFEINATE_BIN="${CAFFEINATE_BIN:-}"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
if [[ -z "${NODE_BIN}" ]]; then
  NODE_BIN="$(command -v node || true)"
fi
NODE_BIN="${NODE_BIN:-/opt/homebrew/bin/node}"
if [[ -z "${NPM_BIN}" ]]; then
  NPM_BIN="$(command -v npm || true)"
fi
if [[ -z "${CAFFEINATE_BIN}" ]]; then
  CAFFEINATE_BIN="$(command -v caffeinate || true)"
fi

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "Missing frontend dir: ${FRONTEND_DIR}" >&2
  exit 1
fi

if [[ ! -x "${NODE_BIN}" ]]; then
  echo "node not found/executable: ${NODE_BIN}" >&2
  exit 1
fi

if [[ ! -x "${NPM_BIN}" ]]; then
  echo "npm not found/executable: ${NPM_BIN}" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "python not found/executable: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -f "${STATIC_SERVER}" ]]; then
  echo "Missing static frontend server: ${STATIC_SERVER}" >&2
  exit 1
fi

cd "${FRONTEND_DIR}"
if [[ "${BUILD_ON_START}" == "1" ]]; then
  "${NPM_BIN}" run build
fi

if [[ ! -f "${DIST_DIR}/index.html" ]]; then
  echo "Missing built frontend entrypoint: ${DIST_DIR}/index.html" >&2
  echo "Run 'cd ${FRONTEND_DIR} && ${NPM_BIN} run build' before starting the public frontend service." >&2
  exit 1
fi

if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
  exec "${CAFFEINATE_BIN}" -dimsu "${PYTHON_BIN}" "${STATIC_SERVER}" --host "${HOST}" --port "${PORT}" --root "${DIST_DIR}"
fi

exec "${PYTHON_BIN}" "${STATIC_SERVER}" --host "${HOST}" --port "${PORT}" --root "${DIST_DIR}"
