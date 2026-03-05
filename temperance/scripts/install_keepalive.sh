#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${ROOT_DIR}/data/private/logs"

STREAM_LABEL="com.temperance.streamlit"
CLOUD_LABEL="com.temperance.cloudflared"

STREAM_PLIST="${LAUNCH_AGENTS_DIR}/${STREAM_LABEL}.plist"
CLOUD_PLIST="${LAUNCH_AGENTS_DIR}/${CLOUD_LABEL}.plist"

STREAM_SCRIPT="${ROOT_DIR}/scripts/service_streamlit.sh"
CLOUD_SCRIPT="${ROOT_DIR}/scripts/service_cloudflared.sh"

PORT="${PORT:-8504}"
ADDRESS="${ADDRESS:-0.0.0.0}"
TUNNEL_NAME="${CLOUDFLARE_TUNNEL:-temperance}"
TUNNEL_HOSTNAME="${TUNNEL_HOSTNAME:-app.temperance-rtl.work}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"

mkdir -p "${LAUNCH_AGENTS_DIR}" "${LOG_DIR}"

usage() {
  cat <<EOF
Usage: $(basename "$0") {install|uninstall|start|stop|restart|status|logs}

Env overrides:
  PORT               Streamlit port (default: 8504)
  ADDRESS            Streamlit address (default: 0.0.0.0)
  CLOUDFLARE_TUNNEL  Named tunnel (default: temperance)
  TUNNEL_HOSTNAME    Hostname label (default: app.temperance-rtl.work)
  CLOUDFLARED_BIN    cloudflared binary (default: cloudflared)
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
  launchctl bootstrap "gui/$(id -u)" "${STREAM_PLIST}" 2>/dev/null || launchctl bootout "gui/$(id -u)" "${STREAM_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${STREAM_PLIST}"
  launchctl bootstrap "gui/$(id -u)" "${CLOUD_PLIST}" 2>/dev/null || launchctl bootout "gui/$(id -u)" "${CLOUD_PLIST}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${CLOUD_PLIST}"
}

unload_jobs() {
  launchctl bootout "gui/$(id -u)" "${CLOUD_PLIST}" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)" "${STREAM_PLIST}" >/dev/null 2>&1 || true
}

status_jobs() {
  echo "Expected public URL: https://${TUNNEL_HOSTNAME}"
  echo "Local URL:           http://127.0.0.1:${PORT}"
  echo
  launchctl print "gui/$(id -u)/${STREAM_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${STREAM_LABEL}: not loaded"
  launchctl print "gui/$(id -u)/${CLOUD_LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${CLOUD_LABEL}: not loaded"
}

logs_jobs() {
  touch "${LOG_DIR}/streamlit_launchd.out.log" "${LOG_DIR}/streamlit_launchd.err.log"
  touch "${LOG_DIR}/cloudflared_launchd.out.log" "${LOG_DIR}/cloudflared_launchd.err.log"
  tail -f \
    "${LOG_DIR}/streamlit_launchd.out.log" \
    "${LOG_DIR}/streamlit_launchd.err.log" \
    "${LOG_DIR}/cloudflared_launchd.out.log" \
    "${LOG_DIR}/cloudflared_launchd.err.log"
}

cmd="${1:-}"
case "${cmd}" in
  install)
    chmod +x "${STREAM_SCRIPT}" "${CLOUD_SCRIPT}"
    write_stream_plist
    write_cloud_plist
    unload_jobs
    load_jobs
    echo "Installed KeepAlive services."
    status_jobs
    ;;
  uninstall)
    unload_jobs
    rm -f "${STREAM_PLIST}" "${CLOUD_PLIST}"
    echo "Uninstalled KeepAlive services."
    ;;
  start)
    write_stream_plist
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
    write_stream_plist
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

