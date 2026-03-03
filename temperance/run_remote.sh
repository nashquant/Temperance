#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STREAMLIT_BIN="${ROOT_DIR}/.venv/bin/streamlit"
APP_FILE="${ROOT_DIR}/app.py"
LOG_DIR="${ROOT_DIR}/data/private/logs"
PID_FILE="${LOG_DIR}/streamlit_remote.pid"
LOG_FILE="${LOG_DIR}/streamlit_remote.log"

ADDRESS="${ADDRESS:-0.0.0.0}"
PORT="${PORT:-8501}"

mkdir -p "${LOG_DIR}"

usage() {
  cat <<EOF
Usage: $(basename "$0") {start|stop|restart|status|logs}

Environment overrides:
  ADDRESS   Streamlit bind address (default: 0.0.0.0)
  PORT      Streamlit port (default: 8501)
EOF
}

is_running() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

print_urls() {
  echo "Local:      http://127.0.0.1:${PORT}"
}

start() {
  if [[ ! -x "${STREAMLIT_BIN}" ]]; then
    echo "Missing ${STREAMLIT_BIN}. Create venv and install requirements first."
    exit 1
  fi
  if [[ ! -f "${APP_FILE}" ]]; then
    echo "Missing app file: ${APP_FILE}"
    exit 1
  fi
  if is_running; then
    echo "Temperance is already running (pid $(cat "${PID_FILE}"))."
    print_urls
    exit 0
  fi

  echo "Starting Temperance..."
  nohup "${STREAMLIT_BIN}" run "${APP_FILE}" \
    --server.address "${ADDRESS}" \
    --server.port "${PORT}" \
    --server.headless true >>"${LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" >"${PID_FILE}"

  # Wait until HTTP is actually reachable.
  local ready=0
  for _ in {1..20}; do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      break
    fi
    if curl -sSf -o /dev/null "http://127.0.0.1:${PORT}/"; then
      ready=1
      break
    fi
    sleep 0.5
  done

  if [[ "${ready}" -eq 1 ]]; then
    echo "Started (pid ${pid})."
    echo "Log: ${LOG_FILE}"
    print_urls
  else
    echo "Failed to start. Recent logs:"
    tail -n 40 "${LOG_FILE}" || true
    kill "${pid}" >/dev/null 2>&1 || true
    rm -f "${PID_FILE}"
    exit 1
  fi
}

stop() {
  if ! is_running; then
    echo "Temperance is not running."
    rm -f "${PID_FILE}"
    return 0
  fi
  local pid
  pid="$(cat "${PID_FILE}")"
  echo "Stopping pid ${pid}..."
  kill "${pid}" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "${pid}" >/dev/null 2>&1; then
    echo "Process still running, sending SIGKILL..."
    kill -9 "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${PID_FILE}"
  echo "Stopped."
}

status() {
  if is_running; then
    echo "Temperance is running (pid $(cat "${PID_FILE}"))."
    echo "Log: ${LOG_FILE}"
    print_urls
  else
    echo "Temperance is not running."
  fi
}

logs() {
  echo "Tailing ${LOG_FILE} (Ctrl+C to exit)..."
  touch "${LOG_FILE}"
  tail -f "${LOG_FILE}"
}

cmd="${1:-}"
case "${cmd}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  *) usage; exit 1 ;;
esac
