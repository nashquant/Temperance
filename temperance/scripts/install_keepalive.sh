#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${ROOT_DIR}/data/private/logs"

BACKEND_LABEL="com.temperance.backend"
FRONTEND_LABEL="com.temperance.frontend"
CLOUD_LABEL="com.temperance.cloudflared"

BACKEND_PLIST="${LAUNCH_AGENTS_DIR}/${BACKEND_LABEL}.plist"
FRONTEND_PLIST="${LAUNCH_AGENTS_DIR}/${FRONTEND_LABEL}.plist"
CLOUD_PLIST="${LAUNCH_AGENTS_DIR}/${CLOUD_LABEL}.plist"

BACKEND_SCRIPT="${ROOT_DIR}/scripts/service_backend.sh"
FRONTEND_SCRIPT="${ROOT_DIR}/scripts/service_frontend.sh"
CLOUD_SCRIPT="${ROOT_DIR}/scripts/service_cloudflared.sh"
CF_CONFIG_PATH="${ROOT_DIR}/data/private/cloudflared.keepalive.yml"

BACKEND_PORT="${BACKEND_PORT:-${V2_BACKEND_PORT:-8000}}"
FRONTEND_PORT="${FRONTEND_PORT:-${V2_FRONTEND_PORT:-5173}}"
BACKEND_HOST="${BACKEND_HOST:-${V2_BACKEND_HOST:-127.0.0.1}}"
FRONTEND_HOST="${FRONTEND_HOST:-${V2_FRONTEND_HOST:-127.0.0.1}}"
BACKEND_PYTHON_BIN="${BACKEND_PYTHON_BIN:-${V2_PYTHON_BIN:-$(cd "${ROOT_DIR}/.." && pwd)/backend/.venv/bin/python}}"
TUNNEL_NAME="${CLOUDFLARE_TUNNEL:-temperance}"
TUNNEL_HOSTNAME="${TUNNEL_HOSTNAME:-app.temperance-rtl.work}"
if [[ -z "${CLOUDFLARED_BIN:-}" ]]; then
  CLOUDFLARED_BIN="$(command -v cloudflared || true)"
fi
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"
if [[ -z "${NODE_BIN:-}" ]]; then
  NODE_BIN="$(command -v node || true)"
fi
NODE_BIN="${NODE_BIN:-/opt/homebrew/bin/node}"
TEMPERANCE_USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
if [[ -z "${CAFFEINATE_BIN:-}" ]]; then
  CAFFEINATE_BIN="$(command -v caffeinate || true)"
fi
CAFFEINATE_BIN="${CAFFEINATE_BIN:-/usr/bin/caffeinate}"

mkdir -p "${LAUNCH_AGENTS_DIR}" "${LOG_DIR}"

usage() {
  cat <<EOF
Usage: $(basename "$0") {install|uninstall|start|stop|restart|status|logs}

Env overrides:
  BACKEND_PORT       backend port (default: 8000)
  FRONTEND_PORT      frontend port (default: 5173)
  BACKEND_HOST       backend host bind (default: 127.0.0.1)
  FRONTEND_HOST      frontend host bind (default: 127.0.0.1)
  BACKEND_PYTHON_BIN backend python (default: ../backend/.venv/bin/python)
  CLOUDFLARE_TUNNEL  named tunnel (default: temperance)
  TUNNEL_HOSTNAME    hostname label (default: app.temperance-rtl.work)
  CLOUDFLARED_BIN    cloudflared binary (default: cloudflared)
  NODE_BIN           node binary (default: /opt/homebrew/bin/node)
  TEMPERANCE_USE_CAFFEINATE wrap services with caffeinate when available (default: 1)
  CAFFEINATE_BIN     caffeinate binary (default: /usr/bin/caffeinate)
EOF
}

write_backend_plist() {
  cat > "${BACKEND_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${BACKEND_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${BACKEND_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>BACKEND_PORT</key>
    <string>${BACKEND_PORT}</string>
    <key>BACKEND_HOST</key>
    <string>${BACKEND_HOST}</string>
    <key>BACKEND_PYTHON_BIN</key>
    <string>${BACKEND_PYTHON_BIN}</string>
    <key>TEMPERANCE_USE_CAFFEINATE</key>
    <string>${TEMPERANCE_USE_CAFFEINATE}</string>
    <key>CAFFEINATE_BIN</key>
    <string>${CAFFEINATE_BIN}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/backend_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/backend_launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF
}

write_frontend_plist() {
  cat > "${FRONTEND_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${FRONTEND_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${FRONTEND_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>FRONTEND_PORT</key>
    <string>${FRONTEND_PORT}</string>
    <key>FRONTEND_HOST</key>
    <string>${FRONTEND_HOST}</string>
    <key>NODE_BIN</key>
    <string>${NODE_BIN}</string>
    <key>TEMPERANCE_USE_CAFFEINATE</key>
    <string>${TEMPERANCE_USE_CAFFEINATE}</string>
    <key>CAFFEINATE_BIN</key>
    <string>${CAFFEINATE_BIN}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/frontend_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/frontend_launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF
}

write_cloudflared_config() {
  cat > "${CF_CONFIG_PATH}" <<EOF
tunnel: ${TUNNEL_NAME}
ingress:
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/api(?:/.*)?$"
    service: http://127.0.0.1:${BACKEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/health$"
    service: http://127.0.0.1:${BACKEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/@vite(?:/.*)?$"
    service: http://127.0.0.1:${FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/@react-refresh$"
    service: http://127.0.0.1:${FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/__vite_ping$"
    service: http://127.0.0.1:${FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/src(?:/.*)?$"
    service: http://127.0.0.1:${FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/node_modules(?:/.*)?$"
    service: http://127.0.0.1:${FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    service: http://127.0.0.1:${FRONTEND_PORT}
  - service: http_status:404
EOF
}

