#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "${ROOT_DIR}"

failed=0

check_fail() {
  printf 'FAIL: %s\n' "$1" >&2
  failed=1
}

check_pass() {
  printf 'PASS: %s\n' "$1"
}

if [[ -f "temperance/.env" ]]; then
  check_fail "temperance/.env exists inside the repo"
else
  check_pass "no repo-local temperance/.env"
fi

tracked_private="$(git ls-files -- '*.db' '*.sqlite' '*.sqlite3' 'temperance/data/private/*' 2>/dev/null || true)"
if [[ -n "${tracked_private}" ]]; then
  check_fail "private database artifacts are tracked"
  printf '%s\n' "${tracked_private}" >&2
else
  check_pass "no tracked private database artifacts"
fi

secret_hits="$(git grep -nI -E '-----BEGIN (RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}' -- . 2>/dev/null || true)"
if [[ -n "${secret_hits}" ]]; then
  check_fail "high-signal secret patterns found in tracked files"
  printf '%s\n' "${secret_hits}" >&2
else
  check_pass "no high-signal secret patterns in tracked files"
fi

if [[ "${failed}" -ne 0 ]]; then
  printf '\nRepo is not safe to leave open yet.\n' >&2
  exit 1
fi

printf '\nRepo safe-open check passed.\n'
