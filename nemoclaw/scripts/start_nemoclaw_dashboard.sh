#!/usr/bin/env bash
set -euo pipefail

SANDBOX_NAME="${1:-nemoclaw-main}"
LOCAL_PORT="${NEMOCLAW_DASHBOARD_PORT:-18789}"
TMP_DIR="$(mktemp -d)"
USER_HOME="${NEMOCLAW_USER_HOME:-${HOME}}"

if [ ! -x "${USER_HOME}/.local/bin/openshell" ] && [ -x "/home/zerausn/.local/bin/openshell" ]; then
  USER_HOME="/home/zerausn"
fi

cleanup() {
  rm -rf "$TMP_DIR"
}

trap cleanup EXIT

export HOME="${USER_HOME}"
export XDG_CONFIG_HOME="${USER_HOME}/.config"
export NVM_DIR="${USER_HOME}/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
fi

export PATH="${USER_HOME}/.local/bin:${PATH}"

if ! command -v openshell >/dev/null 2>&1; then
  echo "[nemoclaw-dashboard] openshell not found" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[nemoclaw-dashboard] node not found" >&2
  exit 1
fi

CONFIG_PATH="${TMP_DIR}/openclaw.json"
openshell sandbox download "$SANDBOX_NAME" /sandbox/.openclaw/openclaw.json "$TMP_DIR" >/dev/null

if [ ! -f "$CONFIG_PATH" ]; then
  echo "[nemoclaw-dashboard] could not download sandbox OpenClaw config" >&2
  exit 1
fi

TOKEN="$(
  node -e "const fs=require('fs'); const j=JSON.parse(fs.readFileSync(process.argv[1],'utf8')); const t=((j.gateway||{}).auth||{}).token||''; if (!t) process.exit(1); process.stdout.write(t);" \
    "$CONFIG_PATH"
)"

URL="http://127.0.0.1:${LOCAL_PORT}/#token=${TOKEN}"

echo "[nemoclaw-dashboard] sandbox: ${SANDBOX_NAME}"
echo "[nemoclaw-dashboard] UI: OpenClaw Control sobre la gateway de NemoClaw"
echo "[nemoclaw-dashboard] abre esta URL en tu navegador:"
echo "${URL}"
echo
echo "[nemoclaw-dashboard] este forward queda en primer plano para que no muera."
echo "[nemoclaw-dashboard] deja esta terminal abierta mientras uses el panel."
echo

openshell forward stop "${LOCAL_PORT}" -g nemoclaw >/dev/null 2>&1 || true
exec openshell forward start "${LOCAL_PORT}" "${SANDBOX_NAME}" -g nemoclaw
