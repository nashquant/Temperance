#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

exec python -m uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --reload
