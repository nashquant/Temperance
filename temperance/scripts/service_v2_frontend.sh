#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

V2_FRONTEND_DIR="${V2_FRONTEND_DIR:-${REPO_DIR}/v2/frontend}"
NPM_BIN="${NPM_BIN:-npm}"
HOST="${V2_FRONTEND_HOST:-127.0.0.1}"
PORT="${V2_FRONTEND_PORT:-5173}"

if ! command -v "${NPM_BIN}" >/dev/null 2>&1; then
  echo "npm not found: ${NPM_BIN}" >&2
  exit 1
fi

if [[ ! -d "${V2_FRONTEND_DIR}" ]]; then
  echo "Missing v2 frontend dir: ${V2_FRONTEND_DIR}" >&2
  exit 1
fi

cd "${V2_FRONTEND_DIR}"
exec "${NPM_BIN}" run dev -- --host "${HOST}" --port "${PORT}"