write_cloud_plist() {
  cat > "${CLOUD_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${CLOUD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${CLOUD_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CLOUDFLARE_TUNNEL</key>
    <string>${TUNNEL_NAME}</string>
    <key>TUNNEL_HOSTNAME</key>
    <string>${TUNNEL_HOSTNAME}</string>
    <key>CLOUDFLARED_BIN</key>
    <string>${CLOUDFLARED_BIN}</string>
    <key>CF_CONFIG_PATH</key>
    <string>${CF_CONFIG_PATH}</string>
    <key>TEMPERANCE_USE_CAFFEINATE</key>
    <string>${TEMPERANCE_USE_CAFFEINATE}</string>
    <key>CAFFEINATE_BIN</key>
    <string>${CAFFEINATE_BIN}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/cloudflared_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/cloudflared_launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF
}

load_jobs() {
  launchctl bootout "gui/$(id -u)" "${BACKEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${BACKEND_PLIST}"
  launchctl bootout "gui/$(id -u)" "${FRONTEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${FRONTEND_PLIST}"
  launchctl bootout "gui/$(id -u)" "${CLOUD_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${CLOUD_PLIST}"
}

restart_jobs() {
  local gui_domain="gui/$(id -u)"

  if launchctl print "${gui_domain}/${BACKEND_LABEL}" >/dev/null 2>&1; then
    launchctl kickstart -k "${gui_domain}/${BACKEND_LABEL}"
  else
    launchctl bootstrap "${gui_domain}" "${BACKEND_PLIST}"
  fi

  if launchctl print "${gui_domain}/${FRONTEND_LABEL}" >/dev/null 2>&1; then
    launchctl kickstart -k "${gui_domain}/${FRONTEND_LABEL}"
  else
    launchctl bootstrap "${gui_domain}" "${FRONTEND_PLIST}"
  fi

  if launchctl print "${gui_domain}/${CLOUD_LABEL}" >/dev/null 2>&1; then
    launchctl kickstart -k "${gui_domain}/${CLOUD_LABEL}"
  else
    launchctl bootstrap "${gui_domain}" "${CLOUD_PLIST}"
  fi
}

unload_jobs() {
  launchctl bootout "gui/$(id -u)" "${CLOUD_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "${FRONTEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "${BACKEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)/com.temperance.v2frontend" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)/com.temperance.v2backend" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)/com.temperance.streamlit" >/dev/null 2>&1 || true
  rm -f \
    "${LAUNCH_AGENTS_DIR}/com.temperance.v2frontend.plist" \
    "${LAUNCH_AGENTS_DIR}/com.temperance.v2backend.plist" \
    "${LAUNCH_AGENTS_DIR}/com.temperance.streamlit.plist"
}

status_jobs() {
  echo "Expected public URL: https://${TUNNEL_HOSTNAME}"
  echo "Local backend:       http://127.0.0.1:${BACKEND_PORT}"
  echo "Local frontend:      http://127.0.0.1:${FRONTEND_PORT}"
  echo "Public app URL:      https://${TUNNEL_HOSTNAME}"
  echo "Tunnel config:       ${CF_CONFIG_PATH}"
  echo "Caffeinate:          ${TEMPERANCE_USE_CAFFEINATE} (${CAFFEINATE_BIN})"
  echo
  launchctl print "gui/$(id -u)/${BACKEND_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${BACKEND_LABEL}: not loaded"
  launchctl print "gui/$(id -u)/${FRONTEND_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${FRONTEND_LABEL}: not loaded"
  launchctl print "gui/$(id -u)/${CLOUD_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${CLOUD_LABEL}: not loaded"
}

logs_jobs() {
  touch "${LOG_DIR}/backend_launchd.out.log" "${LOG_DIR}/backend_launchd.err.log"
  touch "${LOG_DIR}/frontend_launchd.out.log" "${LOG_DIR}/frontend_launchd.err.log"
  touch "${LOG_DIR}/cloudflared_launchd.out.log" "${LOG_DIR}/cloudflared_launchd.err.log"
  tail -f \
    "${LOG_DIR}/backend_launchd.out.log" \
    "${LOG_DIR}/backend_launchd.err.log" \
    "${LOG_DIR}/frontend_launchd.out.log" \
    "${LOG_DIR}/frontend_launchd.err.log" \
    "${LOG_DIR}/cloudflared_launchd.out.log" \
    "${LOG_DIR}/cloudflared_launchd.err.log"
}

cmd="${1:-}"
case "${cmd}" in
  install)
    chmod +x "${BACKEND_SCRIPT}" "${FRONTEND_SCRIPT}" "${CLOUD_SCRIPT}"
    write_cloudflared_config
    write_backend_plist
    write_frontend_plist
    write_cloud_plist
    unload_jobs
    load_jobs
    echo "Installed KeepAlive services."
    status_jobs
    ;;
  uninstall)
    unload_jobs
    rm -f "${BACKEND_PLIST}" "${FRONTEND_PLIST}" "${CLOUD_PLIST}"
    echo "Uninstalled KeepAlive services."
    ;;
  start)
    write_cloudflared_config
    write_backend_plist
    write_frontend_plist
    write_cloud_plist
    load_jobs
    status_jobs
    ;;
  stop)
    unload_jobs
    status_jobs
    ;;
  restart)
    write_cloudflared_config
    write_backend_plist
    write_frontend_plist
    write_cloud_plist
    restart_jobs
    status_jobs
    ;;
  status)
    status_jobs
    ;;
  logs)
    logs_jobs
    ;;
  *)
    usage
    exit 1
    ;;
esac
