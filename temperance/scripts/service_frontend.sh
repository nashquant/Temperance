#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

FRONTEND_DIR="${FRONTEND_DIR:-${V2_FRONTEND_DIR:-${REPO_DIR}/frontend}}"
NODE_BIN="${NODE_BIN:-}"
HOST="${FRONTEND_HOST:-${V2_FRONTEND_HOST:-127.0.0.1}}"
PORT="${FRONTEND_PORT:-${V2_FRONTEND_PORT:-5173}}"
USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
CAFFEINATE_BIN="${CAFFEINATE_BIN:-}"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
if [[ -z "${NODE_BIN}" ]]; then
  NODE_BIN="$(command -v node || true)"
fi
NODE_BIN="${NODE_BIN:-/opt/homebrew/bin/node}"
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

VITE_BIN="${FRONTEND_DIR}/node_modules/vite/bin/vite.js"
if [[ ! -f "${VITE_BIN}" ]]; then
  echo "Missing vite binary: ${VITE_BIN}" >&2
  exit 1
fi

cd "${FRONTEND_DIR}"
if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
  exec "${CAFFEINATE_BIN}" -dimsu "${NODE_BIN}" "${VITE_BIN}" --host "${HOST}" --port "${PORT}"
fi

exec "${NODE_BIN}" "${VITE_BIN}" --host "${HOST}" --port "${PORT}"
