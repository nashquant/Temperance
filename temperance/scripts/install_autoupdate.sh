#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${APP_DIR}/data/private/logs"

LABEL="com.temperance.autoupdate"
PLIST_PATH="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"
SERVICE_SCRIPT="${APP_DIR}/scripts/service_autoupdate.sh"

INTERVAL_SECONDS="${INTERVAL_SECONDS:-3600}" # default: hourly
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-main}"

mkdir -p "${LAUNCH_AGENTS_DIR}" "${LOG_DIR}"

usage() {
  cat <<EOF
Usage: $(basename "$0") {install|uninstall|start|stop|restart|status|logs|run-now}

Env overrides:
  INTERVAL_SECONDS   Check interval in seconds (default: 3600)
  GIT_REMOTE         Git remote to track (default: origin)
  GIT_BRANCH         Git branch to track (default: main)
  TEMPERANCE_ENABLE_GIT_AUTOSYNC  Set to 1 to allow fetch/pull (default: disabled)
EOF
}

write_plist() {
  cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${SERVICE_SCRIPT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${APP_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>GIT_REMOTE</key>
    <string>${GIT_REMOTE}</string>
    <key>GIT_BRANCH</key>
    <string>${GIT_BRANCH}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>${INTERVAL_SECONDS}</integer>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/autoupdate_launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/autoupdate_launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF
}

load_job() {
  launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}" 2>/dev/null || launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"
}

unload_job() {
  launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" >/dev/null 2>&1 || true
}

status_job() {
  echo "Tracking: ${GIT_REMOTE}/${GIT_BRANCH}"
  echo "Interval: ${INTERVAL_SECONDS}s"
  echo "Auto-sync enabled: ${TEMPERANCE_ENABLE_GIT_AUTOSYNC:-0}"
  launchctl print "gui/$(id -u)/${LABEL}" 2>/dev/null | rg "state =|pid =|path =" || echo "${LABEL}: not loaded"
}

logs_job() {
  touch "${LOG_DIR}/autoupdate_launchd.out.log" "${LOG_DIR}/autoupdate_launchd.err.log"
  tail -f "${LOG_DIR}/autoupdate_launchd.out.log" "${LOG_DIR}/autoupdate_launchd.err.log"
}

cmd="${1:-}"
case "${cmd}" in
  install)
    chmod +x "${SERVICE_SCRIPT}"
    write_plist
    unload_job
    load_job
    echo "Installed auto-update job."
    status_job
    ;;
  uninstall)
    unload_job
    rm -f "${PLIST_PATH}"
    echo "Uninstalled auto-update job."
    ;;
  start)
    write_plist
    load_job
    status_job
    ;;
  stop)
    unload_job
    status_job
    ;;
  restart)
    unload_job
    write_plist
    load_job
    status_job
    ;;
  status)
    status_job
    ;;
  logs)
    logs_job
    ;;
  run-now)
    chmod +x "${SERVICE_SCRIPT}"
    "${SERVICE_SCRIPT}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
