#!/usr/bin/env bash
set -euo pipefail

# Named tunnel runner for launchd keep-alive.
# Configure via env:
#   CLOUDFLARE_TUNNEL=temperance
#   TUNNEL_HOSTNAME=app.temperance-rtl.work

TUNNEL_NAME="${CLOUDFLARE_TUNNEL:-temperance}"
CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-cloudflared}"
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

exec "${CLOUDFLARED_BIN}" tunnel run "${TUNNEL_NAME}"
