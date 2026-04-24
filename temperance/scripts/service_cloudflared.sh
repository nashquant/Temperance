#!/usr/bin/env bash
set -euo pipefail

# Named tunnel runner for launchd keep-alive.
# Configure via env:
#   CLOUDFLARE_TUNNEL=temperance
#   TUNNEL_HOSTNAME=app.temperance-rtl.work

TUNNEL_NAME="${CLOUDFLARE_TUNNEL:-temperance}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"
CLOUDFLARED_PROTOCOL="${CLOUDFLARED_PROTOCOL:-http2}"
CF_CONFIG_PATH="${CF_CONFIG_PATH:-}"
USE_CAFFEINATE="${TEMPERANCE_USE_CAFFEINATE:-1}"
CAFFEINATE_BIN="${CAFFEINATE_BIN:-}"
if [[ -z "${CAFFEINATE_BIN}" ]]; then
  CAFFEINATE_BIN="$(command -v caffeinate || true)"
fi
if [[ "${CLOUDFLARED_BIN}" == /* ]]; then
  if [[ ! -x "${CLOUDFLARED_BIN}" ]]; then
    echo "cloudflared not executable: ${CLOUDFLARED_BIN}" >&2
    exit 1
  fi
else
  if ! command -v "${CLOUDFLARED_BIN}" >/dev/null 2>&1; then
    echo "cloudflared not found: ${CLOUDFLARED_BIN}" >&2
    exit 1
  fi
fi

cloudflared_args=()
if [[ -n "${CLOUDFLARED_PROTOCOL}" ]]; then
  cloudflared_args+=(--protocol "${CLOUDFLARED_PROTOCOL}")
fi

if [[ -n "${CF_CONFIG_PATH}" ]]; then
  if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
    exec "${CAFFEINATE_BIN}" -dimsu "${CLOUDFLARED_BIN}" "${cloudflared_args[@]}" --config "${CF_CONFIG_PATH}" tunnel run "${TUNNEL_NAME}"
  fi
  exec "${CLOUDFLARED_BIN}" "${cloudflared_args[@]}" --config "${CF_CONFIG_PATH}" tunnel run "${TUNNEL_NAME}"
fi

if [[ "${USE_CAFFEINATE}" == "1" && -n "${CAFFEINATE_BIN}" ]]; then
  exec "${CAFFEINATE_BIN}" -dimsu "${CLOUDFLARED_BIN}" "${cloudflared_args[@]}" tunnel run "${TUNNEL_NAME}"
fi

exec "${CLOUDFLARED_BIN}" "${cloudflared_args[@]}" tunnel run "${TUNNEL_NAME}"
