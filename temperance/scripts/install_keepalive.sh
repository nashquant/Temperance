#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${ROOT_DIR}/data/private/logs"

STREAM_LABEL="com.temperance.streamlit"
V2_BACKEND_LABEL="com.temperance.v2backend"
V2_FRONTEND_LABEL="com.temperance.v2frontend"
CLOUD_LABEL="com.temperance.cloudflared"

STREAM_PLIST="${LAUNCH_AGENTS_DIR}/${STREAM_LABEL}.plist"
V2_BACKEND_PLIST="${LAUNCH_AGENTS_DIR}/${V2_BACKEND_LABEL}.plist"
V2_FRONTEND_PLIST="${LAUNCH_AGENTS_DIR}/${V2_FRONTEND_LABEL}.plist"
CLOUD_PLIST="${LAUNCH_AGENTS_DIR}/${CLOUD_LABEL}.plist"

STREAM_SCRIPT="${ROOT_DIR}/scripts/service_streamlit.sh"
V2_BACKEND_SCRIPT="${ROOT_DIR}/scripts/service_v2_backend.sh"
V2_FRONTEND_SCRIPT="${ROOT_DIR}/scripts/service_v2_frontend.sh"
CLOUD_SCRIPT="${ROOT_DIR}/scripts/service_cloudflared.sh"
CF_CONFIG_PATH="${ROOT_DIR}/data/private/cloudflared.keepalive.yml"

PORT="${PORT:-8504}"
ADDRESS="${ADDRESS:-0.0.0.0}"
V2_BACKEND_PORT="${V2_BACKEND_PORT:-8000}"
V2_FRONTEND_PORT="${V2_FRONTEND_PORT:-5173}"
V2_BACKEND_HOST="${V2_BACKEND_HOST:-127.0.0.1}"
V2_FRONTEND_HOST="${V2_FRONTEND_HOST:-127.0.0.1}"
V2_PYTHON_BIN="${V2_PYTHON_BIN:-$(cd "${ROOT_DIR}/.." && pwd)/v2/backend/.venv/bin/python}"
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

mkdir -p "${LAUNCH_AGENTS_DIR}" "${LOG_DIR}"

usage() {
  cat <<EOF
Usage: $(basename "$0") {install|uninstall|start|stop|restart|status|logs}

Env overrides:
  PORT               Streamlit port (default: 8504)
  ADDRESS            Streamlit address (default: 0.0.0.0)
  V2_BACKEND_PORT    v2 backend port (default: 8000)
  V2_FRONTEND_PORT   v2 frontend port (default: 5173)
  V2_BACKEND_HOST    v2 backend host bind (default: 127.0.0.1)
  V2_FRONTEND_HOST   v2 frontend host bind (default: 127.0.0.1)
  V2_PYTHON_BIN      v2 backend python (default: ../v2/backend/.venv/bin/python)
  CLOUDFLARE_TUNNEL  Named tunnel (default: temperance)
  TUNNEL_HOSTNAME    Hostname label (default: app.temperance-rtl.work)
  CLOUDFLARED_BIN    cloudflared binary (default: cloudflared)
  NODE_BIN           node binary (default: /opt/homebrew/bin/node)
EOF
}

write_stream_plist() {
  cat > "${STREAM_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${STREAM_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${STREAM_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PORT</key>
    <string>${PORT}</string>
    <key>ADDRESS</key>
    <string>${ADDRESS}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/streamlit_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/streamlit_launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF
}

write_v2_backend_plist() {
  cat > "${V2_BACKEND_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${V2_BACKEND_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${V2_BACKEND_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>V2_BACKEND_PORT</key>
    <string>${V2_BACKEND_PORT}</string>
    <key>V2_BACKEND_HOST</key>
    <string>${V2_BACKEND_HOST}</string>
    <key>V2_PYTHON_BIN</key>
    <string>${V2_PYTHON_BIN}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/v2_backend_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/v2_backend_launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF
}

