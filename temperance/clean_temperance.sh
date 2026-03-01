#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/data/private/logs"
PID_FILE="${LOG_DIR}/streamlit_remote.pid"

PORT="${PORT:-8501}"
START_AFTER_CLEAN="${START_AFTER_CLEAN:-1}"

echo "[temperance] Cleaning existing processes..."

# Kill by saved PID first (if present).
if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}" || true)"
  if [[ -n "${pid}" ]]; then
    kill "${pid}" >/dev/null 2>&1 || true
    kill -9 "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${PID_FILE}"
fi

# Kill any lingering Streamlit process for this app.
pkill -f "streamlit run .*app.py" >/dev/null 2>&1 || true
sleep 1
pkill -9 -f "streamlit run .*app.py" >/dev/null 2>&1 || true

# If something still holds target port, kill it.
port_pid="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "${port_pid}" ]]; then
  kill "${port_pid}" >/dev/null 2>&1 || true
  sleep 1
  kill -9 "${port_pid}" >/dev/null 2>&1 || true
fi

echo "[temperance] Clean stop complete."

if [[ "${START_AFTER_CLEAN}" == "1" ]]; then
  echo "[temperance] Starting fresh instance..."
  (cd "${ROOT_DIR}" && PORT="${PORT}" ./run_remote.sh start)
  echo "[temperance] Done."
else
  echo "[temperance] START_AFTER_CLEAN=0, not starting app."
fi

