#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STREAMLIT_BIN="${ROOT_DIR}/.venv/bin/streamlit"
APP_FILE="${ROOT_DIR}/app.py"
LOG_DIR="${ROOT_DIR}/data/private/logs"
PID_FILE="${LOG_DIR}/streamlit_remote.pid"
LOG_FILE="${LOG_DIR}/streamlit_remote.log"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"
CLOUDFLARED_PID_FILE="${LOG_DIR}/cloudflared_remote.pid"
CLOUDFLARED_LOG_FILE="${LOG_DIR}/cloudflared_remote.log"

ADDRESS="${ADDRESS:-0.0.0.0}"
PORT="${PORT:-8501}"
CLOUDFLARE_MODE="${CLOUDFLARE_MODE:-quick}" # quick | named | off
CLOUDFLARE_TUNNEL="${CLOUDFLARE_TUNNEL:-}"  # required when CLOUDFLARE_MODE=named
TUNNEL_HOSTNAME="${TUNNEL_HOSTNAME:-app.temperance-rtl.work}"

mkdir -p "${LOG_DIR}"

usage() {
  cat <<EOF
Usage: $(basename "$0") {start|stop|restart|status|logs|public-url}

Environment overrides:
  ADDRESS            Streamlit bind address (default: 0.0.0.0)
  PORT               Streamlit port (default: 8501)
  CLOUDFLARE_MODE    quick | named | off (default: quick)
  CLOUDFLARE_TUNNEL  Named tunnel ID/name for cloudflared run (required for named)
  TUNNEL_HOSTNAME    Public hostname label to print in status (optional)
  CLOUDFLARED_BIN    cloudflared binary path/command (default: cloudflared)
EOF
}

is_running_streamlit() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

is_running_cloudflared() {
  if [[ -f "${CLOUDFLARED_PID_FILE}" ]]; then
    local pid
    pid="$(cat "${CLOUDFLARED_PID_FILE}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

print_urls() {
  echo "Local:      http://127.0.0.1:${PORT}"
  if [[ "${CLOUDFLARE_MODE}" == "named" ]]; then
    if [[ -n "${TUNNEL_HOSTNAME}" ]]; then
      echo "Public:     https://${TUNNEL_HOSTNAME}"
    else
      echo "Public:     named Cloudflare tunnel (${CLOUDFLARE_TUNNEL})"
    fi
  elif [[ "${CLOUDFLARE_MODE}" == "quick" ]]; then
    local quick_url
    quick_url="$(rg -o 'https://[-a-zA-Z0-9]+\\.trycloudflare\\.com' "${CLOUDFLARED_LOG_FILE}" -m 1 2>/dev/null || true)"
    if [[ -n "${quick_url}" ]]; then
      echo "Public:     ${quick_url}"
    else
      echo "Public:     quick tunnel starting (check ${CLOUDFLARED_LOG_FILE})"
    fi
  fi
}

start_cloudflared() {
  if [[ "${CLOUDFLARE_MODE}" == "off" ]]; then
    return 0
  fi
  if ! command -v "${CLOUDFLARED_BIN}" >/dev/null 2>&1; then
    echo "cloudflared not found (${CLOUDFLARED_BIN}). Set CLOUDFLARED_BIN or install cloudflared."
    return 1
  fi
  if is_running_cloudflared; then
    echo "cloudflared already running (pid $(cat "${CLOUDFLARED_PID_FILE}"))."
    return 0
  fi
  if [[ "${CLOUDFLARE_MODE}" == "named" && -z "${CLOUDFLARE_TUNNEL}" ]]; then
    echo "CLOUDFLARE_TUNNEL is required when CLOUDFLARE_MODE=named."
    return 1
  fi

  echo "Starting cloudflared (${CLOUDFLARE_MODE} mode)..."
  if [[ "${CLOUDFLARE_MODE}" == "named" ]]; then
    nohup "${CLOUDFLARED_BIN}" tunnel run "${CLOUDFLARE_TUNNEL}" >>"${CLOUDFLARED_LOG_FILE}" 2>&1 &
  else
    nohup "${CLOUDFLARED_BIN}" tunnel --url "http://127.0.0.1:${PORT}" >>"${CLOUDFLARED_LOG_FILE}" 2>&1 &
  fi
  local cpid=$!
  echo "${cpid}" >"${CLOUDFLARED_PID_FILE}"
  sleep 1
  if ! kill -0 "${cpid}" >/dev/null 2>&1; then
    echo "cloudflared failed to start. Recent logs:"
    tail -n 40 "${CLOUDFLARED_LOG_FILE}" || true
    rm -f "${CLOUDFLARED_PID_FILE}"
    return 1
  fi
  echo "cloudflared started (pid ${cpid})."
}

stop_cloudflared() {
  if ! is_running_cloudflared; then
    rm -f "${CLOUDFLARED_PID_FILE}"
    return 0
  fi
  local pid
  pid="$(cat "${CLOUDFLARED_PID_FILE}")"
  echo "Stopping cloudflared pid ${pid}..."
  kill "${pid}" >/dev/null 2>&1 || true
  sleep 1
  if kill -0 "${pid}" >/dev/null 2>&1; then
    kill -9 "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${CLOUDFLARED_PID_FILE}"
  echo "cloudflared stopped."
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
  if is_running_streamlit; then
    echo "Temperance is already running (pid $(cat "${PID_FILE}"))."
    start_cloudflared || true
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
    start_cloudflared || {
      echo "Stopping Streamlit because cloudflared failed."
      stop
      exit 1
    }
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
  if is_running_streamlit; then
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
    echo "Stopped Streamlit."
  else
    echo "Temperance is not running."
    rm -f "${PID_FILE}"
  fi
  stop_cloudflared
}

status() {
  if is_running_streamlit; then
    echo "Temperance is running (pid $(cat "${PID_FILE}"))."
    echo "Log: ${LOG_FILE}"
  else
    echo "Temperance is not running."
  fi
  if is_running_cloudflared; then
    echo "cloudflared is running (pid $(cat "${CLOUDFLARED_PID_FILE}"))."
    echo "cloudflared log: ${CLOUDFLARED_LOG_FILE}"
  else
    echo "cloudflared is not running."
  fi
  print_urls
}

logs() {
  echo "Tailing logs (Ctrl+C to exit)..."
  touch "${LOG_FILE}"
  touch "${CLOUDFLARED_LOG_FILE}"
  tail -f "${LOG_FILE}" "${CLOUDFLARED_LOG_FILE}"
}

public_url() {
  if [[ "${CLOUDFLARE_MODE}" == "off" ]]; then
    echo "Cloudflare mode is off."
    return 1
  fi
  if [[ "${CLOUDFLARE_MODE}" == "named" ]]; then
    echo "https://${TUNNEL_HOSTNAME}"
    return 0
  fi
  local quick_url
  quick_url="$(rg -o 'https://[-a-zA-Z0-9]+\\.trycloudflare\\.com' "${CLOUDFLARED_LOG_FILE}" -m 1 2>/dev/null || true)"
  if [[ -n "${quick_url}" ]]; then
    echo "${quick_url}"
    return 0
  fi
  echo "Quick tunnel URL not found yet. Check ${CLOUDFLARED_LOG_FILE}"
  return 1
}

cmd="${1:-}"
case "${cmd}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  public-url) public_url ;;
  *) usage; exit 1 ;;
esac