write_v2_frontend_plist() {
  cat > "${V2_FRONTEND_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${V2_FRONTEND_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${V2_FRONTEND_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>V2_FRONTEND_PORT</key>
    <string>${V2_FRONTEND_PORT}</string>
    <key>V2_FRONTEND_HOST</key>
    <string>${V2_FRONTEND_HOST}</string>
    <key>NODE_BIN</key>
    <string>${NODE_BIN}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/v2_frontend_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/v2_frontend_launchd.err.log</string>
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
    path: "^/v2(?:/.*)?$"
    service: http://127.0.0.1:${V2_FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/@vite(?:/.*)?$"
    service: http://127.0.0.1:${V2_FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/@react-refresh$"
    service: http://127.0.0.1:${V2_FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/__vite_ping$"
    service: http://127.0.0.1:${V2_FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/src(?:/.*)?$"
    service: http://127.0.0.1:${V2_FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/node_modules(?:/.*)?$"
    service: http://127.0.0.1:${V2_FRONTEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/api(?:/.*)?$"
    service: http://127.0.0.1:${V2_BACKEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    path: "^/health$"
    service: http://127.0.0.1:${V2_BACKEND_PORT}
  - hostname: ${TUNNEL_HOSTNAME}
    service: http://127.0.0.1:${PORT}
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
  launchctl bootout "gui/$(id -u)" "${STREAM_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${STREAM_PLIST}"
  launchctl bootout "gui/$(id -u)" "${V2_BACKEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${V2_BACKEND_PLIST}"
  launchctl bootout "gui/$(id -u)" "${V2_FRONTEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${V2_FRONTEND_PLIST}"
  launchctl bootout "gui/$(id -u)" "${CLOUD_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${CLOUD_PLIST}"
}

unload_jobs() {
  launchctl bootout "gui/$(id -u)" "${CLOUD_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "${V2_FRONTEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "${V2_BACKEND_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "${STREAM_PLIST}" >/dev/null 2>&1 || true
}

status_jobs() {
  echo "Expected public URL: https://${TUNNEL_HOSTNAME}"
  echo "Local v1 URL:        http://127.0.0.1:${PORT}"
  echo "Local v2 backend:    http://127.0.0.1:${V2_BACKEND_PORT}"
  echo "Local v2 frontend:   http://127.0.0.1:${V2_FRONTEND_PORT}/v2"
  echo "Public v2 URL:       https://${TUNNEL_HOSTNAME}/v2"
  echo "Tunnel config:       ${CF_CONFIG_PATH}"
  echo
  launchctl print "gui/$(id -u)/${STREAM_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${STREAM_LABEL}: not loaded"
  launchctl print "gui/$(id -u)/${V2_BACKEND_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${V2_BACKEND_LABEL}: not loaded"
  launchctl print "gui/$(id -u)/${V2_FRONTEND_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${V2_FRONTEND_LABEL}: not loaded"
  launchctl print "gui/$(id -u)/${CLOUD_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${CLOUD_LABEL}: not loaded"
}

logs_jobs() {
  touch "${LOG_DIR}/streamlit_launchd.out.log" "${LOG_DIR}/streamlit_launchd.err.log"
  touch "${LOG_DIR}/v2_backend_launchd.out.log" "${LOG_DIR}/v2_backend_launchd.err.log"
  touch "${LOG_DIR}/v2_frontend_launchd.out.log" "${LOG_DIR}/v2_frontend_launchd.err.log"
  touch "${LOG_DIR}/cloudflared_launchd.out.log" "${LOG_DIR}/cloudflared_launchd.err.log"
  tail -f \
    "${LOG_DIR}/streamlit_launchd.out.log" \
    "${LOG_DIR}/streamlit_launchd.err.log" \
    "${LOG_DIR}/v2_backend_launchd.out.log" \
    "${LOG_DIR}/v2_backend_launchd.err.log" \
    "${LOG_DIR}/v2_frontend_launchd.out.log" \
    "${LOG_DIR}/v2_frontend_launchd.err.log" \
    "${LOG_DIR}/cloudflared_launchd.out.log" \
    "${LOG_DIR}/cloudflared_launchd.err.log"
}

cmd="${1:-}"
case "${cmd}" in
  install)
    chmod +x "${STREAM_SCRIPT}" "${V2_BACKEND_SCRIPT}" "${V2_FRONTEND_SCRIPT}" "${CLOUD_SCRIPT}"
    write_cloudflared_config
    write_stream_plist
    write_v2_backend_plist
    write_v2_frontend_plist
    write_cloud_plist
    unload_jobs
    load_jobs
    echo "Installed KeepAlive services."
    status_jobs
    ;;
  uninstall)
    unload_jobs
    rm -f "${STREAM_PLIST}" "${V2_BACKEND_PLIST}" "${V2_FRONTEND_PLIST}" "${CLOUD_PLIST}"
    echo "Uninstalled KeepAlive services."
    ;;
  start)
    write_cloudflared_config
    write_stream_plist
    write_v2_backend_plist
    write_v2_frontend_plist
    write_cloud_plist
    load_jobs
    status_jobs
    ;;
  stop)
    unload_jobs
    status_jobs
    ;;
  restart)
    unload_jobs
    write_cloudflared_config
    write_stream_plist
    write_v2_backend_plist
    write_v2_frontend_plist
    write_cloud_plist
    load_jobs
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
