#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "${APP_DIR}/.." && pwd)"
LOG_DIR="${APP_DIR}/data/private/logs"
KEEPALIVE_SCRIPT="${APP_DIR}/scripts/install_keepalive.sh"

REMOTE="${GIT_REMOTE:-origin}"
BRANCH="${GIT_BRANCH:-main}"

mkdir -p "${LOG_DIR}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

cd "${REPO_DIR}"

if [[ ! -d .git ]]; then
  log "skip: not a git repository (${REPO_DIR})"
  exit 0
fi

current_branch="$(git branch --show-current || true)"
if [[ "${current_branch}" != "${BRANCH}" ]]; then
  log "skip: current branch is '${current_branch}', expected '${BRANCH}'"
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  log "skip: working tree is dirty; not pulling."
  exit 0
fi

log "fetching ${REMOTE}/${BRANCH}..."
git fetch "${REMOTE}" "${BRANCH}" --prune

local_rev="$(git rev-parse HEAD)"
remote_rev="$(git rev-parse "${REMOTE}/${BRANCH}")"

if [[ "${local_rev}" == "${remote_rev}" ]]; then
  log "up-to-date (${local_rev:0:12})"
  exit 0
fi

if ! git merge-base --is-ancestor "${local_rev}" "${remote_rev}"; then
  log "skip: local is ahead/diverged from ${REMOTE}/${BRANCH}; manual action needed."
  exit 0
fi

log "pulling updates (ff-only)..."
git pull --ff-only "${REMOTE}" "${BRANCH}"
new_rev="$(git rev-parse HEAD)"
log "updated to ${new_rev:0:12}"

if [[ -x "${KEEPALIVE_SCRIPT}" ]]; then
  log "restarting keepalive services..."
  "${KEEPALIVE_SCRIPT}" restart >/dev/null 2>&1 || true
  log "keepalive restart requested."
else
  log "keepalive script not found/executable; skipped restart."
fi

